import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from config import TOKEN, ADMINS
from db import users

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Команда /start
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    users[user_id] = users.get(user_id, {"verified": False, "roblox_user": None})
    await message.answer("👋 Привет! Я помогу тебе войти на приватные сервера Roblox.\n"
                         "Используй /verify <ник_roblox> чтобы подтвердить аккаунт.")

# Команда /verify
@dp.message_handler(commands=['verify'])
async def verify_cmd(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()

    if not args:
        await message.reply("❌ Укажи ник: `/verify roblox_nick`", parse_mode="Markdown")
        return

    code = str(random.randint(10000, 99999))
    users[user_id] = {"verified": True, "roblox_user": args, "code": code}
    await message.answer(f"✅ Твой код подтверждения: `{code}`\n"
                         "Добавь его в описание Roblox-профиля, потом нажми /check.",
                         parse_mode="Markdown")

# Команда /check
@dp.message_handler(commands=['check'])
async def check_cmd(message: types.Message):
    user = users.get(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала введи /verify <ник>")
        return

    if user["verified"]:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("1️⃣ Сервер 1", "2️⃣ Сервер 2", "3️⃣ Сервер 3")
        await message.answer("🎮 Выбери сервер для входа:", reply_markup=markup)
    else:
        await message.answer("😕 Аккаунт ещё не подтверждён.")

# Обработка выбора сервера
@dp.message_handler(lambda msg: msg.text.startswith("1️⃣") or msg.text.startswith("2️⃣") or msg.text.startswith("3️⃣"))
async def server_choice(message: types.Message):
    server_name = message.text
    await message.answer(f"🚀 Подключаю к {server_name}...\n(в будущем тут будет кнопка перехода в Roblox)")

# Запуск
if __name__ == "__main__":
    from web_server import keep_alive
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
