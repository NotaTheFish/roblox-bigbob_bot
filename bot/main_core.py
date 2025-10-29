# bot/main_core.py
# aiogram==2.25.1

import asyncio
import random
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ParseMode, CallbackQuery
)

from sqlalchemy import text

# --- Конфиг ---
from bot.config import TOKEN
try:
    from bot.config import ADMIN_ROOT_IDS
except Exception:
    ADMIN_ROOT_IDS = []
try:
    from bot.config import ADMIN_LOGIN_PASSWORD
except Exception:
    ADMIN_LOGIN_PASSWORD = "CHANGE_ME_NOW"

from bot.db import SessionLocal, User, Server, PromoCode, Item

# --- Инициализация бота ---
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- Состояния ---
user_states: Dict[int, Dict[str, Any]] = {}

# -----------------------
# Таблица админов (простая ACL)
# -----------------------
def ensure_admins_table():
    sess = SessionLocal()
    try:
        sess.execute(text("""
            CREATE TABLE IF NOT EXISTS admins (
                telegram_id INTEGER PRIMARY KEY
            )
        """))
        sess.commit()
    finally:
        sess.close()

def is_admin(user_id: int) -> bool:
    sess = SessionLocal()
    try:
        row = sess.execute(text("SELECT telegram_id FROM admins WHERE telegram_id=:tid"), {"tid": user_id}).fetchone()
        return row is not None
    finally:
        sess.close()

def add_admin(user_id: int):
    sess = SessionLocal()
    try:
        sess.execute(text("INSERT OR IGNORE INTO admins(telegram_id) VALUES(:tid)"), {"tid": user_id})
        sess.commit()
    finally:
        sess.close()

def remove_admin(user_id: int):
    sess = SessionLocal()
    try:
        sess.execute(text("DELETE FROM admins WHERE telegram_id=:tid"), {"tid": user_id})
        sess.commit()
    finally:
        sess.close()

ensure_admins_table()

async def notify_roots(msg: str):
    if not ADMIN_ROOT_IDS:
        return
    for rid in ADMIN_ROOT_IDS:
        try:
            await bot.send_message(rid, f"📣 <b>LOG</b>\n{msg}", parse_mode=ParseMode.HTML)
        except Exception:
            pass

# -----------------------
# Верификация Roblox (реальная)
# -----------------------
import requests, concurrent.futures
HTTP_TIMEOUT = 8
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def _blocking_fetch_user_id(username: str) -> Optional[int]:
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("data"):
        return None
    return data["data"][0].get("id")

def _blocking_fetch_description(user_id: int) -> Optional[str]:
    url = f"https://users.roblox.com/v1/users/{user_id}"
    r = requests.get(url, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json().get("description")

async def fetch_roblox_description(username: str) -> Optional[str]:
    loop = asyncio.get_event_loop()
    user_id = await loop.run_in_executor(_executor, _blocking_fetch_user_id, username)
    if not user_id:
        return None
    desc = await loop.run_in_executor(_executor, _blocking_fetch_description, user_id)
    return desc

# -----------------------
# Клавиатуры
# -----------------------
def kb_main() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("⚡ Играть"))
    kb.row(KeyboardButton("💼 Аккаунт"), KeyboardButton("💰 Донат-меню"))
    kb.row(KeyboardButton("👑 Админ-панель"))
    return kb

def kb_back() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🔙 Назад"))
    return kb

