# bot/main_core.py

import random
import asyncio
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.executor import start_webhook
from bot.config import TOKEN, WEBHOOK_URL
from bot.db import SessionLocal, User, Server, PromoCode, Item

# --- Flask сервер ---
app = Flask(__name__)

# --- Настройки вебхука ---
WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080
WEBHOOK_URL_FULL = WEBHOOK_URL + "/" + TOKEN.split(":")[0]

# --- Телеграм бот ---
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- Хранение временных состояний ---
user_states = {}

# --- Список админов ---
ADMIN_IDS = [5813380332, 1748138420]

# --- Обработчики команд ---
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

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Да ✅", callback_data="confirm_yes"))
    keyboard.add(InlineKeyboardButton("Нет ❌", callback_data="confirm_no"))

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

    user.verified = True
    session.commit()

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Мой аккаунт", "Топ игроков")
    markup.add("Присоединиться к игре", "Войти в режим Админа")
    await message.answer("✅ Аккаунт подтверждён!\nВыбери действие:", reply_markup=markup)
    session.close()

# --- Главное меню ---
@dp.message_handler(lambda msg: msg.text == "Мой аккаунт")
async def my_account(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user or not user.verified:
        await message.answer("❌ Аккаунт не подтверждён")
        session.close()
        return
    info = (f"👤 Ник: {user.roblox_user}\n"
            f"💰 Баланс: {user.balance} орешков\n"
            f"💎 Кеш: {user.cash}\n"
            f"📦 Предметы: {user.items}\n"
            f"🎮 Уровень: {user.level}\n"
            f"⏱ Время в игре: {user.play_time}\n"
            f"👥 Приглашённые: {user.referrals}")
    await message.answer(info)
    session.close()

@dp.message_handler(lambda msg: msg.text == "Топ игроков")
async def top_players(message: types.Message):
    session = SessionLocal()
    top = session.query(User).order_by(User.level.desc()).limit(15).all()
    text = "🏆 Топ 15 игроков:\n"
    for u in top:
        text += f"{u.roblox_user} — уровень {u.level}\n"
    await message.answer(text)
    session.close()

@dp.message_handler(lambda msg: msg.text == "Присоединиться к игре")
async def join_game(message: types.Message):
    session = SessionLocal()
    servers = session.query(Server).order_by(Server.number.asc()).all()
    if not servers:
        await message.answer("❌ Сервера не добавлены")
        session.close()
        return

    keyboard = InlineKeyboardMarkup()
    for s in servers:
        if s.link:
            keyboard.add(InlineKeyboardButton(f"Сервер {s.number}", url=s.link))
        else:
            keyboard.add(InlineKeyboardButton(f"Сервер {s.number} ❌", callback_data=f"server_closed_{s.number}"))
    await message.answer("Выбери сервер:", reply_markup=keyboard)
    session.close()

@dp.callback_query_handler(lambda c: c.data.startswith("server_closed_"))
async def server_closed(callback_query: types.CallbackQuery):
    number = callback_query.data.split("_")[-1]
    await callback_query.answer(f"Сервер {number} закрыт")

# --- Админский режим ---
@dp.message_handler(lambda msg: msg.text == "Войти в режим Админа")
async def enter_admin_mode(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ты не Админ")
        return
    user_states[message.from_user.id] = {"step": "admin_main"}
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Пользователи", callback_data="admin_users"),
        InlineKeyboardButton("Сервера", callback_data="admin_servers")
    )
    keyboard.add(
        InlineKeyboardButton("Промокоды", callback_data="admin_promos"),
        InlineKeyboardButton("Магазин", callback_data="admin_shop")
    )
    await message.answer("✅ Режим Админа активирован:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("admin_"))
async def admin_menu(callback_query: types.CallbackQuery):
    session = SessionLocal()
    user_id = callback_query.from_user.id

    if callback_query.data == "admin_users":
        users = session.query(User).order_by(User.level.desc()).limit(20).all()
        text = "👥 Пользователи:\n"
        for u in users:
            text += f"{u.roblox_user} (Telegram: {u.telegram_id})\n"
        await callback_query.message.answer(text)
    
    elif callback_query.data == "admin_servers":
        servers = session.query(Server).order_by(Server.number.asc()).all()
        text = "🎮 Сервера:\n"
        for s in servers:
            text += f"Сервер {s.number} — {s.link if s.link else 'закрыт'}\n"
        await callback_query.message.answer(text)
    
    elif callback_query.data == "admin_promos":
        promos = session.query(PromoCode).all()
        text = "💎 Промокоды:\n"
        for p in promos:
            text += f"{p.code} — {p.type} {p.value}\n"
        await callback_query.message.answer(text)
    
    elif callback_query.data == "admin_shop":
        items = session.query(Item).all()
        text = "🛒 Магазин:\n"
        for i in items:
            text += f"{i.name} — {i.price} орешков\n"
        await callback_query.message.answer(text)
    
    session.close()
    await callback_query.answer()

# --- Flask endpoint для сервера Roblox ---
@app.route('/update_player', methods=["POST"])
def update_player():
    data = request.json
    try:
        session = SessionLocal()
        user = session.query(User).filter_by(roblox_user=data["username"]).first()
        if user is None:
            # Автоматическое создание нового пользователя
            user = User(
                telegram_id=None,
                roblox_user=data["username"],
                verified=False,
                level=data.get("level", 0),
                cash=data.get("cash", 0),
                items=data.get("items", ""),
                play_time=data.get("play_time", 0),
                balance=0,
                referrals=0
            )
            session.add(user)
            session.commit()
        
        else:
            user.level = data.get("level", user.level)
            user.cash = data.get("cash", user.cash)
            user.items = data.get("items", user.items)
            user.play_time = data.get("play_time", user.play_time)
            session.commit()
        
        session.close()
        return {"status": "ok"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

# --- Webhook обработчик ---
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    update = types.Update.to_object(request.get_json(force=True))
    asyncio.create_task(dp.process_update(update))
    return "OK", 200

# --- Webhook запуск ---
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL_FULL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == "__main__":
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
