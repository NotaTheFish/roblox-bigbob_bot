import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.executor import start_webhook

from aiogram.dispatcher.filters import Command

from bot.config import TOKEN, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT, ROOT_ADMIN_ID
from bot.db import Base, engine, SessionLocal, Admin

# ----- Bot init -----
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ✅ Middleware — блокировка забаненных пользователей
from bot.utils.block_middleware import BlockMiddleware
dp.middleware.setup(BlockMiddleware())

# ----- DB -----
Base.metadata.create_all(bind=engine)

with SessionLocal() as s:
    root = s.query(Admin).filter_by(telegram_id=ROOT_ADMIN_ID).first()
    if not root:
        s.add(Admin(telegram_id=ROOT_ADMIN_ID, is_root=True))
        s.commit()
        print("✅ Root admin added to DB")


# =========================================================
#  HANDLERS
# =========================================================

# ✅ Admin login / approve system
from bot.handlers.admin.login import register_admin_login
register_admin_login(dp)

# ✅ Admin menu
from bot.handlers.admin.menu import register_admin_menu
register_admin_menu(dp)

# ✅ Admin: users control
from bot.handlers.admin.users import register_admin_users
register_admin_users(dp)

# ✅ Admin: promo system
from bot.handlers.admin.promo import register_admin_promos
register_admin_promos(dp)

# ✅ Admin: shop system
from bot.handlers.admin.shop import register_admin_shop
register_admin_shop(dp)

# ✅ Admin: topup approvals
from bot.handlers.admin.payments import register_admin_payments
register_admin_payments(dp)

# ✅ Admin: achievements
from bot.handlers.admin.achievements import register_admin_achievements
register_admin_achievements(dp)


# ========== USER HANDLERS ==========

# ✅ User: promo activation
from bot.handlers.user.promo import activate_promo
dp.register_message_handler(activate_promo, Command("promo"))

# ✅ User: shop
from bot.handlers.user.shop import user_shop, user_buy_confirm, user_buy_finish, cancel_buy
dp.register_message_handler(user_shop, commands=["shop"])
dp.register_callback_query_handler(user_buy_confirm, lambda c: c.data.startswith("user_buy:"))
dp.register_callback_query_handler(user_buy_finish, lambda c: c.data.startswith("user_buy_ok:"))
dp.register_callback_query_handler(cancel_buy, lambda c: c.data == "cancel_buy")

# ✅ User: top up
from bot.handlers.user.balance import topup_start, topup_pick_method, topup_enter_amount
from bot.states.user_states import TopUpState

dp.register_message_handler(topup_start, commands=["topup"])
dp.register_callback_query_handler(topup_pick_method, lambda c: c.data.startswith("pay_"), state=TopUpState.waiting_for_method)
dp.register_message_handler(topup_enter_amount, state=TopUpState.waiting_for_amount)

# ✅ User: achievements
from bot.handlers.user.achievements import my_achievements
dp.register_message_handler(my_achievements, commands=["achievements"])

# ✅ User: Roblox verification ⭐
from bot.handlers.user.verify import register_verify
register_verify(dp)

# ✅ Start handler with verification control
from bot.handlers.user.start import register_start
register_start(dp)


# =========================================================
#  WEBHOOK
# =========================================================

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    print(f"🚀 Webhook set: {WEBHOOK_URL}")

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
