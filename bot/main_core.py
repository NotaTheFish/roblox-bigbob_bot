import logging
from aiogram import types
from aiohttp import web
from sqlalchemy import select

from bot.bot_instance import bot, dp
from bot.config import (
    WEBHOOK_URL,
    WEBHOOK_PATH,
    WEBAPP_HOST,
    WEBAPP_PORT,
    ROOT_ADMIN_ID,
)
from bot.db import Admin, async_session, init_db
from bot.utils.block_middleware import BlockMiddleware

# --- Логирование ---
logging.basicConfig(level=logging.INFO)

# ==========================================================
#  ✅ Подключаем handlers
# ==========================================================

# --- User handlers ---
from bot.handlers.user.start import register_start
from bot.handlers.user.menu import register_user_menu
from bot.handlers.user.verify import register_verify
from bot.handlers.user.promo import register_promo
from bot.handlers.user.shop import register_user_shop
from bot.handlers.user.balance import register_user_balance

# --- Admin handlers ---
from bot.handlers.admin.users import register_admin_users
from bot.handlers.admin.promo import register_admin_promo
from bot.handlers.admin.shop import register_admin_shop
from bot.handlers.admin.payments import register_admin_payments
from bot.handlers.admin.menu import register_admin_menu
from bot.handlers.admin.login import register_admin_login
from bot.handlers.admin.achievements import register_admin_achievements

_handlers_registered = False


def setup_handlers() -> None:
    global _handlers_registered
    if _handlers_registered:
        return

    # middleware
    dp.middleware.setup(BlockMiddleware())

    # user
    register_start(dp)
    register_user_menu(dp)
    register_verify(dp)
    register_promo(dp)
    register_user_shop(dp)
    register_user_balance(dp)

    # admin
    register_admin_users(dp)
    register_admin_promo(dp)
    register_admin_shop(dp)
    register_admin_payments(dp)
    register_admin_menu(dp)
    register_admin_login(dp)
    register_admin_achievements(dp)

    _handlers_registered = True


# ==========================================================
#  ✅ Webhook system
# ==========================================================

async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.process_update(update)
    return web.Response()


async def ensure_root_admin():
    async with async_session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == ROOT_ADMIN_ID))
        root = result.scalar_one_or_none()

        if not root and ROOT_ADMIN_ID != 0:
            session.add(Admin(telegram_id=ROOT_ADMIN_ID, is_root=True))
            await session.commit()
            logging.info("✅ Root admin создан")


async def on_startup(app):
    # webhook
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")

    # init DB async
    await init_db()

    # ensure admin exists
    await ensure_root_admin()


async def on_shutdown(app):
    await bot.delete_webhook()
    logging.info("🛑 Webhook удалён")


def main():
    setup_handlers()
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    main()
