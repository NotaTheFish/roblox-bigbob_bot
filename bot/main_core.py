from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ParseMode
from aiohttp import web

from bot.config import TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT
from bot.db import SessionLocal, Admin

# --- Инициализация бота ---
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==========================================================
#        ✅ РЕГИСТРАЦИЯ ВСЕХ HANDLER'ОВ ТУТ
# ==========================================================

# ✅ Start handler + верификация
from bot.handlers.user.start import register_start
register_start(dp)

# ✅ Основное меню пользователя
from bot.handlers.user.menu import register_user_menu
register_user_menu(dp)

# ✅ Верификация Roblox
from bot.handlers.user.verify import register_verify
register_verify(dp)

# ✅ Промокоды (пользователь)
from bot.handlers.user.promo import register_promo
register_promo(dp)

# ✅ Магазин (покупки)
from bot.handlers.user.shop import register_user_shop
register_user_shop(dp)

# ✅ Пополнение баланса (пользователь)
from bot.handlers.user.payments import register_user_payments
register_user_payments(dp)

# ✅ Админ — пользователи
from bot.handlers.admin.users import register_admin_users
register_admin_users(dp)

# ✅ Админ — промокоды
from bot.handlers.admin.promo import register_admin_promo
register_admin_promo(dp)

# ✅ Админ — магазин
from bot.handlers.admin.shop import register_admin_shop
register_admin_shop(dp)

# ✅ Админ — пополнения
from bot.handlers.admin.payments import register_admin_payments
register_admin_payments(dp)

# ✅ Админ меню
from bot.handlers.admin.main_admin import register_admin_panel
register_admin_panel(dp)

# ==========================================================
#                 ✅ СИСТЕМА WEBHOOK
# ==========================================================

async def handle(request):
    req = await request.json()
    update = types.Update(**req)
    await dp.process_update(update)
    return web.Response()

async def on_startup(dp):
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    print("✅ Webhook установлен:", WEBHOOK_URL + WEBHOOK_PATH)

async def on_shutdown(dp):
    await bot.delete_webhook()
    print("🛑 Webhook удалён")

def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle)

    # Root admin check
    with SessionLocal() as s:
        admin = s.query(Admin).first()
        if not admin:
            print("⚠️ Нет главного админа в базе! Выдать /admin_login и назначить.")

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)


if __name__ == "__main__":
    main()
