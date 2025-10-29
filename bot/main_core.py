# bot/main_core.py
# aiogram v2.25.x

import random
import asyncio
import concurrent.futures
import requests
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ParseMode, CallbackQuery
)

from bot.config import TOKEN
from bot.db import SessionLocal, User, Server

# ------------------------------------------------
#  Основные настройки
# ------------------------------------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

ADMIN_IDS = [5813380332, 1748138420]
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# user_states хранит текущий экран пользователя
user_states: Dict[int, Dict[str, Any]] = {}

# ------------------------------------------------
#  Roblox API: получение описания профиля
# ------------------------------------------------
HTTP_TIMEOUT = 8

def _blocking_fetch_user_id(username: str) -> Optional[int]:
    """Ищет Roblox ID по нику"""
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("data"):
        return None
    return data["data"][0].get("id")

def _blocking_fetch_description(user_id: int) -> Optional[str]:
    """Получает описание профиля Roblox"""
    url = f"https://users.roblox.com/v1/users/{user_id}"
    r = requests.get(url, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json().get("description")

async def fetch_roblox_description(username: str) -> Optional[str]:
    """Асинхронная обёртка"""
    loop = asyncio.get_event_loop()
    user_id = await loop.run_in_executor(_executor, _blocking_fetch_user_id, username)
    if not user_id:
        return None
    return await loop.run_in_executor(_executor, _blocking_fetch_description, user_id)

# ------------------------------------------------
#  Клавиатуры
# ------------------------------------------------
def kb_main() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("⚡ Играть"))
    kb.row(KeyboardButton("💼 Аккаунт"), KeyboardButton("💰 Донат-меню"))
    kb.row(KeyboardButton("🏠 Главное меню"))
    kb.row(KeyboardButton("👑 Админ-панель"))
    return kb

def kb_back() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🔙 Назад"))
    kb.add(KeyboardButton("🏠 Главное меню"))
    return kb

def kb_account() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("💰 Баланс"), KeyboardButton("💸 Пополнить баланс"))
    kb.row(KeyboardButton("🎁 Активировать промокод"))
    kb.row(KeyboardButton("👥 Реферальная программа"), KeyboardButton("🏆 Топ игроков"))
    kb.row(KeyboardButton("🔙 Назад"), KeyboardButton("🏠 Главное меню"))
    return kb

def kb_shop() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("💸 Купить кеш"))
    kb.row(KeyboardButton("🛡 Купить привилегию"), KeyboardButton("🎒 Купить предмет"))
    kb.row(KeyboardButton("🔙 Назад"), KeyboardButton("🏠 Главное меню"))
    return kb

def kb_admin_main() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👥 Пользователи"), KeyboardButton("🖥 Сервера"))
    kb.row(KeyboardButton("🎟 Промокоды"), KeyboardButton("🛒 Магазин"))
    kb.row(KeyboardButton("↩️ Выйти в режим пользователя"))
    kb.row(KeyboardButton("🏠 Главное меню"))
    return kb

# ------------------------------------------------
#  Утилиты
# ------------------------------------------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def ensure_user_in_db(user_id: int) -> User:
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        user = User(telegram_id=user_id, verified=False)
        session.add(user)
        session.commit()
    session.close()
    return user

async def show_main_menu(chat_id: int):
    user_states[chat_id] = {"screen": "main"}
    await bot.send_message(chat_id, "🏠 Главное меню", reply_markup=kb_main())

# ------------------------------------------------
#  /start — приветствие
# ------------------------------------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    ensure_user_in_db(message.from_user.id)
    await message.answer(
        "👋 Привет! Я помогу тебе попасть на приватные сервера Roblox.\n"
        "Для начала пройди верификацию — нажми /verify",
        reply_markup=kb_back()
    )

# ------------------------------------------------
#  /verify — начало верификации Roblox
# ------------------------------------------------
@dp.message_handler(commands=['verify'])
async def cmd_verify(message: types.Message):
    ensure_user_in_db(message.from_user.id)
    user_states[message.from_user.id] = {"screen": "await_nick"}
    await message.answer("✍️ Напиши свой ник Roblox:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "await_nick")
async def handle_nick(message: types.Message):
    if message.text in ("🏠 Главное меню", "🔙 Назад"):
        return await show_main_menu(message.chat.id)

    nick = message.text.strip()
    user_states[message.from_user.id] = {"screen": "confirm_nick", "nick": nick}

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Да ✅", callback_data="nick_yes"))
    kb.add(InlineKeyboardButton("Нет ❌", callback_data="nick_no"))

    await message.answer(f"Проверим — это твой ник в Roblox?\n\n<b>{nick}</b>", 
                         parse_mode=ParseMode.HTML, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ("nick_yes", "nick_no"))
async def cb_confirm_nick(call: CallbackQuery):
    uid = call.from_user.id
    if call.data == "nick_no":
        user_states[uid] = {"screen": "await_nick"}
        await call.message.edit_text("Окей, введи ник ещё раз ✍️")
        return await call.answer()

    nick = user_states[uid]["nick"]
    code = str(random.randint(10000, 99999))

    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=uid).first()
    if user:
        user.roblox_user = nick
        user.code = code
        user.verified = False
        session.commit()
    session.close()

    await call.message.edit_text(
        f"✅ Отлично!\nДобавь этот код в описание Roblox-профиля:\n\n<code>{code}</code>\n\n"
        "После этого нажми /check — бот проверит твой аккаунт.",
        parse_mode=ParseMode.HTML
    )
    await call.answer()

