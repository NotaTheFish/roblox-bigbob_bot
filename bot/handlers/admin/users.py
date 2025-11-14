from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import or_, select

from bot.db import Admin, User, async_session
from bot.keyboards.admin_keyboards import (
    admin_main_menu_kb,
    admin_users_menu_kb,
)
from bot.services.user_titles import get_user_titles_by_tg_id, normalize_titles
from bot.states.admin_states import (
    AdminUsersState,
    GiveMoneyState,
    GiveTitleState,
    RemoveMoneyState,
)
from bot.utils.achievement_checker import check_achievements


router = Router(name="admin_users")
logger = logging.getLogger(__name__)


# -------- Проверка админа --------
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# -------- Кнопки карточки пользователя --------
def user_card_kb(user_id, is_blocked):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Выдать валюту", callback_data=f"give_money:{user_id}"
    )
    builder.button(
        text="➖ Удержать валюту", callback_data=f"remove_money:{user_id}"
    )
    if is_blocked:
        builder.button(
            text="✅ Разблокировать", callback_data=f"unblock_user:{user_id}"
        )
    else:
        builder.button(
            text="🚫 Заблокировать", callback_data=f"block_user:{user_id}"
        )
    builder.button(text="🎖 Выдать титул", callback_data=f"give_title:{user_id}")
    builder.button(text="⬅️ Назад", callback_data="admin_users")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


# -------- /admin_users — список --------
async def _send_users_list(message: types.Message):
    async with async_session() as session:
        users = (
            await session.scalars(select(User).order_by(User.balance.desc()).limit(50))
        ).all()

    if not users:
        return await message.answer(
            "Пользователей пока нет.",
            reply_markup=admin_users_menu_kb(),
        )

    text = "👥 <b>ТОП 50 пользователей по балансу</b>\n\n"
    for u in users:
        name = f"@{u.tg_username}" if u.tg_username else (u.username or f"ID {u.tg_id}")
        text += f"• <code>{name}</code> — 💰 {u.balance}\n"

    text += "\n🔎 Отправьте Telegram ID, @username или Roblox ник для поиска"
    await message.answer(text, parse_mode="HTML", reply_markup=admin_users_menu_kb())


