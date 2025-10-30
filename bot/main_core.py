import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ParseMode
from aiohttp import web

from bot.config import TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT, ROOT_ADMIN_ID
from bot.db import SessionLocal, Admin

# --- Логирование ---
logging.basicConfig(level=logging.INFO)

# --- Бот и диспетчер ---
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

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

register_start(dp)
register_user_menu(dp)
register_verify(dp)
register_promo(dp)
register_user_shop(dp)
register_user_balance(dp)

# --- Admin handlers ---
from bot.handlers.admin.users import register_admin_users
from bot.handlers.admin.promo import register_admin_promo
from bot.handlers.admin.shop import register_admin_shop
from bot.handlers.admin.payments import register_admin_payments
from bot.handlers.admin.main_admin import register_admin_panel

register_admin_users(dp)
register_admin_promo(dp)
register_admin_shop(dp)
register_admin_payments(dp)
register_admin_panel(dp)

# ==========================================================
#  ✅ Webhook system
# ==========================================================

async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.process_update(update)
    return web.Response()

async def on_startup(app):
    # Set webhook
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")

    # Ensure root admin exists
    with SessionLocal() as s:
        root = s.query(Admin).filter_by(telegram_id=ROOT_ADMIN_ID).first()
        if not root:
            s.add(Admin(telegram_id=ROOT_ADMIN_ID, role="root"))
            s.commit()
            logging.info("✅ Root admin создан в базе")

async def on_shutdown(app):
    await bot.delete_webhook()
    logging.info("🛑 Webhook удалён")

def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

if __name__ == "__main__":
    main()