# ------------------------------------------------
#  /check — проверка описания Roblox профиля
# ------------------------------------------------
@dp.message_handler(commands=['check'])
async def cmd_check(message: types.Message):
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

    if not user or not user.roblox_user:
        session.close()
        return await message.answer("❌ Сначала сделай /verify и укажи ник Roblox.")

    code = user.code
    if not code:
        session.close()
        return await message.answer("❌ Код не найден. Пройди /verify заново.")

    msg = await message.answer("🔍 Проверяю Roblox профиль...")

    try:
        description = await fetch_roblox_description(user.roblox_user.strip())
    except Exception:
        session.close()
        return await msg.edit_text("⚠️ Ошибка при запросе Roblox API. Попробуй позже.")

    if not description:
        session.close()
        return await msg.edit_text("❌ Профиль не найден или описание пустое.")

    if code.lower() in description.lower():
        user.verified = True
        session.commit()
        session.close()
        await msg.edit_text("✅ Аккаунт подтверждён! Добро пожаловать.")
        await show_main_menu(message.chat.id)
    else:
        session.close()
        await msg.edit_text(
            "❌ Код не найден в описании профиля.\n"
            "Проверь, что добавил его и попробуй ещё раз."
        )

# ------------------------------------------------
#  Меню: Играть / Аккаунт / Донат
# ------------------------------------------------
@dp.message_handler(lambda m: m.text == "⚡ Играть")
async def menu_play(message: types.Message):
    session = SessionLocal()
    servers = session.query(Server).order_by(Server.number.asc()).all()
    session.close()

    if not servers:
        return await message.answer("❌ Сервера пока не добавлены.", reply_markup=kb_main())

    kb = InlineKeyboardMarkup()
    for s in servers:
        if s.link:
            kb.add(InlineKeyboardButton(f"Сервер {s.number}", url=s.link))
        else:
            kb.add(InlineKeyboardButton(f"Сервер {s.number} ❌", callback_data=f"server_closed:{s.number}"))

    await message.answer("🎮 Выбери сервер:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("server_closed:"))
async def cb_server_closed(call: CallbackQuery):
    number = call.data.split(":")[1]
    await call.answer(f"Сервер {number} закрыт", show_alert=True)

# ------------------------------------------------
#  Меню аккаунта
# ------------------------------------------------
@dp.message_handler(lambda m: m.text == "💼 Аккаунт")
async def menu_account(message: types.Message):
    session = SessionLocal()
    u = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    session.close()

    if not u:
        return await message.answer("Ошибка: аккаунт не найден.", reply_markup=kb_main())

    info = (
        f"👤 Ник: {u.roblox_user or '—'}\n"
        f"💰 Баланс: {u.balance} орешков\n"
        f"💎 Кеш: {u.cash}\n"
        f"🎮 Уровень: {u.level}\n"
        f"⏱ Время в игре: {u.play_time}\n"
        f"👥 Приглашённые: {u.referrals}"
    )
    await message.answer(info, reply_markup=kb_account())

# ------------------------------------------------
#  Меню доната
# ------------------------------------------------
@dp.message_handler(lambda m: m.text == "💰 Донат-меню")
async def menu_donate(message: types.Message):
    await message.answer("💎 Раздел доната в разработке.", reply_markup=kb_shop())

# ------------------------------------------------
#  Админка
# ------------------------------------------------
@dp.message_handler(lambda m: m.text == "👑 Админ-панель")
async def admin_enter(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    await message.answer("👑 Добро пожаловать в админ-панель.", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: m.text == "↩️ Выйти в режим пользователя")
async def leave_admin(message: types.Message):
    await show_main_menu(message.chat.id)

# ------------------------------------------------
#  Навигация: Назад / Главное меню
# ------------------------------------------------
@dp.message_handler(lambda m: m.text in ("🏠 Главное меню", "🔙 Назад"))
async def go_back(message: types.Message):
    await show_main_menu(message.chat.id)
