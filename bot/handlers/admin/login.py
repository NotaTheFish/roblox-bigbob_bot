from __future__ import annotations

from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.bot_instance import bot
from bot.config import ADMIN_LOGIN_PASSWORD, ROOT_ADMIN_ID
from bot.db import Admin, AdminRequest, async_session


# ---------------- Проверка админа ----------------
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# ---------------- Команда /admin_login ----------------
async def admin_login(message: types.Message):
    args = message.get_args()
    if not args:
        return await message.reply(
            "Введите секретный код:\n`/admin_login CODE`",
            parse_mode="Markdown"
        )

    if args.strip() != ADMIN_LOGIN_PASSWORD:
        return await message.reply("❌ Неверный код")

    if not message.from_user:
        return

    uid = message.from_user.id

    if await is_admin(uid):
        return await message.reply("✅ Вы уже админ")

    async with async_session() as session:
        pending = await session.scalar(
            select(AdminRequest).where(
                AdminRequest.telegram_id == uid,
                AdminRequest.status == "pending"
            )
        )

        if pending:
            return await message.reply("⌛ Ваша заявка уже ожидает рассмотрения")

        session.add(
            AdminRequest(
                telegram_id=uid,
                username=message.from_user.username or "unknown"
            )
        )
        await session.commit()

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

    async with async_session() as session:
        req = await session.scalar(
            select(AdminRequest).where(
                AdminRequest.telegram_id == uid,
                AdminRequest.status == "pending"
            )
        )

        if not req:
            return await call.answer("Заявка не найдена", show_alert=True)

        if call.data.startswith("admin_ok"):
            req.status = "approved"
            session.add(Admin(telegram_id=uid, is_root=False))
            msg = "✅ Ваша заявка на админку одобрена"
            result = "Админ одобрен ✅"
        else:
            req.status = "denied"
            msg = "❌ Вам отказано"
            result = "Админ отклонён ❌"

        await session.commit()

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
