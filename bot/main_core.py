import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.executor import start_webhook

from bot.config import TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT
from bot.db import Base, engine, SessionLocal, Admin
from bot.config import ROOT_ADMIN_ID
from bot.handlers.admin.menu import register_admin_menu
from bot.handlers.admin.users import register_admin_users
register_admin_users(dp)


# ----- Create bot & storage -----
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ✅ подключаем блокировку middleware
from bot.utils.block_middleware import BlockMiddleware
dp.middleware.setup(BlockMiddleware())

# ----- DB init -----
Base.metadata.create_all(bind=engine)

# ensure root admin exists
with SessionLocal() as s:
    root = s.query(Admin).filter_by(telegram_id=ROOT_ADMIN_ID).first()
    if not root:
        s.add(Admin(telegram_id=ROOT_ADMIN_ID, is_root=True))
        s.commit()
        print("✅ Root admin added to DB")


# =========================================================
#  HANDLERS REGISTRATION
# =========================================================

# admin
from bot.handlers.admin.login import register_admin_login

# user (позже подключим, пока оставим пустым)
# from bot.handlers.user.start import register_start

# register
register_admin_login(dp)
register_admin_menu(dp)
# register_start(dp)

# =========================================================
#  WEBHOOK
# =========================================================

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    print("🚀 Bot webhook set:", WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == "__main__":
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
