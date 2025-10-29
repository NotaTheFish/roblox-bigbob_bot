# bot/main_core.py

import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from bot.config import TOKEN
from bot.db import SessionLocal, User

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- Твой код бота без запуска сервера ---

user_states = {}

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    session = SessionLocal()
    user_id = message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()

    if not user:
        user = User(telegram_id=user_id, verified=False)
        session.add(user)
        session.commit()

    await message.answer(
        "👋 Привет! Я помогу тебе войти на приватные сервера Roblox.\n"
        "Используй /verify чтобы подтвердить аккаунт."
    )
    session.close()

@dp.message_handler(commands=['verify'])
async def verify_cmd(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {"step": "await_nick"}
    await message.answer("Напиши свой ник Roblox:")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("step") == "await_nick")
async def handle_nick(message: types.Message):
    user_id = message.from_user.id
    nick = message.text.strip()
    user_states[user_id]["nick"] = nick
    user_states[user_id]["step"] = "confirm_nick"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Да ✅", callback_data="confirm_yes"))
    keyboard.add(types.InlineKeyboardButton("Нет ❌", callback_data="confirm_no"))

    await message.answer(f"Ты уверен, что твой ник '{nick}' верный?", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data in ["confirm_yes", "confirm_no"])
async def process_confirm(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    
    if callback_query.data == "confirm_yes":
        nick = user_states[user_id]["nick"]
        code = str(random.randint(10000, 99999))
        user.roblox_user = nick
        user.code = code
        user.verified = False
        session.commit()

        await bot.send_message(
            user_id,
            f"✅ Твой код подтверждения: `{code}`\nДобавь его в описание Roblox-профиля, потом нажми /check.",
            parse_mode=ParseMode.MARKDOWN
        )
        user_states[user_id]["step"] = "checked"
    else:
        await bot.send_message(user_id, "Окей, напиши свой ник снова:")
        user_states[user_id]["step"] = "await_nick"

    session.close()
    await callback_query.answer()

@dp.message_handler(commands=['check'])
async def check_cmd(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

    if not user or not user.roblox_user:
        await message.answer("❌ Сначала введи /verify и укажи ник")
        session.close()
        return

    # Автоматическая верификация
    user.verified = True
    session.commit()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("1️⃣ Сервер 1", "2️⃣ Сервер 2", "3️⃣ Сервер 3")

    await message.answer("✅ Аккаунт подтверждён!\n🎮 Выбери сервер для входа:", reply_markup=markup)
    session.close()

