from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.config import ADMIN_LOGIN_PASSWORD, ROOT_ADMIN_ID
from bot.db import Admin, AdminRequest, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb
from bot.states.admin_states import AdminLoginState


# ---------------- Router ----------------
router = Router(name="admin_login")


logger = logging.getLogger(__name__)


# ---------------- Проверка админа ----------------
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# ---------------- Команда /admin_login ----------------
async def _process_admin_code(message: types.Message, code: str) -> bool:
    code = (code or "").strip()

    if not code:
        await message.reply("❌ Код не может быть пустым")
        return False

    if code != ADMIN_LOGIN_PASSWORD:
        await message.reply("❌ Неверный код")
        return False

    if not message.from_user:
        return False

    uid = message.from_user.id

    if await is_admin(uid):
        await message.reply("✅ Вы уже админ", reply_markup=admin_main_menu_kb())
        return True

    username = message.from_user.username or "unknown"

    async with async_session() as session:
        pending = await session.scalar(
            select(AdminRequest).where(
                AdminRequest.telegram_id == uid,
                AdminRequest.status == "pending"
            )
        )

        if pending:
            await message.reply("⌛ Ваша заявка уже ожидает рассмотрения")
            return True

        request = AdminRequest(
            telegram_id=uid,
            username=username
        )
        session.add(request)
        await session.commit()
        request_id = request.request_id

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Разрешить", callback_data=f"approve_admin:{request_id}")
    builder.button(text="❌ Отклонить", callback_data=f"reject_admin:{request_id}")
    builder.adjust(2)
    reply_markup = builder.as_markup()

    await message.bot.send_message(
        ROOT_ADMIN_ID,
        (
            "👤 Пользователь @{} хочет стать админом\n"
            "🆔 ID заявки: {}"
        ).format(username, request_id),
        **({"reply_markup": reply_markup} if reply_markup else {})
    )

    await message.reply("⌛ Запрос отправлен, ожидайте одобрения")
    return True


@router.message(Command("admin_login"))
async def admin_login(message: types.Message, command: CommandObject):
    args = (command.args or "").strip()
    if not args:
        return await message.reply(
            "Введите секретный код:\n`/admin_login CODE`",
            parse_mode="Markdown"
        )

    await _process_admin_code(message, args)


@router.message(F.text == "Ввести секретный код администратора")
async def admin_login_prompt(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    await state.set_state(AdminLoginState.waiting_for_code)
    await message.reply("🔐 Введите секретный код администратора:")


@router.message(AdminLoginState.waiting_for_code)
async def admin_login_code_input(message: types.Message, state: FSMContext):
    success = await _process_admin_code(message, message.text or "")
    if success:
        await state.clear()


# ---------------- Callback: approve / deny ----------------
@router.callback_query(F.data.startswith("approve_admin") | F.data.startswith("reject_admin"))
async def admin_request_callback(call: types.CallbackQuery):
    request_id = call.data.split(":", 1)[1]

    async with async_session() as session:
        req = await session.scalar(
            select(AdminRequest).where(
                AdminRequest.request_id == request_id,
                AdminRequest.status == "pending"
            )
        )

        if not req:
            return await call.answer("Заявка не найдена", show_alert=True)

        uid = req.telegram_id
        username = req.username or "unknown"

        moderator_id = call.from_user.id if call.from_user else "unknown"

        if call.data.startswith("approve_admin"):
            req.status = "approved"
            session.add(Admin(telegram_id=uid, is_root=False))
            msg = "✅ Ваша заявка на админку одобрена"
            result = "Админ одобрен ✅"
            reply_markup = admin_main_menu_kb()
            logger.info(
                "Admin request %s approved by %s for user %s",
                request_id,
                moderator_id,
                uid,
            )
        else:
            req.status = "denied"
            msg = "❌ Вам отказано"
            result = "Админ отклонён ❌"
            reply_markup = None
            logger.info(
                "Admin request %s rejected by %s for user %s",
                request_id,
                moderator_id,
                uid,
            )

        await session.commit()

    if reply_markup:
        await call.bot.send_message(uid, msg, reply_markup=reply_markup)
    else:
        await call.bot.send_message(uid, msg)
    await call.bot.send_message(
        ROOT_ADMIN_ID,
        (
            "🆔 Заявка {request_id} пользователя @{username}: {result}"
        ).format(request_id=request_id, username=username, result=result)
    )
    await call.message.edit_text(f"{result}\n🆔 Заявка: {request_id}")
    await call.answer()
