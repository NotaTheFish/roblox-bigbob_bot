from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.db import SessionLocal, User, Admin
from bot.main_core import bot

# Проверка админа
def is_admin(uid: int) -> bool:
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())


# --- клавиатуры ---

def user_card_kb(user_id, is_blocked):
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(InlineKeyboardButton("➕ Выдать валюту", callback_data=f"give_money:{user_id}"))

    if is_blocked:
        kb.add(InlineKeyboardButton("✅ Разблокировать", callback_data=f"unblock_user:{user_id}"))
    else:
        kb.add(InlineKeyboardButton("🚫 Заблокировать", callback_data=f"block_user:{user_id}"))

    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_users"))
    return kb


# --- /admin_users ---

async def admin_users_list(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Нет доступа", show_alert=True)

    with SessionLocal() as s:
        users = s.query(User).order_by(User.balance.desc()).limit(50).all()

    if not users:
        return await call.message.edit_text("Пользователей пока нет.")

    text = "👥 <b>ТОП 50 пользователей</b> по балансу:\n\n"
    for u in users:
        name = u.tg_username or u.username or f"ID {u.tg_id}"
        text += f"• <code>{name}</code> — 💰 {u.balance}\n"

    text += "\n🔎 Отправьте Telegram ID, @username или Roblox ник для поиска"

    await call.message.edit_text(text)


# --- поиск пользователя ---

async def admin_search_user(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    query = message.text.strip().lstrip("@")

    with SessionLocal() as s:
        user = (
            s.query(User)
            .filter(
                (User.tg_id == query) |
                (User.tg_username == query) |
                (User.username == query)
            )
            .first()
        )

    if not user:
        return await message.reply("❌ Пользователь не найден")

    text = (
        f"<b>👤 Пользователь найден</b>\n"
        f"TG: @{user.tg_username}\n"
        f"TG ID: <code>{user.tg_id}</code>\n"
        f"Roblox: <code>{user.username}</code>\n"
        f"Roblox ID: <code>{user.roblox_id}</code>\n"
        f"Баланс: 💰 {user.balance}\n"
        f"Дата регистрации: {user.created_at}\n"
    )

    await message.reply(text, reply_markup=user_card_kb(user.tg_id, user.is_blocked))


# --- обработка действий admin/user management ---

from bot.states.admin_states import GiveMoneyState

async def user_management_actions(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    action, user_id = call.data.split(":")
    user_id = int(user_id)

    if action == "give_money":
        await call.message.answer(
            f"Введите сумму для пользователя <code>{user_id}</code>:",
            parse_mode="HTML"
        )
        call.bot.data["give_money_target"] = user_id
        return await GiveMoneyState.waiting_for_amount.set()

    elif action == "block_user":
        with SessionLocal() as s:
            user = s.query(User).filter_by(tg_id=user_id).first()
            if not user:
                return await call.answer("Пользователь не найден", show_alert=True)
            user.is_blocked = True
            s.commit()

        await call.answer("🚫 Пользователь заблокирован", show_alert=True)
        await bot.send_message(user_id, "⛔ Ваш доступ к боту заблокирован администратором.")
        return await call.message.edit_text("✅ Пользователь заблокирован")

    elif action == "unblock_user":
        with SessionLocal() as s:
            user = s.query(User).filter_by(tg_id=user_id).first()
            if not user:
                return await call.answer("Пользователь не найден", show_alert=True)
            user.is_blocked = False
            s.commit()

        await call.answer("✅ Пользователь разблокирован", show_alert=True)
        await bot.send_message(user_id, "✅ Ваш доступ к боту восстановлен.")
        return await call.message.edit_text("✅ Пользователь разблокирован")


# --- Выдача валюты ---

from aiogram.dispatcher import FSMContext
from bot.utils.achievement_checker import check_achievements

async def process_money_amount(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ Нет доступа")

    try:
        amount = int(message.text)
        if amount <= 0 or amount > 1_000_000:
            return await message.reply("❌ Введите сумму от 1 до 1,000,000")
    except:
        return await message.reply("❌ Нужно число")

    user_id = message.bot.data.get("give_money_target")

    if not user_id:
        await state.finish()
        return await message.reply("Ошибка: ID пользователя потерян")

    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=user_id).first()
        if not user:
            await state.finish()
            return await message.reply("⛔ Пользователь не найден")

        user.balance += amount
        s.commit()
        check_achievements(user)

    await message.reply(
        f"✅ Выдали <b>{amount}</b> монет пользователю <code>{user_id}</code>",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(user_id, f"🎁 Вам выдано <b>{amount}</b> монет администратором!")
    except:
        pass

    await state.finish()


# --- регистрация ---

def register_admin_users(dp: Dispatcher):
    dp.register_callback_query_handler(admin_users_list, lambda c: c.data == "admin_users")
    dp.register_message_handler(admin_search_user, content_types=["text"])
    dp.register_callback_query_handler(
        user_management_actions,
        lambda c: c.data.startswith("give_money") or c.data.startswith("block_user") or c.data.startswith("unblock_user")
    )
    dp.register_message_handler(process_money_amount, state=GiveMoneyState.waiting_for_amount)

