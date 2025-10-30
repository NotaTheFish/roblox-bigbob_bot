# bot/main_core.py
# aiogram 2.25.1 — вебхук обрабатывается во Flask (см. bot/web_server.py)
# Улучшено: SQLite FSM (user_states), aiohttp для Roblox, антифлуд, чистые хелперы БД.

import asyncio
import json
import logging
import random
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional, Callable

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ParseMode, CallbackQuery
)

from bot.config import TOKEN, ADMINS, ADMIN_ROOT_IDS  # ADMINS/ADMIN_ROOT_IDS берём из .env
from bot.db import SessionLocal, Base, engine, User, Server, PromoCode, Item  # БД-модели и движок

# -------------------------------------------------
# ЛОГИ
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main_core")

# -------------------------------------------------
# БОТ / ДИСПЕТЧЕР
# -------------------------------------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Совокупность админов (из конфига). Локально можно расширить списком.
ADMIN_IDS = set(ADMINS or []) | set(ADMIN_ROOT_IDS or [])

# -------------------------------------------------
# SQLite FSM — таблица состояний
# -------------------------------------------------
from sqlalchemy import Column, Integer, String

class UserState(Base):
    __tablename__ = "user_states"

    user_id = Column(Integer, primary_key=True, index=True)
    screen = Column(String, default="main")
    data = Column(String, default="{}")  # JSON словарь контекста

# Создадим таблицу, если её ещё нет
Base.metadata.create_all(bind=engine)

