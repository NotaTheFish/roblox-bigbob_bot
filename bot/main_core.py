# bot/main_core.py
# aiogram==2.25.1

import asyncio
import random
from typing import Dict, Any, Optional, List

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ParseMode, CallbackQuery
)

from sqlalchemy import text

# ---- конфиг ----
try:
    from bot.config import TOKEN
except Exception:
    raise RuntimeError("В config.py должен быть TOKEN")

# Необязательные настройки (лучше задать в config.py)
try:
    from bot.config import ADMIN_ROOT_IDS  # список ID, кто подтверждает вход в админку
except Exception:
    ADMIN_ROOT_IDS = []  # задай в config.py

try:
    from bot.config import ADMIN_LOGIN_PASSWORD  # пароль для /admin_login
except Exception:
    ADMIN_LOGIN_PASSWORD = "CHANGE_ME_NOW"  # задай в config.py

from bot.db import SessionLocal, User, Server, PromoCode, Item

# -----------------------
#   Инициализация бота
# -----------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# -----------------------
#   Состояния и константы
# -----------------------
user_states: Dict[int, Dict[str, Any]] = {}

# -----------------------
#   Хелперы БД: таблица admins
# -----------------------
def ensure_admins_table():
    """Создаёт таблицу admins (telegram_id PRIMARY KEY), если её нет."""
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
    """Проверка по таблице admins."""
    sess = SessionLocal()
    try:
        r = sess.execute(text("SELECT telegram_id FROM admins WHERE telegram_id=:tid"), {"tid": user_id}).fetchone()
        return r is not None
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

# -----------------------
#   Логи для ROOT-админов
# -----------------------
async def notify_roots(text_msg: str):
    if not ADMIN_ROOT_IDS:
        return
    for rid in ADMIN_ROOT_IDS:
        try:
            await bot.send_message(rid, f"📣 <b>LOG</b>\n{text_msg}", parse_mode=ParseMode.HTML)
        except Exception:
            # если кому-то не доставили — просто игнор
            pass

# -----------------------
#   Клавиатуры
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
    kb.row(KeyboardButton("↩️ Выйти в режим пользователя"))
    return kb

