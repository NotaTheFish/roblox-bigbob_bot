from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.exceptions import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import or_, select

from bot.db import Admin, User, async_session
from bot.states.admin_states import GiveMoneyState
from bot.utils.achievement_checker import check_achievements


router = Router(name="admin_users")


# -------- Проверка админа --------
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# -------- Кнопки карточки пользователя --------
def user_card_kb(user_id, is_blocked):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Выдать валюту", callback_data=f"give_money:{user_id}"))
    if is_blocked:
        kb.add(InlineKeyboardButton("✅ Разблокировать", callback_data=f"unblock_user:{user_id}"))
    else:
        kb.add(InlineKeyboardButton("🚫 Заблокировать", callback_data=f"block_user:{user_id}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_users"))
    return kb


# -------- /admin_users — список --------
@router.callback_query(F.data == "admin_users")
async def admin_users_list(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("⛔ Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("⛔ Нет доступа", show_alert=True)

    async with async_session() as session:
        users = (
            await session.scalars(select(User).order_by(User.balance.desc()).limit(50))
        ).all()

    if not users:
        return await call.message.edit_text("Пользователей пока нет.")

    text = "👥 <b>ТОП 50 пользователей по балансу</b>\n\n"
    for u in users:
        name = f"@{u.tg_username}" if u.tg_username else (u.username or f"ID {u.tg_id}")
        text += f"• <code>{name}</code> — 💰 {u.balance}\n"

    text += "\n🔎 Отправьте Telegram ID, @username или Roblox ник для поиска"
    await call.message.edit_text(text, parse_mode="HTML")


# -------- Поиск пользователя --------
@router.message(F.text)
async def admin_search_user(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        raise SkipHandler()

    query = message.text.strip().lstrip("@")
    if not query:
        return await message.reply("Введите запрос для поиска")

    filters = []
    if query.isdigit():
        tg_id = int(query)
        filters.append(User.tg_id == tg_id)

    like_pattern = f"%{query}%"
    filters.append(User.tg_username.ilike(like_pattern))
    filters.append(User.username.ilike(like_pattern))

    async with async_session() as session:
        user = await session.scalar(select(User).where(or_(*filters)))

    if not user:
        return await message.reply("❌ Пользователь не найден")

    tg_username = f"@{user.tg_username}" if user.tg_username else "—"
    roblox_username = user.username or "—"
    roblox_id = user.roblox_id or "—"
    created_at = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"

    text = (
        f"<b>👤 Пользователь найден</b>\n"
        f"TG: {tg_username}\n"
        f"TG ID: <code>{user.tg_id}</code>\n"
        f"Roblox: <code>{roblox_username}</code>\n"
        f"Roblox ID: <code>{roblox_id}</code>\n"
        f"Баланс: 💰 {user.balance}\n"
        f"Дата регистрации: {created_at}\n"
    )

    await message.reply(text, reply_markup=user_card_kb(user.tg_id, user.is_blocked), parse_mode="HTML")


# -------- Управление пользователем: блок/разблок/выдача -------
@router.callback_query(
    F.data.startswith("give_money")
    | F.data.startswith("block_user")
    | F.data.startswith("unblock_user")
)
async def user_management_actions(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    action, user_id = call.data.split(":")
    user_id = int(user_id)

    # Выдача денег
    if action == "give_money":
        await call.message.answer(
            f"Введите сумму для пользователя <code>{user_id}</code>:", parse_mode="HTML"
        )
        call.bot.data["give_money_target"] = user_id
        await state.set_state(GiveMoneyState.waiting_for_amount)
        return

    # Блокировка и разблокировка
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return await call.answer("Пользователь не найден", show_alert=True)

        if action == "block_user":
            user.is_blocked = True
            await session.commit()
            await call.bot.send_message(user_id, "⛔ Ваш доступ к боту заблокирован.")
            await call.message.edit_text("✅ Пользователь заблокирован")
            return await call.answer()

        if action == "unblock_user":
            user.is_blocked = False
            await session.commit()
            await call.bot.send_message(user_id, "✅ Ваш доступ восстановлен.")
            await call.message.edit_text("✅ Пользователь разблокирован")
            return await call.answer()


# -------- Процесс выдачи валюты --------
@router.message(StateFilter(GiveMoneyState.waiting_for_amount))
async def process_money_amount(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    try:
        amount = int(message.text)
        if amount <= 0 or amount > 1_000_000:
            return await message.reply("❌ Введите сумму от 1 до 1,000,000")
    except ValueError:
        return await message.reply("❌ Нужно число")

    user_id = message.bot.data.get("give_money_target")
    if not user_id:
        await state.clear()
        return await message.reply("Ошибка: ID пользователя потерян")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        user.balance += amount
        await session.commit()

    await check_achievements(user)

    await message.reply(
        f"✅ Выдано <b>{amount}</b> монет пользователю <code>{user_id}</code>", parse_mode="HTML"
    )

    try:
        await message.bot.send_message(
            user_id, f"🎁 Вам выдано <b>{amount}</b> монет администратором!"
        )
    except Exception:
        pass

    await state.clear()