@contextmanager
def session_scope():
    """Контекстный менеджер для сессий SQLAlchemy."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

def ensure_user(uid: int) -> None:
    """Гарантируем наличие пользователя и записи состояния в БД."""
    with session_scope() as s:
        u = s.query(User).filter_by(telegram_id=uid).first()
        if not u:
            u = User(telegram_id=uid, verified=False)
            s.add(u)
        st = s.query(UserState).get(uid)
        if not st:
            st = UserState(user_id=uid, screen="main", data="{}")
            s.add(st)

def get_state(uid: int) -> Dict[str, Any]:
    """Читаем состояние пользователя из SQLite."""
    with session_scope() as s:
        st = s.query(UserState).get(uid)
        if not st:
            st = UserState(user_id=uid, screen="main", data="{}")
            s.add(st)
            return {"screen": "main"}
        try:
            payload = json.loads(st.data or "{}")
        except Exception:
            payload = {}
        payload["screen"] = st.screen or "main"
        return payload

def set_state(uid: int, screen: Optional[str] = None, **data) -> None:
    """Сохраняем состояние пользователя в SQLite."""
    with session_scope() as s:
        st = s.query(UserState).get(uid)
        if not st:
            st = UserState(user_id=uid, screen=screen or "main", data=json.dumps(data or {}))
            s.add(st)
            return
        try:
            payload = json.loads(st.data or "{}")
        except Exception:
            payload = {}
        if data:
            payload.update(data)
        if screen is not None:
            st.screen = screen
        st.data = json.dumps(payload)

def state_is(expected: str) -> Callable[[types.Message], bool]:
    """Фильтр aiogram: текущий экран равен expected."""
    def _pred(m: types.Message) -> bool:
        st = get_state(m.from_user.id)
        return st.get("screen") == expected
    return _pred

# -------------------------------------------------
# АНТИФЛУД (простая защита)
# -------------------------------------------------
_last_action_ts: Dict[int, float] = {}
ANTIFLOOD_SECONDS = 0.8

def not_flooding(uid: int) -> bool:
    now = time.monotonic()
    last = _last_action_ts.get(uid, 0.0)
    if now - last < ANTIFLOOD_SECONDS:
        return False
    _last_action_ts[uid] = now
    return True

# -------------------------------------------------
# ROBLOX HELPERS — aiohttp (не блокируем event loop)
# -------------------------------------------------
HTTP_TIMEOUT = 8

async def _fetch_json(session: aiohttp.ClientSession, method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
    try:
        async with session.request(method, url, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientError as e:
        log.warning("Roblox HTTP error: %s", e)
        return None

async def get_description_by_username(username: str) -> Optional[str]:
    """Возвращает описание Roblox-профиля по нику."""
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 1) имя -> id
        url_lookup = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username], "excludeBannedUsers": True}
        data = await _fetch_json(session, "POST", url_lookup, json=payload)
        if not data or not data.get("data"):
            return None
        user_id = data["data"][0].get("id")
        if not user_id:
            return None
        # 2) id -> описание
        url_user = f"https://users.roblox.com/v1/users/{user_id}"
        info = await _fetch_json(session, "GET", url_user)
        if not info:
            return None
        return info.get("description")

# -------------------------------------------------
# КНОПКИ / КЛАВИАТУРЫ
# -------------------------------------------------
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
    kb.row(KeyboardButton("💰 Баланс"), KeyboardButton("🎁 Активировать промокод"))
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
    kb.row(KeyboardButton("↩️ Выйти в режим пользователя"))
    return kb

def kb_admin_servers() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Добавить сервер"), KeyboardButton("➖ Удалить последний сервер"))
    kb.row(KeyboardButton("🔗 Управление ссылками серверов"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    return kb

# -------------------------------------------------
# УТИЛИТЫ
# -------------------------------------------------
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

async def show_main_menu(chat_id: int):
    set_state(chat_id, screen="main")
    await bot.send_message(chat_id, "🏠 Главное меню", reply_markup=kb_main())

# -------------------------------------------------
# КОМАНДЫ: /start /verify /check
# -------------------------------------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer(
        "👋 Привет! Я помогу тебе войти на приватные сервера Roblox.\n"
        "Нажми «⚡ Играть» или зайди в «💼 Аккаунт». Для подтверждения аккаунта используй /verify.",
        reply_markup=kb_main()
    )

@dp.message_handler(commands=['verify'])
async def cmd_verify(message: types.Message):
    ensure_user(message.from_user.id)
    set_state(message.from_user.id, screen="await_nick")
    await message.answer("✍️ Напиши свой ник Roblox:", reply_markup=kb_back())

@dp.message_handler(state_is("await_nick"))
async def handle_nick(message: types.Message):
    if message.text == "🔙 Назад":
        return await show_main_menu(message.chat.id)

    nick = (message.text or "").strip()
    if not nick:
        return await message.answer("❗ Укажи ник текстом.")

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Да ✅", callback_data="nick_yes"))
    kb.add(InlineKeyboardButton("Нет ❌", callback_data="nick_no"))
    set_state(message.from_user.id, screen="confirm_nick", nick=nick)
    await message.answer(
        f"Проверим, это твой ник в Roblox?\n\n<b>{nick}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data in ("nick_yes", "nick_no"))
async def cb_confirm_nick(call: CallbackQuery):
    uid = call.from_user.id
    st = get_state(uid)

    if call.data == "nick_no":
        set_state(uid, screen="await_nick", nick=None)
        await call.message.edit_text("Окей, введи ник ещё раз ✍️")
        return await call.answer()

    nick = st.get("nick")
    if not nick:
        await call.answer("Повтори /verify", show_alert=True)
        return

    code = str(random.randint(10000, 99999))
    with session_scope() as s:
        u = s.query(User).filter_by(telegram_id=uid).first()
        if not u:
            u = User(telegram_id=uid, verified=False)
            s.add(u)
            s.flush()
        u.roblox_user = nick
        u.code = code
        u.verified = False

    try:
        await call.message.edit_text(
            "✅ Сгенерирован код подтверждения.\n"
            f"Добавь этот код в описание профиля Roblox (About/О себе):\n\n<code>{code}</code>\n\n"
            "Когда готово — нажми /check.",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await bot.send_message(
            uid,
            "✅ Сгенерирован код подтверждения.\n"
            f"Вставь в описание Roblox:\n\n<code>{code}</code>\n\nЗатем — /check.",
            parse_mode=ParseMode.HTML
        )

    set_state(uid, screen="main", nick=None)
    await call.answer()

@dp.message_handler(commands=['check'])
async def cmd_check(message: types.Message):
    uid = message.from_user.id
    with session_scope() as s:
        u = s.query(User).filter_by(telegram_id=uid).first()
        if not u or not u.roblox_user:
            return await message.answer("❌ Сначала сделай /verify и укажи ник.")
        if not u.code:
            return await message.answer("❌ Код подтверждения не найден. Повтори /verify.")

    status = await message.answer("🔍 Проверяю Roblox профиль…")

    # антифлуд (на кнопке часто жмут)
    if not not_flooding(uid):
        return await status.edit_text("⏳ Подожди немного и повтори.")

    desc = await get_description_by_username(u.roblox_user.strip())
    if desc is None:
        return await status.edit_text("❌ Профиль не найден или Roblox API недоступен, попробуй позже.")

    if not (desc or "").strip():
        return await status.edit_text("⚠️ Профиль закрыт или пустое описание. Открой профиль и вставь код.")

    needle = (u.code or "").replace(" ", "").lower()
    hay = (desc or "").replace(" ", "").lower()
    if needle and needle in hay:
        with session_scope() as s:
            dbu = s.query(User).filter_by(telegram_id=uid).first()
            if dbu:
                dbu.verified = True
                # по желанию — одноразовый код:
                # dbu.code = None
        await status.edit_text("✅ Аккаунт подтверждён! Доступ открыт.")
        await show_main_menu(message.chat.id)
    else:
        await status.edit_text("❌ Код не найден в описании. Убедись, что вставил верно и профиль открыт.")

# -------------------------------------------------
# ИГРАТЬ — список серверов
# -------------------------------------------------
@dp.message_handler(lambda m: m.text == "⚡ Играть")
async def menu_play(message: types.Message):
    with session_scope() as s:
        servers = s.query(Server).order_by(Server.number.asc()).all()

    if not servers:
        return await message.answer("❌ Сервера ещё не добавлены.", reply_markup=kb_main())

    kb = InlineKeyboardMarkup()
    for srv in servers:
        if srv.link:
            kb.add(InlineKeyboardButton(f"Сервер {srv.number}", url=srv.link))
        else:
            kb.add(InlineKeyboardButton(f"Сервер {srv.number} ❌", callback_data=f"srv_closed:{srv.number}"))
    await message.answer("🎮 Выбери сервер:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("srv_closed:"))
async def cb_srv_closed(call: CallbackQuery):
    n = call.data.split(":")[1]
    await call.answer(f"Сервер {n} закрыт", show_alert=True)

# -------------------------------------------------
# АККАУНТ
# -------------------------------------------------
@dp.message_handler(lambda m: m.text == "💼 Аккаунт")
async def menu_account(message: types.Message):
    uid = message.from_user.id
    with session_scope() as s:
        u = s.query(User).filter_by(telegram_id=uid).first()
        if not u:
            ensure_user(uid)
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

    set_state(uid, screen="account")
    await message.answer(info, reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "💰 Баланс")
async def account_balance(message: types.Message):
    uid = message.from_user.id
    with session_scope() as s:
        u = s.query(User).filter_by(telegram_id=uid).first()
        bal = u.balance if u else 0
    await message.answer(f"💰 Твой баланс: <b>{bal}</b> орешков.", parse_mode=ParseMode.HTML, reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "🎁 Активировать промокод")
async def account_promocode(message: types.Message):
    set_state(message.from_user.id, screen="await_promocode")
    await message.answer("Введи промокод:", reply_markup=kb_back())

@dp.message_handler(state_is("await_promocode"))
async def handle_promocode(message: types.Message):
    uid = message.from_user.id
    if message.text == "🔙 Назад":
        set_state(uid, screen="account")
        return await message.answer("Меню аккаунта:", reply_markup=kb_account())

    code = (message.text or "").strip()

    with session_scope() as s:
        promo = s.query(PromoCode).filter_by(code=code).first()
        u = s.query(User).filter_by(telegram_id=uid).first()

        if not promo or not promo.active:
            return await message.answer("❌ Промокод не найден или не активен.", reply_markup=kb_account())

        # Срок действия
        if getattr(promo, "expires_at", None) and datetime.utcnow() > promo.expires_at:
            return await message.answer("⌛ Срок действия промокода истёк.", reply_markup=kb_account())

        # Лимит активаций
        if promo.max_uses is not None and promo.uses >= promo.max_uses:
            return await message.answer("⌛ Промокод исчерпан.", reply_markup=kb_account())

        # Применение
        if promo.promo_type in ("value", "discount"):
            u.balance += promo.value or 0

        promo.uses += 1

    set_state(uid, screen="account")
    await message.answer("✅ Промокод применён!", reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "👥 Реферальная программа")
async def account_ref(message: types.Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"Приглашай друзей и получай бонусы!\n🔗 Твоя ссылка: {link}", reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "🏆 Топ игроков")
async def account_top(message: types.Message):
    with session_scope() as s:
        top = s.query(User).order_by(User.level.desc()).limit(15).all()
        lines = [f"• {u.roblox_user or '—'} — уровень {u.level}" for u in top]
    txt = "🏆 Топ 15 игроков:\n" + ("\n".join(lines) if lines else "Пока пусто.")
    await message.answer(txt, reply_markup=kb_account())

# -------------------------------------------------
# МАГАЗИН (пользователь)
# -------------------------------------------------
@dp.message_handler(lambda m: m.text == "💰 Донат-меню")
async def menu_shop(message: types.Message):
    set_state(message.from_user.id, screen="shop")
    await message.answer("🛒 Магазин:", reply_markup=kb_shop())

@dp.message_handler(lambda m: m.text in ("💸 Купить кеш", "🛡 Купить привилегию", "🎒 Купить предмет"))
async def shop_items(message: types.Message):
    label = message.text
    with session_scope() as s:
        items = s.query(Item).filter_by(is_active=True).order_by(Item.price.asc()).all()
    if not items:
        return await message.answer("Пока нет доступных товаров.", reply_markup=kb_shop())
    kb = InlineKeyboardMarkup()
    for it in items:
        kb.add(InlineKeyboardButton(f"{it.name} — {it.price} ореш.", callback_data=f"buy_item:{it.id}"))
    await message.answer(f"Раздел: {label}\nВыбери товар:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("buy_item:"))
async def cb_buy_item(call: CallbackQuery):
    item_id = int(call.data.split(":")[1])
    uid = call.from_user.id
    with session_scope() as s:
        it = s.query(Item).filter_by(id=item_id, is_active=True).first()
        u = s.query(User).filter_by(telegram_id=uid).first()
        if not it or not u:
            return await call.answer("Товар недоступен.", show_alert=True)
        if u.balance < it.price:
            return await call.answer("Недостаточно орешков.", show_alert=True)
        u.balance -= it.price
        u.items = (u.items or "")
        u.items += (", " if u.items else "") + it.name
    await call.answer("Покупка успешна!", show_alert=True)

# -------------------------------------------------
# НАЗАД И FALLBACK
# -------------------------------------------------
@dp.message_handler(lambda m: m.text == "🔙 Назад")
async def go_back(message: types.Message):
    st = get_state(message.from_user.id)
    screen = st.get("screen", "main")
    if screen in ("account", "shop"):
        return await show_main_menu(message.chat.id)
    if isinstance(screen, str) and screen.startswith("admin"):
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    return await show_main_menu(message.chat.id)

# -------------------------------------------------
# АДМИНКА
# -------------------------------------------------
@dp.message_handler(lambda m: m.text == "👑 Админ-панель")
async def enter_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    set_state(message.from_user.id, screen="admin")
    await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: m.text == "↩️ Выйти в режим пользователя")
async def leave_admin(message: types.Message):
    await show_main_menu(message.chat.id)

# --- Админ: сервера ---
@dp.message_handler(lambda m: m.text == "🖥 Сервера")
async def admin_servers(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    set_state(message.from_user.id, screen="admin_servers")
    await message.answer("🖥 Управление серверами:", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "➕ Добавить сервер")
async def admin_add_server(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    with session_scope() as s:
        last = s.query(Server).order_by(Server.number.desc()).first()
        next_num = (last.number + 1) if last else 1
        srv = Server(number=next_num, link=None, closed_message="Сервер закрыт")
        s.add(srv)
    await message.answer(f"✅ Добавлен сервер {next_num}.", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "➖ Удалить последний сервер")
async def admin_del_last_server(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    with session_scope() as s:
        last = s.query(Server).order_by(Server.number.desc()).first()
        if not last:
            return await message.answer("❌ Нет серверов для удаления.", reply_markup=kb_admin_servers())
        num = last.number
        s.delete(last)
    await message.answer(f"🗑 Удалён сервер {num}.", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "🔗 Управление ссылками серверов")
async def admin_server_links(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    with session_scope() as s:
        servers = s.query(Server).order_by(Server.number.asc()).all()
    if not servers:
        return await message.answer("Сервера отсутствуют.", reply_markup=kb_admin_servers())

    kb = InlineKeyboardMarkup()
    for srv in servers:
        kb.add(InlineKeyboardButton(f"Сервер {srv.number}", callback_data=f"pick_srv:{srv.id}"))
    await message.answer("Выбери сервер для управления ссылкой:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("pick_srv:"))
async def cb_pick_server(call: CallbackQuery):
    srv_id = int(call.data.split(":")[1])
    set_state(call.from_user.id, screen="admin_srv_edit", srv_id=srv_id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📎 Добавить ссылку"), KeyboardButton("❌ Удалить ссылку"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    await call.message.edit_text("Действие с выбранным сервером:", reply_markup=None)
    await bot.send_message(call.from_user.id, "Выбери действие:", reply_markup=kb)
    await call.answer()

@dp.message_handler(lambda m: m.text in ("📎 Добавить ссылку", "❌ Удалить ссылку"))
async def admin_srv_link_action(message: types.Message):
    st = get_state(message.from_user.id)
    if st.get("screen") != "admin_srv_edit":
        return
    if message.text == "📎 Добавить ссылку":
        set_state(message.from_user.id, screen="admin_srv_add_link")
        return await message.answer("Вставь ссылку Roblox (share URL):", reply_markup=kb_back())

    # удалить ссылку
    with session_scope() as s:
        srv = s.query(Server).filter_by(id=st.get("srv_id")).first()
        if not srv:
            return await message.answer("Сервер не найден.", reply_markup=kb_admin_main())
        srv.link = None
    set_state(message.from_user.id, screen="admin")
    await message.answer("🗑 Ссылка удалена.", reply_markup=kb_admin_main())

@dp.message_handler(state_is("admin_srv_add_link"))
async def admin_srv_add_link(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    link = (message.text or "").strip()
    st = get_state(message.from_user.id)
    srv_id = st.get("srv_id")
    if not srv_id:
        set_state(message.from_user.id, screen="admin")
        return await message.answer("❌ Контекст сервера потерян.", reply_markup=kb_admin_main())

    with session_scope() as s:
        srv = s.query(Server).filter_by(id=srv_id).first()
        if not srv:
            return await message.answer("❌ Сервер не найден.", reply_markup=kb_admin_main())
        srv.link = link

    set_state(message.from_user.id, screen="admin")
    await message.answer("✅ Ссылка добавлена!", reply_markup=kb_admin_main())

# --- Админ: промокоды ---
def kb_admin_promos() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📜 Список промокодов"))
    kb.row(KeyboardButton("➕ Создать промокод"), KeyboardButton("🗑 Удалить промокод"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    return kb

@dp.message_handler(lambda m: m.text == "🎟 Промокоды")
async def admin_promos(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    set_state(message.from_user.id, screen="admin_promos")
    await message.answer("🎟 Промокоды:", reply_markup=kb_admin_promos())

@dp.message_handler(lambda m: m.text == "📜 Список промокодов")
async def admin_promos_list(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    with session_scope() as s:
        promos = s.query(PromoCode).order_by(PromoCode.id.desc()).limit(50).all()
        if not promos:
            return await message.answer("Промокодов нет.", reply_markup=kb_admin_promos())
        lines = []
        for p in promos:
            exp = p.expires_at.strftime("%Y-%m-%d %H:%M") if getattr(p, "expires_at", None) else "—"
            cap = f"{p.code} | type={p.promo_type} value={p.value} uses={p.uses}/{p.max_uses or '∞'} exp={exp}"
            lines.append(cap)
    await message.answer("Список промокодов:\n" + "\n".join(lines), reply_markup=kb_admin_promos())

@dp.message_handler(lambda m: m.text == "➕ Создать промокод")
async def admin_promo_create(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    set_state(message.from_user.id, screen="promo_new_type")
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("value"), KeyboardButton("discount"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    await message.answer(
        "Выбери тип промокода: value (начисляет орешки) или discount (аналогично для простоты)",
        reply_markup=kb
    )

@dp.message_handler(state_is("promo_new_type"))
async def promo_new_type(message: types.Message):
    if message.text.startswith("🔙"):
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    ptype = (message.text or "").strip().lower()
    if ptype not in ("value", "discount"):
        return await message.answer("Укажи: value или discount.")
    set_state(message.from_user.id, screen="promo_new_value", ptype=ptype)
    await message.answer("Введи числовое значение (сколько орешков начислять):", reply_markup=kb_back())

@dp.message_handler(state_is("promo_new_value"))
async def promo_new_value(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    try:
        val = int(message.text.strip())
    except Exception:
        return await message.answer("Нужно целое число.")
    st = get_state(message.from_user.id)
    st.update({"value": val})
    set_state(message.from_user.id, screen="promo_new_max", **st)
    await message.answer("Введи максимальное количество активаций (или 0 для ∞):", reply_markup=kb_back())

@dp.message_handler(state_is("promo_new_max"))
async def promo_new_max(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    try:
        mx = int(message.text.strip())
    except Exception:
        return await message.answer("Нужно целое число (0 — без лимита).")
    st = get_state(message.from_user.id)
    st.update({"max_uses": (None if mx == 0 else mx)})
    set_state(message.from_user.id, screen="promo_new_code", **st)
    await message.answer("Введи текст промокода (например, BIGBOB2025):", reply_markup=kb_back())

@dp.message_handler(state_is("promo_new_code"))
async def promo_new_code(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    code = (message.text or "").strip()
    st = get_state(message.from_user.id)
    with session_scope() as s:
        if s.query(PromoCode).filter_by(code=code).first():
            return await message.answer("❌ Такой код уже существует. Введи другой.")
        p = PromoCode(
            code=code,
            promo_type=st.get("ptype"),
            value=st.get("value", 0),
            max_uses=st.get("max_uses"),
            uses=0,
            expires_at=None
        )
        s.add(p)
    set_state(message.from_user.id, screen="admin")
    await message.answer("✅ Промокод создан.", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: m.text == "🗑 Удалить промокод")
async def admin_promo_delete(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    set_state(message.from_user.id, screen="promo_del_code")
    await message.answer("Введи код промокода для удаления:", reply_markup=kb_back())

@dp.message_handler(state_is("promo_del_code"))
async def promo_del_code(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    code = (message.text or "").strip()
    with session_scope() as s:
        p = s.query(PromoCode).filter_by(code=code).first()
        if not p:
            return await message.answer("❌ Промокод не найден.", reply_markup=kb_admin_main())
        s.delete(p)
    set_state(message.from_user.id, screen="admin")
    await message.answer("🗑 Промокод удалён.", reply_markup=kb_admin_main())

# --- Админ: магазин ---
def kb_admin_store() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📦 Список товаров"))
    kb.row(KeyboardButton("➕ Добавить товар"), KeyboardButton("🗑 Удалить товар"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    return kb

@dp.message_handler(lambda m: m.text == "🛒 Магазин")
async def admin_store(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    set_state(message.from_user.id, screen="admin_store")
    await message.answer("🛒 Управление магазином:", reply_markup=kb_admin_store())

@dp.message_handler(lambda m: m.text == "📦 Список товаров")
async def admin_store_list(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    with session_scope() as s:
        items = s.query(Item).order_by(Item.id.desc()).limit(50).all()
        if not items:
            return await message.answer("Пока нет товаров.", reply_markup=kb_admin_store())
        lines = [f"{it.id}. {it.name} — {it.price} ореш. ({'on' if it.is_active else 'off'})" for it in items]
    await message.answer("Список товаров:\n" + "\n".join(lines), reply_markup=kb_admin_store())

@dp.message_handler(lambda m: m.text == "➕ Добавить товар")
async def admin_store_add(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    set_state(message.from_user.id, screen="add_item_name")
    await message.answer("Название товара:", reply_markup=kb_back())

@dp.message_handler(state_is("add_item_name"))
async def admin_store_add_name(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin_store")
        return await message.answer("🛒 Управление магазином:", reply_markup=kb_admin_store())
    name = (message.text or "").strip()
    set_state(message.from_user.id, screen="add_item_price", name=name)
    await message.answer("Цена (в орешках), целое число:", reply_markup=kb_back())

@dp.message_handler(state_is("add_item_price"))
async def admin_store_add_price(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin_store")
        return await message.answer("🛒 Управление магазином:", reply_markup=kb_admin_store())
    try:
        price = int(message.text.strip())
    except Exception:
        return await message.answer("Нужно целое число.")
    st = get_state(message.from_user.id)
    name = st.get("name")
    with session_scope() as s:
        it = Item(name=name, price=price, is_active=True)
        s.add(it)
    set_state(message.from_user.id, screen="admin_store", name=None)
    await message.answer("✅ Товар добавлен.", reply_markup=kb_admin_store())

@dp.message_handler(lambda m: m.text == "🗑 Удалить товар")
async def admin_store_del(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    set_state(message.from_user.id, screen="del_item_id")
    await message.answer("Введи ID товара для удаления:", reply_markup=kb_back())

@dp.message_handler(state_is("del_item_id"))
async def admin_store_del_id(message: types.Message):
    if message.text == "🔙 Назад":
        set_state(message.from_user.id, screen="admin_store")
        return await message.answer("🛒 Управление магазином:", reply_markup=kb_admin_store())
    try:
        iid = int(message.text.strip())
    except Exception:
        return await message.answer("Нужно целое число — ID товара.")
    with session_scope() as s:
        it = s.query(Item).filter_by(id=iid).first()
        if not it:
            return await message.answer("❌ Товар не найден.", reply_markup=kb_admin_store())
        s.delete(it)
    set_state(message.from_user.id, screen="admin_store")
    await message.answer("🗑 Товар удалён.", reply_markup=kb_admin_store())

# -------------------------------------------------
# Fallback: универсальная «Назад (в админ-меню)» и дефолт
# -------------------------------------------------
@dp.message_handler()
async def fallback(message: types.Message):
    if message.text == "🔙 Назад (в админ-меню)":
        set_state(message.from_user.id, screen="admin")
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    await show_main_menu(message.chat.id)