def kb_admin_servers() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Добавить сервер"), KeyboardButton("➖ Удалить последний сервер"))
    kb.row(KeyboardButton("🔗 Управление ссылками серверов"))
    kb.row(KeyboardButton("📝 Сообщение закрытого сервера"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    return kb

def kb_admin_settings() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Выдать администратора по коду"))
    kb.row(KeyboardButton("➖ Удалить администратора"))
    kb.row(KeyboardButton("📃 Список администраторов"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    return kb

# -----------------------
#   Утилиты
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
#   Команды входа в админку (2FA)
# -----------------------
@dp.message_handler(commands=["admin_login"])
async def admin_login(message: types.Message):
    """
    Шаг 1: /admin_login <пароль>
    Если пароль верен — отправляем всем ROOT-админам запрос на одобрение.
    После одобрения — юзер попадает в таблицу admins.
    """
    parts = message.get_args().strip() if hasattr(message, "get_args") else ""
    if not parts:
        return await message.reply("Использование: <code>/admin_login ПАРОЛЬ</code>", parse_mode=ParseMode.HTML)

    pwd = parts
    if pwd != ADMIN_LOGIN_PASSWORD:
        await notify_roots(f"❌ Попытка входа в админку: @{message.from_user.username} ({message.from_user.id}), неверный пароль.")
        return await message.reply("❌ Неверный пароль.")

    # отправляем запрос на одобрение
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve:{message.from_user.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject:{message.from_user.id}")
    )
    caption = f"🛡 Запрос на выдачу админ-прав\n" \
              f"Пользователь: @{message.from_user.username or '—'} ({message.from_user.id})"
    for rid in ADMIN_ROOT_IDS:
        try:
            await bot.send_message(rid, caption, reply_markup=kb)
        except Exception:
            pass

    await message.reply("🕓 Запрос отправлен создателям. Ожидайте одобрения.")

@dp.callback_query_handler(lambda c: c.data.startswith("admin_approve:") or c.data.startswith("admin_reject:"))
async def cb_admin_approve(call: CallbackQuery):
    """Шаг 2: ROOT-админ одобряет/отклоняет заявку"""
    if call.from_user.id not in ADMIN_ROOT_IDS:
        return await call.answer("Нет прав.", show_alert=True)

    target_id = int(call.data.split(":")[1])
    if call.data.startswith("admin_approve:"):
        add_admin(target_id)
        await notify_roots(f"✅ Одобрено: {target_id} получил админ-права.")
        try:
            await bot.send_message(target_id, "✅ Тебе выданы админ-права. Зайди в «👑 Админ-панель».")
        except Exception:
            pass
        await call.message.edit_text(call.message.text + "\n\n✅ Одобрено.")
    else:
        await notify_roots(f"❌ Отклонено: {target_id} не получил админ-права.")
        try:
            await bot.send_message(target_id, "❌ Заявка на админ-права отклонена.")
        except Exception:
            pass
        await call.message.edit_text(call.message.text + "\n\n❌ Отклонено.")
    await call.answer()

# -----------------------
#   Пользовательские команды (кратко)
# -----------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    ensure_user_in_db(message.from_user.id)
    user_states[message.from_user.id] = {"screen": "main"}
    await message.answer(
        "👋 Привет! Я помогу тебе войти на приватные сервера Roblox.\n"
        "Нажми «⚡ Играть», зайди в «💼 Аккаунт» или «💰 Донат-меню».",
        reply_markup=kb_main()
    )

@dp.message_handler(lambda m: m.text == "⚡ Играть")
async def menu_play(message: types.Message):
    sess = SessionLocal()
    try:
        servers: List[Server] = sess.query(Server).order_by(Server.number.asc()).all()
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

def kb_account() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("💰 Баланс"), KeyboardButton("💸 Пополнить баланс"))
    kb.row(KeyboardButton("🎁 Активировать промокод"))
    kb.row(KeyboardButton("👥 Реферальная программа"), KeyboardButton("🏆 Топ игроков"))
    kb.row(KeyboardButton("🔙 Назад"))
    return kb

@dp.message_handler(lambda m: m.text == "💼 Аккаунт")
async def menu_account(message: types.Message):
    user_states[message.from_user.id] = {"screen": "account"}
    sess = SessionLocal()
    try:
        u: Optional[User] = sess.query(User).filter_by(telegram_id=message.from_user.id).first()
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
        if not promo:
            return await message.answer("❌ Промокод не найден.", reply_markup=kb_account())
        if promo.max_uses is not None and promo.uses >= promo.max_uses:
            return await message.answer("⌛ Промокод исчерпан.", reply_markup=kb_account())

        # пример применения
        if promo.promo_type in ("discount", "value"):
            u.balance += (promo.value or 0)

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

@dp.message_handler(lambda m: m.text in ("💸 Купить кеш", "🛡 Купить привилегию", "🎒 Купить предмет"))
async def shop_items(message: types.Message):
    await message.answer("🧱 Раздел в разработке. Здесь появятся товары.", reply_markup=kb_shop())

@dp.message_handler(lambda m: m.text == "🔙 Назад")
async def go_back(message: types.Message):
    screen = user_states.get(message.from_user.id, {}).get("screen", "main")
    if screen in ("account", "shop"):
        return await show_main_menu(message.chat.id)
    if screen in ("admin", "admin_users", "admin_servers", "admin_promos", "admin_store", "admin_settings",
                  "admin_srv_edit", "admin_srv_add_link"):
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    await show_main_menu(message.chat.id)

# -----------------------
#   Админ-панель
# -----------------------
@dp.message_handler(lambda m: m.text == "👑 Админ-панель")
async def enter_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Нет доступа. Введите /admin_login <пароль> и ждите одобрения.")
    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: m.text == "↩️ Выйти в режим пользователя")
async def leave_admin(message: types.Message):
    await show_main_menu(message.chat.id)

# ---- Админ: Пользователи (заглушка-вход) ----
@dp.message_handler(lambda m: m.text == "👥 Пользователи")
async def admin_users(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_users"}
    await message.answer("👥 Управление пользователями (в разработке).", reply_markup=kb_admin_main())

# ---- Админ: Сервера ----
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
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
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
        return await message.answer("Вставь ссылку Roblox (из твоего формата):", reply_markup=kb_back())

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
    # Выбор сервера
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

# ---- Админ: Промокоды (заглушка) ----
@dp.message_handler(lambda m: m.text == "🎟 Промокоды")
async def admin_promos(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_promos"}
    await message.answer("🎟 Управление промокодами (создание/список/удаление) — скоро здесь.", reply_markup=kb_admin_main())

# ---- Админ: Магазин (заглушка) ----
@dp.message_handler(lambda m: m.text == "🛒 Магазин")
async def admin_store(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_store"}
    await message.answer("🛒 Управление товарами — скоро здесь.", reply_markup=kb_admin_main())

# ---- Админ: Настройки ----
@dp.message_handler(lambda m: m.text == "⚙ Настройки")
async def admin_settings(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_settings"}
    await message.answer("⚙ Настройки админов:", reply_markup=kb_admin_settings())

@dp.message_handler(lambda m: m.text == "📃 Список администраторов")
async def admin_list_admins(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    sess = SessionLocal()
    try:
        rows = sess.execute(text("SELECT telegram_id FROM admins ORDER BY telegram_id ASC")).fetchall()
    finally:
        sess.close()
    ids = [str(r[0]) for r in rows]
    txt = "👑 Администраторы:\n" + ("\n".join(ids) if ids else "— пусто —")
    await message.answer(txt, reply_markup=kb_admin_settings())

@dp.message_handler(lambda m: m.text == "➕ Выдать администратора по коду")
async def admin_give_by_code(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_add_manual"}
    await message.answer("Введи Telegram ID пользователя для выдачи прав:", reply_markup=kb_back())

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

@dp.message_handler(lambda m: m.text == "➖ Удалить администратора")
async def admin_remove_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"screen": "admin_remove_manual"}
    await message.answer("Введи Telegram ID для удаления прав:", reply_markup=kb_back())

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
