import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError
from sqlalchemy import select

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, async_session, init_db
from bot.handlers.admin import routers as admin_routers
from bot.handlers.user import routers as user_routers
from bot.utils.block_middleware import BlockMiddleware

logger = logging.getLogger(__name__)


async def ensure_root_admin() -> None:
    async with async_session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == ROOT_ADMIN_ID))
        root = result.scalar_one_or_none()
        if not root and ROOT_ADMIN_ID != 0:
            session.add(Admin(telegram_id=ROOT_ADMIN_ID, is_root=True))
            await session.commit()
            logger.info("✅ Root admin создан")


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(BlockMiddleware())
    for router in (*user_routers, *admin_routers):
        dispatcher.include_router(router)
    return dispatcher


async def on_startup(dispatcher: Dispatcher) -> None:
    await init_db()
    await ensure_root_admin()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🤖 Бот запущен в режиме polling (webhook отключён)")


async def on_shutdown(dispatcher: Dispatcher) -> None:
    await bot.session.close()
    logger.info("🛑 Bot polling остановлен")


async def start_bot() -> None:
    dispatcher = build_dispatcher()
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    try:
        await dispatcher.start_polling(bot)
    except TelegramConflictError:
        logger.warning("⚠️ Polling conflict detected — возможно, предыдущий процесс бота ещё завершается.")
        await asyncio.sleep(5)
        logger.info("🔁 Повторный запуск polling...")
        await dispatcher.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_bot())


if __name__ == "__main__":
    main()
