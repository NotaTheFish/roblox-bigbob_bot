from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.db import SessionLocal, Admin, AdminRequest
from bot.config import ADMIN_LOGIN_PASSWORD, ROOT_ADMIN_ID
from bot.main_core import bot

# ---------------- BAL: проверка админа ----------------
def is_admin(uid: int) -> bool:
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())


# ---------------- Команда /admin_login ----------------
async def admin_login(message: types.Message):
    args = message.get_args()
    if not args:
        return await message.reply("Введите секретный код:\n`/admin_login CODE`", parse_mode="Markdown")

    if args.strip() != ADMIN_LOGIN_PASSWORD:
        return await message.reply("❌ Неверный код")

    uid = message.from_user.id

    if is_admin(uid):
        return await message.reply("✅ Вы уже админ")

    with SessionLocal() as s:
        s.add(AdminRequest(
            telegram_id=uid,
            username=message.from_user.username or "unknown"
        ))
        s.commit()

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Разрешить", callback_data=f"admin_ok:{uid}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_no:{uid}")
    )

    await bot.send_message(
        ROOT_ADMIN_ID,
        f"👤 Пользователь @{message.from_user.username} хочет стать админом",
        reply_markup=kb
    )

    await message.reply("⌛ Запрос отправлен, ожидайте одобрения")


# ---------------- Callback: approve / deny ----------------
async def admin_request_callback(call: types.CallbackQuery):
    uid = int(call.data.split(":")[1])

    with SessionLocal() as s:
        req = s.query(AdminRequest).filter_by(telegram_id=uid, status="pending").first()
        if not req:
            return await call.answer("Заявка не найдена", show_alert=True)

        if call.data.startswith("admin_ok"):
            req.status = "approved"
            s.add(Admin(telegram_id=uid, is_root=False))
            msg = "✅ Ваша заявка на админку одобрена"
            result = "Админ одобрен ✅"
        else:
            req.status = "denied"
            msg = "❌ Вам отказано"
            result = "Админ отклонён ❌"

        s.commit()

    await bot.send_message(uid, msg)
    await call.message.edit_text(result)
    await call.answer()


# ---------------- Register ----------------
def register_admin_login(dp: Dispatcher):
    dp.register_message_handler(admin_login, Command("admin_login"))
    dp.register_callback_query_handler(
        admin_request_callback,
        lambda c: c.data.startswith("admin_ok") or c.data.startswith("admin_no")
    )