@router.message(~StateFilter(GiveMoneyState.waiting_for_amount), F.text == "👥 Пользователи")
async def admin_users_entry(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.set_state(AdminUsersState.searching)
    await _send_users_list(message)


@router.message(StateFilter(AdminUsersState.searching), F.text == "🔁 Обновить список")
async def admin_users_list(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await _send_users_list(message)


@router.message(StateFilter(AdminUsersState.searching), F.text == "↩️ Назад")
async def admin_users_back(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb(),
    )


# -------- Поиск пользователя --------
@router.message(
    StateFilter(AdminUsersState.searching),
    F.text,
    ~F.text.in_({"👥 Пользователи", "🔁 Обновить список", "↩️ Назад", "↩️ В меню"}),
)
async def admin_search_user(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return  # <--- заменили raise SkipHandler()

    query = message.text.strip().lstrip("@")
    if not query:
        return await message.reply(
            "Введите запрос для поиска",
            reply_markup=admin_users_menu_kb(),
        )

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
        return await message.reply(
            "❌ Пользователь не найден",
            reply_markup=admin_users_menu_kb(),
        )

    tg_username = f"@{user.tg_username}" if user.tg_username else "—"
    roblox_username = user.username or "—"
    roblox_id = user.roblox_id or "—"
    created_at = (
        user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"
    )

    title_info = None
    if user.tg_id:
        title_info = await get_user_titles_by_tg_id(user.tg_id)
    titles_line = "—"
    selected_title_line = "—"
    if title_info:
        titles_line = ", ".join(title_info.titles) if title_info.titles else "—"
        selected_title_line = title_info.selected_title or "—"

    text = (
        f"<b>👤 Пользователь найден</b>\n"
        f"TG: {tg_username}\n"
        f"TG ID: <code>{user.tg_id}</code>\n"
        f"Roblox: <code>{roblox_username}</code>\n"
        f"Roblox ID: <code>{roblox_id}</code>\n"
        f"Баланс: 💰 {user.balance}\n"
        f"Титулы: {titles_line}\n"
        f"Выбранный титул: {selected_title_line}\n"
        f"Дата регистрации: {created_at}\n"
    )

    await message.reply(
        text,
        parse_mode="HTML",
        reply_markup=user_card_kb(user.tg_id, user.is_blocked),
    )


# -------- Управление пользователем: блок/разблок/выдача -------
@router.callback_query(
    F.data.startswith("give_money")
    | F.data.startswith("remove_money")
    | F.data.startswith("block_user")
    | F.data.startswith("unblock_user")
    | F.data.startswith("give_title")
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
        await state.update_data(target_user_id=user_id)
        await state.set_state(GiveMoneyState.waiting_for_amount)
        return

    if action == "remove_money":
        await call.message.answer(
            f"Введите сумму удержания для пользователя <code>{user_id}</code>:",
            parse_mode="HTML",
        )
        await state.update_data(target_user_id=user_id)
        await state.set_state(RemoveMoneyState.waiting_for_amount)
        return

    if action == "give_title":
        await call.message.answer(
            f"Введите текст титула для пользователя <code>{user_id}</code>:",
            parse_mode="HTML",
        )
        await state.update_data(target_user_id=user_id)
        await state.set_state(GiveTitleState.waiting_for_title)
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
            return

        if action == "unblock_user":
            user.is_blocked = False
            await session.commit()
            await call.bot.send_message(user_id, "✅ Ваш доступ восстановлен.")
            await call.message.edit_text("✅ Пользователь разблокирован")
            return


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

    data = await state.get_data()
    user_id = data.get("target_user_id")
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

    if "target_user_id" in data:
        data.pop("target_user_id")
        await state.set_data(data)

    await state.clear()


@router.message(StateFilter(GiveTitleState.waiting_for_title))
async def process_give_title(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    title_text = (message.text or "").strip()
    if not title_text:
        return await message.reply("❌ Титул не может быть пустым")
    if len(title_text) > 255:
        return await message.reply("❌ Титул должен быть короче 255 символов")

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        return await message.reply("Ошибка: пользователь не выбран")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        titles = normalize_titles(user.titles)
        titles = [t for t in titles if t != title_text]
        titles.append(title_text)
        user.titles = titles
        if not user.selected_title:
            user.selected_title = title_text
        await session.commit()

    await message.reply(
        (
            f"✅ Титул <b>{title_text}</b> добавлен пользователю "
            f"<code>{target_user_id}</code>"
        ),
        parse_mode="HTML",
    )

    try:
        await message.bot.send_message(
            target_user_id,
            f"🏅 Вам присвоен новый титул: <b>{title_text}</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не удалось уведомить пользователя %s о новом титуле", target_user_id)

    await state.clear()


@router.message(StateFilter(RemoveMoneyState.waiting_for_amount))
async def process_remove_amount(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    try:
        amount = int(message.text)
        if amount <= 0:
            return await message.reply("❌ Введите сумму больше 0")
    except ValueError:
        return await message.reply("❌ Нужно число")

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        return await message.reply("Ошибка: ID пользователя потерян")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        if user.balance - amount < 0:
            return await message.reply(
                "❌ Нельзя удержать больше, чем есть на балансе пользователя"
            )

    await state.update_data(remove_amount=amount)
    await state.set_state(RemoveMoneyState.waiting_for_reason)
    await message.reply("Введите причину удержания:")


@router.message(StateFilter(RemoveMoneyState.waiting_for_reason))
async def process_remove_reason(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    if not await is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    remove_amount = data.get("remove_amount")
    if not target_user_id or not remove_amount:
        await state.clear()
        return await message.reply("Ошибка: данные удержания потеряны")

    reason = message.text.strip()
    if not reason:
        return await message.reply("❌ Причина не может быть пустой")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == target_user_id))
        if not user:
            await state.clear()
            return await message.reply("⛔ Пользователь не найден")

        if user.balance - remove_amount < 0:
            await state.clear()
            return await message.reply(
                "❌ Баланс пользователя изменился, удержание невозможно"
            )

        user.balance -= remove_amount
        await session.commit()

    logger.info(
        "Admin %s removed %s coins from user %s for reason: %s",
        message.from_user.id,
        remove_amount,
        target_user_id,
        reason,
    )

    try:
        await message.bot.send_message(
            target_user_id,
            (
                "⚠️ С вашего баланса удержано "
                f"<b>{remove_amount}</b> монет.\nПричина: {reason}"
            ),
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Не удалось отправить сообщение пользователю %s", target_user_id)

    await message.reply(
        (
            f"✅ Удержано <b>{remove_amount}</b> монет у пользователя "
            f"<code>{target_user_id}</code>.\nПричина: {reason}"
        ),
        parse_mode="HTML",
    )

    await state.clear()
