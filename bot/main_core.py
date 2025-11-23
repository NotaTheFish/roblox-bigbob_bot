import asyncio
import logging
import os
from contextlib import suppress
from typing import Optional

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.exceptions import TelegramConflictError
from sqlalchemy import select

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, async_session, init_db
from bot.handlers.admin import routers as admin_routers
from bot.handlers.global_block_filter import router as global_block_filter_router
from bot.handlers.user import routers as user_routers
from bot.middleware import BannedMiddleware, BotStatusMiddleware, CallbackDedupMiddleware, UserSyncMiddleware

# Firebase sync
from bot.firebase.firebase_service import init_firebase, firebase_sync_loop

logger = logging.getLogger(__name__)


redis_url = os.getenv("REDIS_URL")

if redis_url:
    storage = RedisStorage.from_url(redis_url)
else:
    logger.warning("REDIS_URL is not set; falling back to in-memory FSM storage (non-persistent).")
    storage = MemoryStorage()

firebase_sync_task: Optional[asyncio.Task] = None


async def ensure_root_admin() -> None:
    async with async_session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == ROOT_ADMIN_ID))
        root = result.scalar_one_or_none()

        if not root and ROOT_ADMIN_ID != 0:
            session.add(Admin(telegram_id=ROOT_ADMIN_ID, is_root=True))
            await session.commit()
            logger.info("✅ Root admin создан")


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=storage)

    dispatcher.update.outer_middleware(BotStatusMiddleware())
    dispatcher.update.outer_middleware(UserSyncMiddleware())
    dispatcher.update.outer_middleware(CallbackDedupMiddleware())
    dispatcher.update.outer_middleware(BannedMiddleware())

    dispatcher.include_router(global_block_filter_router)
    for router in (*user_routers, *admin_routers):
        dispatcher.include_router(router)

    return dispatcher


async def on_startup(dispatcher: Dispatcher) -> None:
    await init_db()
    await ensure_root_admin()

    # Инициализация Firebase
    try:
        init_firebase()
        logger.info("🔥 Firebase инициализирован!")
    except Exception as e:
        logger.error(f"❌ Firebase init error: {e}")

    # Запуск фонового синка
    global firebase_sync_task
    firebase_sync_task = asyncio.create_task(firebase_sync_loop())
    logger.info("🔄 Firebase sync task запущен")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🤖 Бот запущен (polling)")


async def on_shutdown(dispatcher: Dispatcher) -> None:
    global firebase_sync_task

    if firebase_sync_task:
        firebase_sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await firebase_sync_task
        logger.info("🔻 Firebase sync task остановлен")

    await bot.session.close()
    logger.info("🛑 Бот остановлен")


async def start_bot() -> None:
    dispatcher = build_dispatcher()
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    try:
        await dispatcher.start_polling(bot)
    except TelegramConflictError:
        logger.warning("⚠️ Polling conflict — ждём завершения старого процесса...")
        await asyncio.sleep(5)
        await dispatcher.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_bot())


if __name__ == "__main__":
    main()