def kb_account() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("💰 Баланс"), KeyboardButton("💸 Пополнить баланс"))
    kb.row(KeyboardButton("🎁 Активировать промокод"))
    kb.row(KeyboardButton("👥 Реферальная программа"), KeyboardButton("🏆 Топ игроков"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

def kb_shop() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("💸 Купить кеш"))
    kb.row(KeyboardButton("🛡 Купить привилегию"), KeyboardButton("🎒 Купить предмет"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

def kb_admin_main() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👥 Пользователи"), KeyboardButton("🖥 Сервера"))
    kb.row(KeyboardButton("🎟 Промокоды"), KeyboardButton("🛒 Магазин"))
    kb.row(KeyboardButton("⚙ Настройки"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

def kb_admin_servers() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Добавить сервер"), KeyboardButton("➖ Удалить последний сервер"))
    kb.row(KeyboardButton("🔗 Управление ссылками серверов"))
    kb.row(KeyboardButton("📝 Сообщение закрытого сервера"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

def kb_admin_settings() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📃 Список администраторов"))
    kb.row(KeyboardButton("➕ Выдать администратора (ID)"))
    kb.row(KeyboardButton("➖ Удалить администратора (ID)"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

def kb_admin_promos() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Создать промокод"))
    kb.row(KeyboardButton("📋 Список (все)"), KeyboardButton("✅ Список (активные)"))
    kb.row(KeyboardButton("⛔ Список (неактивные)"), KeyboardButton("🗑 Удалить промокод"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

def kb_admin_store() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Добавить товар"), KeyboardButton("🗑 Удалить товар"))
    kb.row(KeyboardButton("📦 Список товаров"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

# -----------------------
# Утилиты
# -----------------------
def ensure_user_in_db(user_id: int) -> User:
    sess = SessionLocal()
    try:
        u = sess.query(User).filter_by(telegram_id=user_id).first()
        if not u:
            u = User(telegram_id=user_id, verified=False)
            sess.add(u)
            sess.commit()
        return u
    finally:
        sess.close()

async def show_main_menu(chat_id: int):
    user_states[chat_id] = {"screen": "main"}
    await bot.send_message(chat_id, "🏠 Главное меню", reply_markup=kb_main())

# -----------------------
# Команды: /start /verify /check
# -----------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    ensure_user_in_db(message.from_user.id)
    user_states[message.from_user.id] = {"screen": "main"}
    await message.answer(
        "👋 Привет! Я помогу тебе войти на приватные сервера Roblox.\n"
        "Используй /verify для подтверждения аккаунта и /check для проверки.",
        reply_markup=kb_main()
    )

@dp.message_handler(commands=['verify'])
async def cmd_verify(message: types.Message):
    ensure_user_in_db(message.from_user.id)
    user_states[message.from_user.id] = {"screen": "await_nick"}
    await message.answer("✍️ Напиши свой ник Roblox:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "await_nick")
async def handle_nick(message: types.Message):
    if message.text == "🔙 Назад":
        return await show_main_menu(message.chat.id)

    nick = message.text.strip()
    user_states[message.from_user.id] = {"screen": "confirm_nick", "nick": nick}
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Да ✅", callback_data="nick_yes"),
           InlineKeyboardButton("Нет ❌", callback_data="nick_no"))
    await message.answer(
        f"Проверим: это твой ник в Roblox?\n\n<b>{nick}</b>",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query_handler(lambda c: c.data in ("nick_yes", "nick_no"))
async def cb_confirm_nick(call: CallbackQuery):
    uid = call.from_user.id
    st = user_states.get(uid, {})
    if call.data == "nick_no":
        user_states[uid] = {"screen": "await_nick"}
        await call.message.edit_text("Окей, введи ник ещё раз ✍️")
        return await call.answer()

    # nick_yes
    nick = st.get("nick")
    code = str(random.randint(10000, 99999))
    sess = SessionLocal()
    try:
        u = sess.query(User).filter_by(telegram_id=uid).first()
        if u:
            u.roblox_user = nick
            # поле code должно быть в модели; если нет — добавь в БД
            setattr(u, "code", code)
            u.verified = False
            sess.commit()
    finally:
        sess.close()

    await call.message.edit_text(
        "✅ Сгенерирован код подтверждения.\n"
        f"Вставь в описание профиля Roblox этот код:\n\n<code>{code}</code>\n\n"
        "Затем нажми /check.",
        parse_mode=ParseMode.HTML
    )
    user_states[uid] = {"screen": "main"}
    await call.answer()

@dp.message_handler(commands=['check'])
async def cmd_check(message: types.Message):
    sess = SessionLocal()
    try:
        u = sess.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not u or not u.roblox_user:
            return await message.answer("❌ Сначала /verify и укажи ник.")

        user_code = getattr(u, "code", None)
        if not user_code:
            return await message.answer("❌ Код подтверждения не найден. Сначала сделай /verify.")

        status_msg = await message.answer("🔍 Проверяю Roblox профиль...")
        try:
            desc = await fetch_roblox_description(u.roblox_user.strip())
        except requests.HTTPError:
            return await status_msg.edit_text("⚠️ Roblox API ответил ошибкой. Попробуй позже.")
        except requests.RequestException:
            return await status_msg.edit_text("⚠️ Нет связи с Roblox API. Попробуй ещё раз.")

        if desc is None:
            return await status_msg.edit_text("❌ Профиль не найден или недоступен.")

        if not desc.strip():
            return await status_msg.edit_text(
                "⚠️ Профиль закрыт или пустое описание. Открой профиль и добавь код, затем /check."
            )

        hay = re.sub(r"\s+", "", desc).lower()
        needle = re.sub(r"\s+", "", str(user_code)).lower()
        if needle in hay:
            u.verified = True
            sess.commit()
            await status_msg.edit_text("✅ Аккаунт подтверждён! Доступ открыт.")
            user_states[message.from_user.id] = {"screen": "main"}
            await message.answer("🏠 Главное меню", reply_markup=kb_main())
        else:
            await status_msg.edit_text(
                "❌ Код не найден в описании.\n"
                "Проверь правильность и видимость, затем сделай /check ещё раз."
            )
    finally:
        sess.close()

# -----------------------
# Пользовательское меню
# -----------------------
@dp.message_handler(lambda m: m.text == "⚡ Играть")
async def menu_play(message: types.Message):
    sess = SessionLocal()
    try:
        servers = sess.query(Server).order_by(Server.number.asc()).all()
        if not servers:
            return await message.answer("❌ Сервера ещё не добавлены.", reply_markup=kb_main())
        kb = InlineKeyboardMarkup()
        for s in servers:
            if s.link:
                kb.add(InlineKeyboardButton(f"Сервер {s.number}", url=s.link))
            else:
                kb.add(InlineKeyboardButton(f"Сервер {s.number} ❌", callback_data=f"server_closed:{s.number}"))
        await message.answer("🎮 Выбери сервер:", reply_markup=kb)
    finally:
        sess.close()

@dp.callback_query_handler(lambda c: c.data.startswith("server_closed:"))
async def cb_server_closed(call: CallbackQuery):
    num = call.data.split(":")[1]
    await call.answer(f"Сервер {num} закрыт", show_alert=True)

@dp.message_handler(lambda m: m.text == "💼 Аккаунт")
async def menu_account(message: types.Message):
    user_states[message.from_user.id] = {"screen": "account"}
    sess = SessionLocal()
    try:
        u = sess.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not u:
            ensure_user_in_db(message.from_user.id)
            return await message.answer("Профиль создан. Нажми ещё раз «💼 Аккаунт».", reply_markup=kb_account())
        info = (
            f"👤 Ник: {u.roblox_user or '—'}\n"
            f"🎮 Уровень: {u.level}\n"
            f"💎 Кеш: {u.cash}\n"
            f"📦 Предметы: {u.items or '—'}\n"
            f"⏱ Время в игре: {u.play_time} мин\n"
            f"👥 Приглашённые: {u.referrals}\n"
            f"💰 Баланс бота: {u.balance} орешков"
        )
        await message.answer(info, reply_markup=kb_account())
    finally:
        sess.close()

@dp.message_handler(lambda m: m.text == "💰 Баланс")
async def account_balance(message: types.Message):
    sess = SessionLocal()
    try:
        u = sess.query(User).filter_by(telegram_id=message.from_user.id).first()
        bal = u.balance if u else 0
    finally:
        sess.close()
    await message.answer(f"💰 Твой баланс: <b>{bal}</b> орешков.", parse_mode=ParseMode.HTML, reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "💸 Пополнить баланс")
async def account_topup(message: types.Message):
    await message.answer("💳 Пополнение в разработке (EUR/UAH/RUB/crypto).", reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "🎁 Активировать промокод")
async def account_promocode(message: types.Message):
    user_states[message.from_user.id] = {"screen": "await_promocode"}
    await message.answer("Введи промокод:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "await_promocode")
async def handle_promocode(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "account"}
        return await message.answer("Меню аккаунта:", reply_markup=kb_account())

    code = message.text.strip()
    sess = SessionLocal()
    try:
        promo = sess.query(PromoCode).filter_by(code=code).first()
        u = sess.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not promo or (promo.max_uses is not None and promo.uses >= promo.max_uses) \
           or (promo.expires_at and datetime.utcnow() > promo.expires_at):
            return await message.answer("❌ Промокод недействителен.", reply_markup=kb_account())

        # применение
        if promo.promo_type == "value":
            u.balance += promo.value or 0
        elif promo.promo_type == "cash":
            u.cash += promo.value or 0
        elif promo.promo_type == "item":
            # просто добавим в строку предметов
            name = f"ITEM_{promo.value or 0}"
            u.items = (u.items + f",{name}") if u.items else name
        elif promo.promo_type == "discount":
            # скидка как орешки — простая модель; можно хранить отдельно
            u.balance += promo.value or 0
        elif promo.promo_type == "admin_access":
            add_admin(u.telegram_id)

        promo.uses += 1
        sess.commit()
    finally:
        sess.close()

    user_states[message.from_user.id] = {"screen": "account"}
    await message.answer("✅ Промокод применён!", reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "👥 Реферальная программа")
async def account_ref(message: types.Message):
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"Приглашай друзей!\n🔗 Твоя ссылка: {ref_link}", reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "🏆 Топ игроков")
async def account_top(message: types.Message):
    sess = SessionLocal()
    try:
        top = sess.query(User).order_by(User.level.desc()).limit(15).all()
    finally:
        sess.close()
    text = "🏆 Топ 15 игроков:\n" + "\n".join(
        f"• {u.roblox_user or '—'} — уровень {u.level}" for u in top
    )
    await message.answer(text, reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "💰 Донат-меню")
async def menu_shop(message: types.Message):
    user_states[message.from_user.id] = {"screen": "shop"}
    await message.answer("🛒 Магазин:", reply_markup=kb_shop())

# Покупки пользователем
def list_items_by_category(category: str) -> List[Item]:
    sess = SessionLocal()
    try:
        return sess.query(Item).filter_by(category=category, is_active=True).order_by(Item.id.asc()).all()
    finally:
        sess.close()

@dp.message_handler(lambda m: m.text in ("💸 Купить кеш", "🛡 Купить привилегию", "🎒 Купить предмет"))
async def shop_items(message: types.Message):
    category_map = {
        "💸 Купить кеш": "cash",
        "🛡 Купить привилегию": "privilege",
        "🎒 Купить предмет": "item",
    }
    cat = category_map[message.text]
    items = list_items_by_category(cat)
    if not items:
        return await message.answer("Пока пусто. Загляни позже.", reply_markup=kb_shop())

    kb = InlineKeyboardMarkup()
    for it in items:
        kb.add(InlineKeyboardButton(f"{it.name} — {it.price}🥜", callback_data=f"buy:{it.id}"))
    await message.answer("Выбери товар:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("buy:"))
async def cb_buy(call: CallbackQuery):
    item_id = int(call.data.split(":")[1])
    sess = SessionLocal()
    try:
        u = sess.query(User).filter_by(telegram_id=call.from_user.id).first()
        it = sess.query(Item).filter_by(id=item_id, is_active=True).first()
        if not u or not it:
            return await call.answer("Товар недоступен.", show_alert=True)
        if u.balance < it.price:
            return await call.answer("Недостаточно орешков.", show_alert=True)

        u.balance -= it.price
        if it.category == "cash":
            # выдернем число из названия, например "Кеш +500"
            m = re.search(r"(\d+)", it.name)
            if m:
                u.cash += int(m.group(1))
        else:
            # добавим в предметы/привилегии
            add = it.name
            u.items = (u.items + f",{add}") if u.items else add

        sess.commit()
    finally:
        sess.close()

    await call.answer("Покупка успешна!", show_alert=True)
    await call.message.edit_reply_markup(None)
    await bot.send_message(call.from_user.id, "✅ Спасибо за покупку!", reply_markup=kb_shop())

# -----------------------
# Кнопка Назад (универсально)
# -----------------------
@dp.message_handler(lambda m: m.text == "🔙 Назад")
async def go_back(message: types.Message):
    screen = user_states.get(message.from_user.id, {}).get("screen", "main")
    if screen in ("account", "shop"):
        return await show_main_menu(message.chat.id)
    if screen.startswith("admin"):
        # если мы в подразделах админки — возвращаем в главное админ-меню
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    await show_main_menu(message.chat.id)

# -----------------------
# Админка: вход
# -----------------------
@dp.message_handler(lambda m: m.text == "👑 Админ-панель")
async def enter_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Нет доступа. Введите /admin_login <пароль> и ждите одобрения.")
    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())

# 2FA вход
@dp.message_handler(commands=["admin_login"])
async def admin_login(message: types.Message):
    args = message.get_args() if hasattr(message, "get_args") else ""
    pwd = (args or "").strip()
    if not pwd:
        return await message.reply("Использование: <code>/admin_login ПАРОЛЬ</code>", parse_mode=ParseMode.HTML)
    if pwd != ADMIN_LOGIN_PASSWORD:
        await notify_roots(f"❌ Неверный пароль админ-входа: {message.from_user.id}")
        return await message.reply("❌ Неверный пароль.")

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve:{message.from_user.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject:{message.from_user.id}")
    )
    cap = f"🛡 Запрос на выдачу админ-прав от @{message.from_user.username or '—'} ({message.from_user.id})"
    for rid in ADMIN_ROOT_IDS:
        try:
            await bot.send_message(rid, cap, reply_markup=kb)
        except Exception:
            pass
    await message.reply("🕓 Запрос отправлен. Ожидайте одобрения.")

@dp.callback_query_handler(lambda c: c.data.startswith("admin_approve:") or c.data.startswith("admin_reject:"))
async def cb_admin_approve(call: CallbackQuery):
    if call.from_user.id not in ADMIN_ROOT_IDS:
        return await call.answer("Нет прав.", show_alert=True)
    target = int(call.data.split(":")[1])
    if call.data.startswith("admin_approve:"):
        add_admin(target)
        await notify_roots(f"✅ Одобрено: {target} получил админ-права.")
        try:
            await bot.send_message(target, "✅ Тебе выданы админ-права. Зайди в «👑 Админ-панель».")
        except Exception:
            pass
        await call.message.edit_text(call.message.text + "\n\n✅ Одобрено.")
    else:
        await notify_roots(f"❌ Отклонено: {target} не получил админ-права.")
        try:
            await bot.send_message(target, "❌ Заявка на админ-права отклонена.")
        except Exception:
            pass
        await call.message.edit_text(call.message.text + "\n\n❌ Отклонено.")
    await call.answer()

# -----------------------
# Админка: Пользователи (заглушка)
# -----------------------
@dp.message_handler(lambda m: m.text == "👥 Пользователи")
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_users"}
    await message.answer("👥 Управление пользователями (скоро расширим).", reply_markup=kb_admin_main())

# -----------------------
# Админка: Сервера
# -----------------------
@dp.message_handler(lambda m: m.text == "🖥 Сервера")
async def admin_servers(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_servers"}
    await message.answer("🖥 Управление серверами:", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "➕ Добавить сервер")
async def admin_add_server(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    sess = SessionLocal()
    try:
        last = sess.query(Server).order_by(Server.number.desc()).first()
        next_num = (last.number + 1) if last else 1
        s = Server(number=next_num, link=None, closed_message="Сервер закрыт")
        sess.add(s)
        sess.commit()
    finally:
        sess.close()
    await notify_roots(f"➕ Админ {message.from_user.id} добавил сервер {next_num}")
    await message.answer(f"✅ Добавлен сервер {next_num}.", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "➖ Удалить последний сервер")
async def admin_del_last_server(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    sess = SessionLocal()
    try:
        last = sess.query(Server).order_by(Server.number.desc()).first()
        if not last:
            return await message.answer("❌ Нет серверов для удаления.", reply_markup=kb_admin_servers())
        num = last.number
        sess.delete(last)
        sess.commit()
    finally:
        sess.close()
    await notify_roots(f"🗑 Админ {message.from_user.id} удалил сервер {num}")
    await message.answer(f"🗑 Удалён сервер {num}.", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "🔗 Управление ссылками серверов")
async def admin_server_links(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    sess = SessionLocal()
    try:
        servers = sess.query(Server).order_by(Server.number.asc()).all()
    finally:
        sess.close()
    if not servers:
        return await message.answer("Сервера отсутствуют.", reply_markup=kb_admin_servers())
    kb = InlineKeyboardMarkup()
    for s in servers:
        kb.add(InlineKeyboardButton(f"Сервер {s.number}", callback_data=f"pick_srv:{s.id}"))
    await message.answer("Выбери сервер для управления ссылкой:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("pick_srv:"))
async def cb_pick_server(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    srv_id = int(call.data.split(":")[1])
    user_states[call.from_user.id] = {"screen": "admin_srv_edit", "srv_id": srv_id}
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📎 Добавить ссылку"), KeyboardButton("❌ Удалить ссылку"))
    kb.row(KeyboardButton("🔙 Назад"))
    await call.message.edit_text("Действие с выбранным сервером:", reply_markup=None)
    await bot.send_message(call.from_user.id, "Выбери действие:", reply_markup=kb)
    await call.answer()

@dp.message_handler(lambda m: m.text in ("📎 Добавить ссылку", "❌ Удалить ссылку"))
async def admin_srv_link_action(message: types.Message):
    st = user_states.get(message.from_user.id, {})
    if st.get("screen") != "admin_srv_edit":
        return
    if message.text == "📎 Добавить ссылку":
        user_states[message.from_user.id]["screen"] = "admin_srv_add_link"
        return await message.answer("Вставь ссылку Roblox:", reply_markup=kb_back())

    # удалить ссылку
    sess = SessionLocal()
    try:
        srv = sess.query(Server).filter_by(id=st.get("srv_id")).first()
        if not srv:
            return await message.answer("Сервер не найден.", reply_markup=kb_admin_main())
        srv.link = None
        sess.commit()
        await notify_roots(f"🔗 Админ {message.from_user.id} удалил ссылку у сервера {srv.number}")
    finally:
        sess.close()
    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("🗑 Ссылка удалена.", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "admin_srv_add_link")
async def admin_srv_add_link(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())

    link = message.text.strip()
    st = user_states.get(message.from_user.id, {})
    srv_id = st.get("srv_id")
    sess = SessionLocal()
    try:
        srv = sess.query(Server).filter_by(id=srv_id).first()
        if not srv:
            return await message.answer("❌ Сервер не найден.", reply_markup=kb_admin_main())
        srv.link = link
        sess.commit()
        await notify_roots(f"🔗 Админ {message.from_user.id} установил ссылку для сервера {srv.number}")
    finally:
        sess.close()
    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("✅ Ссылка добавлена!", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: m.text == "📝 Сообщение закрытого сервера")
async def admin_srv_closed_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    sess = SessionLocal()
    try:
        servers = sess.query(Server).order_by(Server.number.asc()).all()
    finally:
        sess.close()
    if not servers:
        return await message.answer("Сервера отсутствуют.", reply_markup=kb_admin_servers())
    kb = InlineKeyboardMarkup()
    for s in servers:
        kb.add(InlineKeyboardButton(f"Сервер {s.number}", callback_data=f"srv_msg:{s.id}"))
    await message.answer("Выбери сервер для изменения сообщения закрытия:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("srv_msg:"))
async def cb_srv_msg(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа.", show_alert=True)
    srv_id = int(call.data.split(":")[1])
    user_states[call.from_user.id] = {"screen": "admin_srv_set_msg", "srv_id": srv_id}
    await call.message.edit_text("Введи новое сообщение (например «Сервер закрыт»):", reply_markup=None)
    await call.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "admin_srv_set_msg")
async def admin_srv_set_msg(message: types.Message):
    text_msg = message.text.strip()
    st = user_states.get(message.from_user.id, {})
    srv_id = st.get("srv_id")
    sess = SessionLocal()
    try:
        srv = sess.query(Server).filter_by(id=srv_id).first()
        if not srv:
            return await message.answer("Сервер не найден.", reply_markup=kb_admin_main())
        srv.closed_message = text_msg
        sess.commit()
        await notify_roots(f"📝 Админ {message.from_user.id} изменил сообщение закрытого сервера {srv.number} → «{text_msg}»")
    finally:
        sess.close()
    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("✅ Сообщение обновлено.", reply_markup=kb_admin_main())

# -----------------------
# Админка: Промокоды (полный)
# -----------------------
@dp.message_handler(lambda m: m.text == "🎟 Промокоды")
async def admin_promos(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_promos"}
    await message.answer("🎟 Управление промокодами:", reply_markup=kb_admin_promos())

@dp.message_handler(lambda m: m.text == "📋 Список (все)")
async def promos_list_all(message: types.Message):
    if not is_admin(message.from_user.id): return
    sess = SessionLocal()
    try:
        promos = sess.query(PromoCode).order_by(PromoCode.id.desc()).all()
    finally:
        sess.close()
    if not promos:
        return await message.answer("Пусто.", reply_markup=kb_admin_promos())
    lines = []
    now = datetime.utcnow()
    for p in promos:
        active = (p.max_uses is None or p.uses < p.max_uses) and (not p.expires_at or now <= p.expires_at)
        lines.append(f"{'✅' if active else '⛔'} <code>{p.code}</code> • {p.promo_type} • val={p.value} • uses={p.uses}/{p.max_uses or '∞'} • exp={p.expires_at or '∞'}")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb_admin_promos())

@dp.message_handler(lambda m: m.text == "✅ Список (активные)")
async def promos_list_active(message: types.Message):
    if not is_admin(message.from_user.id): return
    now = datetime.utcnow()
    sess = SessionLocal()
    try:
        promos = sess.query(PromoCode).order_by(PromoCode.id.desc()).all()
    finally:
        sess.close()
    filtered = [p for p in promos if (p.max_uses is None or p.uses < p.max_uses) and (not p.expires_at or now <= p.expires_at)]
    if not filtered:
        return await message.answer("Активных нет.", reply_markup=kb_admin_promos())
    lines = [f"✅ <code>{p.code}</code> • {p.promo_type} • +{p.value}" for p in filtered]
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb_admin_promos())

@dp.message_handler(lambda m: m.text == "⛔ Список (неактивные)")
async def promos_list_inactive(message: types.Message):
    if not is_admin(message.from_user.id): return
    now = datetime.utcnow()
    sess = SessionLocal()
    try:
        promos = sess.query(PromoCode).order_by(PromoCode.id.desc()).all()
    finally:
        sess.close()
    filtered = [p for p in promos if (p.max_uses is not None and p.uses >= p.max_uses) or (p.expires_at and now > p.expires_at)]
    if not filtered:
        return await message.answer("Неактивных нет.", reply_markup=kb_admin_promos())
    lines = [f"⛔ <code>{p.code}</code> • {p.promo_type}" for p in filtered]
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb_admin_promos())

@dp.message_handler(lambda m: m.text == "🗑 Удалить промокод")
async def promo_delete_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "admin_promo_delete"}
    await message.answer("Введи код промокода для удаления:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "admin_promo_delete")
async def promo_delete_do(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "admin_promos"}
        return await message.answer("🎟 Промокоды:", reply_markup=kb_admin_promos())

    code = message.text.strip()
    sess = SessionLocal()
    try:
        p = sess.query(PromoCode).filter_by(code=code).first()
        if not p:
            return await message.answer("❌ Не найден.", reply_markup=kb_admin_promos())
        sess.delete(p)
        sess.commit()
    finally:
        sess.close()
    await notify_roots(f"🗑 Админ {message.from_user.id} удалил промокод {code}")
    user_states[message.from_user.id] = {"screen": "admin_promos"}
    await message.answer("✅ Удалён.", reply_markup=kb_admin_promos())

# Wizard создания промокода
@dp.message_handler(lambda m: m.text == "➕ Создать промокод")
async def promo_create_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "promo_create", "step": "type"}
    kb = InlineKeyboardMarkup()
    for t in ("value", "cash", "item", "discount", "admin_access"):
        kb.add(InlineKeyboardButton(t, callback_data=f"pc_type:{t}"))
    await message.answer("Выбери тип промокода:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("pc_type:"))
async def pc_pick_type(call: CallbackQuery):
    t = call.data.split(":")[1]
    st = {"screen": "promo_create", "step": "value", "promo_type": t}
    user_states[call.from_user.id] = st
    await call.message.edit_text(f"Тип: <b>{t}</b>\nВведи числовое значение (например, 100).", parse_mode=ParseMode.HTML)
    await call.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "promo_create")
async def promo_create_flow(message: types.Message):
    st = user_states.get(message.from_user.id, {})
    step = st.get("step")

    # Шаг: value
    if step == "value":
        try:
            val = int(message.text.strip())
        except ValueError:
            return await message.answer("Введи число.")
        st["value"] = val
        st["step"] = "max_uses"
        user_states[message.from_user.id] = st
        return await message.answer("Сколько активаций? (число) или напиши '∞' для безлимитно.")

    # Шаг: max_uses
    if step == "max_uses":
        txt = message.text.strip()
        if txt == "∞":
            st["max_uses"] = None
        else:
            try:
                st["max_uses"] = int(txt)
            except ValueError:
                return await message.answer("Введи число или '∞'.")
        st["step"] = "duration"
        user_states[message.from_user.id] = st
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("Минуты", callback_data="pc_dur:minutes"),
            InlineKeyboardButton("Часы", callback_data="pc_dur:hours"),
            InlineKeyboardButton("Дни", callback_data="pc_dur:days"),
            InlineKeyboardButton("Безлимитно", callback_data="pc_dur:inf"),
        )
        return await message.answer("Выбери период действия:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("pc_dur:"))
async def pc_pick_duration(call: CallbackQuery):
    kind = call.data.split(":")[1]
    st = user_states.get(call.from_user.id, {})
    if kind == "inf":
        st["expires_at"] = None
        st["step"] = "code"
        user_states[call.from_user.id] = st
        await call.message.edit_text("Введи текст кода (например: BIGBOB2025).")
        return await call.answer()
    # иначе просим число периода
    st["dur_kind"] = kind
    st["step"] = "dur_value"
    user_states[call.from_user.id] = st
    await call.message.edit_text(f"Сколько { 'минут' if kind=='minutes' else 'часов' if kind=='hours' else 'дней' }?")
    await call.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "promo_create" and user_states.get(m.from_user.id, {}).get("step") in ("dur_value", "code"))
async def promo_create_duration_and_code(message: types.Message):
    st = user_states.get(message.from_user.id, {})
    step = st.get("step")

    if step == "dur_value":
        try:
            n = int(message.text.strip())
        except ValueError:
            return await message.answer("Введи число.")
        now = datetime.utcnow()
        kind = st.get("dur_kind")
        if kind == "minutes":
            st["expires_at"] = now + timedelta(minutes=n)
        elif kind == "hours":
            st["expires_at"] = now + timedelta(hours=n)
        else:
            st["expires_at"] = now + timedelta(days=n)
        st["step"] = "code"
        user_states[message.from_user.id] = st
        return await message.answer("Теперь введи сам промокод (например: BIGBOB2025).")

    if step == "code":
        code = message.text.strip()
        st["code"] = code
        # сохранить в БД
        sess = SessionLocal()
        try:
            p = PromoCode(
                code=st["code"],
                promo_type=st["promo_type"],
                value=st["value"],
                max_uses=st["max_uses"],
                uses=0,
                expires_at=st.get("expires_at"),
                admin_access=True if st["promo_type"] == "admin_access" else False
            )
            sess.add(p)
            sess.commit()
        finally:
            sess.close()
        await notify_roots(f"🎟 Админ {message.from_user.id} создал промокод {st['code']} ({st['promo_type']} val={st['value']})")
        user_states[message.from_user.id] = {"screen": "admin_promos"}
        await message.answer("✅ Промокод создан.", reply_markup=kb_admin_promos())

# -----------------------
# Админка: Магазин (полный)
# -----------------------
@dp.message_handler(lambda m: m.text == "🛒 Магазин")
async def admin_store(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "admin_store"}
    await message.answer("🛒 Управление магазином:", reply_markup=kb_admin_store())

@dp.message_handler(lambda m: m.text == "📦 Список товаров")
async def admin_store_list(message: types.Message):
    if not is_admin(message.from_user.id): return
    sess = SessionLocal()
    try:
        items = sess.query(Item).order_by(Item.id.asc()).all()
    finally:
        sess.close()
    if not items:
        return await message.answer("Товаров пока нет.", reply_markup=kb_admin_store())
    lines = [f"{'✅' if it.is_active else '⛔'} #{it.id} [{it.category}] {it.name} — {it.price}🥜" for it in items]
    await message.answer("\n".join(lines), reply_markup=kb_admin_store())

@dp.message_handler(lambda m: m.text == "➕ Добавить товар")
async def admin_store_add(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "store_add", "step": "category"}
    kb = InlineKeyboardMarkup()
    for c in ("cash", "privilege", "item"):
        kb.add(InlineKeyboardButton(c, callback_data=f"sadd_cat:{c}"))
    await message.answer("Выбери категорию товара:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("sadd_cat:"))
async def sadd_pick_cat(call: CallbackQuery):
    cat = call.data.split(":")[1]
    st = {"screen": "store_add", "step": "name", "category": cat}
    user_states[call.from_user.id] = st
    await call.message.edit_text(f"Категория: <b>{cat}</b>\nВведи название товара:", parse_mode=ParseMode.HTML)
    await call.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "store_add")
async def store_add_flow(message: types.Message):
    st = user_states.get(message.from_user.id, {})
    step = st.get("step")

    if step == "name":
        st["name"] = message.text.strip()
        st["step"] = "price"
        user_states[message.from_user.id] = st
        return await message.answer("Введи цену в орешках (число):")

    if step == "price":
        try:
            price = int(message.text.strip())
        except ValueError:
            return await message.answer("Число, пожалуйста.")
        sess = SessionLocal()
        try:
            it = Item(name=st["name"], price=price, category=st["category"], is_active=True)
            sess.add(it)
            sess.commit()
            new_id = it.id
        finally:
            sess.close()
        await notify_roots(f"🛒 Админ {message.from_user.id} добавил товар #{new_id} [{st['category']}] {st['name']} — {price}🥜")
        user_states[message.from_user.id] = {"screen": "admin_store"}
        await message.answer("✅ Товар добавлен.", reply_markup=kb_admin_store())

@dp.message_handler(lambda m: m.text == "🗑 Удалить товар")
async def admin_store_del(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "store_del"}
    await message.answer("Введи ID товара для удаления:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "store_del")
async def admin_store_del_do(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "admin_store"}
        return await message.answer("🛒 Управление магазином:", reply_markup=kb_admin_store())
    try:
        iid = int(message.text.strip())
    except ValueError:
        return await message.answer("Нужен числовой ID.")
    sess = SessionLocal()
    try:
        it = sess.query(Item).filter_by(id=iid).first()
        if not it:
            return await message.answer("❌ Не найден.", reply_markup=kb_admin_store())
        sess.delete(it)
        sess.commit()
    finally:
        sess.close()
    await notify_roots(f"🗑 Админ {message.from_user.id} удалил товар #{iid}")
    user_states[message.from_user.id] = {"screen": "admin_store"}
    await message.answer("✅ Товар удалён.", reply_markup=kb_admin_store())

# -----------------------
# Админка: Настройки
# -----------------------
@dp.message_handler(lambda m: m.text == "⚙ Настройки")
async def admin_settings(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "admin_settings"}
    await message.answer("⚙ Настройки админов:", reply_markup=kb_admin_settings())

@dp.message_handler(lambda m: m.text == "📃 Список администраторов")
async def admin_list_admins(message: types.Message):
    if not is_admin(message.from_user.id): return
    sess = SessionLocal()
    try:
        rows = sess.execute(text("SELECT telegram_id FROM admins ORDER BY telegram_id ASC")).fetchall()
    finally:
        sess.close()
    ids = [str(r[0]) for r in rows]
    txt = "👑 Администраторы:\n" + ("\n".join(ids) if ids else "— пусто —")
    await message.answer(txt, reply_markup=kb_admin_settings())

@dp.message_handler(lambda m: m.text == "➕ Выдать администратора (ID)")
async def admin_give_by_id(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "admin_add_manual"}
    await message.answer("Введи Telegram ID пользователя:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "admin_add_manual")
async def admin_add_manual(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "admin_settings"}
        return await message.answer("⚙ Настройки админов:", reply_markup=kb_admin_settings())
    try:
        tid = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Неверный формат. Введи числовой Telegram ID.")
    add_admin(tid)
    await notify_roots(f"✅ Админ {message.from_user.id} выдал права админа {tid}")
    user_states[message.from_user.id] = {"screen": "admin_settings"}
    await message.answer("✅ Права выданы.", reply_markup=kb_admin_settings())

@dp.message_handler(lambda m: m.text == "➖ Удалить администратора (ID)")
async def admin_remove_admin_cmd(message: types.Message):
    if not is_admin(message.from_user.id): return
    user_states[message.from_user.id] = {"screen": "admin_remove_manual"}
    await message.answer("Введи Telegram ID для снятия прав:", reply_markup=kb_back())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "admin_remove_manual")
async def admin_remove_manual(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "admin_settings"}
        return await message.answer("⚙ Настройки админов:", reply_markup=kb_admin_settings())
    try:
        tid = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Неверный формат. Введи числовой Telegram ID.")
    remove_admin(tid)
    await notify_roots(f"🗑 Админ {message.from_user.id} снял права с {tid}")
    user_states[message.from_user.id] = {"screen": "admin_settings"}
    await message.answer("✅ Права сняты.", reply_markup=kb_admin_settings())
