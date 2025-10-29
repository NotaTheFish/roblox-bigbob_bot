# bot/main_core.py
# aiogram v2.25.1

import random
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ParseMode, CallbackQuery
)

from bot.config import TOKEN
from bot.db import SessionLocal, User, Server, PromoCode, Item

# -----------------------
#   Инициализация бота
# -----------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# -----------------------
#   Константы и состояния
# -----------------------
ADMIN_IDS = [5813380332, 1748138420]

# user_states: хранит “экран” и временные данные.
# Примеры:
#   user_states[user_id] = {"screen": "main"}
#   user_states[user_id] = {"screen": "account"}
#   user_states[user_id] = {"screen": "shop"}
#   user_states[user_id] = {"screen": "admin"}
#   user_states[user_id] = {"screen": "await_nick"}
#   user_states[user_id] = {"screen": "admin_servers"} ...
user_states: Dict[int, Dict[str, Any]] = {}

# ---------- Roblox verification helpers ----------
import json, requests, concurrent.futures

HTTP_TIMEOUT = 8  # секунд
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def _blocking_fetch_user_id(username: str) -> Optional[int]:
    """
    Запрашивает users.roblox.com/v1/usernames/users (POST) -> userId по нику.
    """
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data.get("data"):
        return None
    entry = data["data"][0]
    return entry.get("id")

def _blocking_fetch_description(user_id: int) -> Optional[str]:
    """
    Запрашивает users.roblox.com/v1/users/{userId} -> description.
    """
    url = f"https://users.roblox.com/v1/users/{user_id}"
    r = requests.get(url, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data.get("description")

async def fetch_roblox_description(username: str) -> Optional[str]:
    """
    Асинхронная оболочка над блокирующими requests.
    """
    loop = asyncio.get_event_loop()
    user_id = await loop.run_in_executor(_executor, _blocking_fetch_user_id, username)
    if not user_id:
        return None
    desc = await loop.run_in_executor(_executor, _blocking_fetch_description, user_id)
    return desc


# -----------------------
#   Вспомогательные клавиатуры (Reply)
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
    kb.row(KeyboardButton("↩️ Выйти в режим пользователя"))
    return kb

def kb_admin_servers() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Добавить сервер"), KeyboardButton("➖ Удалить последний сервер"))
    kb.row(KeyboardButton("🔗 Управление ссылками серверов"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    return kb

# -----------------------
#   Утилиты
# -----------------------
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

# -----------------------
#   Команды: старт / verify / check
# -----------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user = ensure_user_in_db(message.from_user.id)
    user_states[message.from_user.id] = {"screen": "main"}
    await message.answer(
        "👋 Привет! Я помогу тебе войти на приватные сервера Roblox.\n"
        "Нажми «⚡ Играть», либо зайди в «💼 Аккаунт».",
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
    kb.add(InlineKeyboardButton("Да ✅", callback_data="nick_yes"))
    kb.add(InlineKeyboardButton("Нет ❌", callback_data="nick_no"))
    await message.answer(f"Проверим: это твой ник в Roblox?\n\n<b>{nick}</b>", reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query_handler(lambda c: c.data in ("nick_yes", "nick_no"))
async def cb_confirm_nick(call: CallbackQuery):
    uid = call.from_user.id
    state = user_states.get(uid, {})
    if call.data == "nick_no":
        user_states[uid] = {"screen": "await_nick"}
        await call.message.edit_text("Окей, введи ник ещё раз ✍️")
        return await call.answer()

    # nick_yes
    nick = state.get("nick")
    code = str(random.randint(10000, 99999))

    # Сохраняем в БД
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=uid).first()
    if user:
        user.roblox_user = nick
        # сохраним код в поле items как временное место (или добавь поле code в БД)
        # лучше: добавь в модель User поле code = Column(String, nullable=True)
        try:
            setattr(user, "code", code)  # на случай если поле уже добавлено
        except Exception:
            pass
        user.verified = False
        session.commit()
    session.close()

    await call.message.edit_text(
        "✅ Супер! Сгенерирован код подтверждения.\n"
        f"Добавь в описание профиля Roblox этот код:\n\n<code>{code}</code>\n\n"
        "После этого нажми /check — бот проверит и даст доступ.",
        parse_mode=ParseMode.HTML
    )
    user_states[uid] = {"screen": "main"}
    await call.answer()

@dp.message_handler(commands=['check'])
async def cmd_check(message: types.Message):
    """
    Реальная верификация:
    1) Берём из БД ник и код
    2) Показываем "Проверяю…"
    3) Через Roblox API получаем описание профиля
    4) Ищем код в описании (без учёта регистра/пробелов)
    """
    session = SessionLocal()
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user or not user.roblox_user:
        session.close()
        return await message.answer("❌ Сначала сделай /verify и укажи ник.")

    # достанем код; если поля code нет — попытаемся вытащить из items как fallback
    user_code = getattr(user, "code", None)
    if not user_code or not str(user_code).strip():
        # если совсем нет — предложим перепройти verify
        session.close()
        return await message.answer("❌ Код подтверждения не найден. Сначала сделай /verify.")

    # индикатор
    status_msg = await message.answer("🔍 Проверяю Roblox профиль...")

    try:
        description = await fetch_roblox_description(user.roblox_user.strip())
    except requests.HTTPError as e:
        await status_msg.edit_text(
            "⚠️ Roblox API ответил ошибкой. Попробуй позже."
        )
        session.close()
        return
    except requests.RequestException:
        await status_msg.edit_text(
            "⚠️ Нет связи с Roblox API. Попробуй ещё раз чуть позже."
        )
        session.close()
        return

    if description is None:
        # ник не найден или профиль недоступен
        await status_msg.edit_text(
            "❌ Профиль не найден или временно недоступен.\n"
            "Проверь правильность ника и попробуй ещё раз."
        )
        session.close()
        return

    # дружелюбное предупреждение на закрытый/пустой профиль
    if not description.strip():
        await status_msg.edit_text(
            "⚠️ Твой Roblox профиль закрыт или в нём пустое описание.\n"
            "Пожалуйста, временно открой профиль и добавь код в «О нас», затем сделай /check снова."
        )
        session.close()
        return

    # Поиск кода (без регистра и с очисткой пробелов)
    haystack = description.replace(" ", "").lower()
    needle = str(user_code).replace(" ", "").lower()

    if needle and needle in haystack:
        user.verified = True
        # по желанию можно обнулить код, чтобы один раз использовать
        # user.code = None
        session.commit()
        session.close()

        await status_msg.edit_text("✅ Аккаунт подтверждён! Доступ открыт.")
        await message.answer("🏠 Главное меню", reply_markup=kb_main())
        user_states[message.from_user.id] = {"screen": "main"}
    else:
        session.close()
        await status_msg.edit_text(
            "❌ Код не найден в описании твоего профиля.\n"
            "Убедись, что вставил правильный код в «О нас» и профиль открыт, затем сделай /check ещё раз."
        )

# -----------------------
#   Главное меню (Reply)
# -----------------------
@dp.message_handler(lambda m: m.text == "⚡ Играть")
async def menu_play(message: types.Message):
    # Покажем доступные сервера (Inline, с линками)
    session = SessionLocal()
    servers = session.query(Server).order_by(Server.number.asc()).all()
    session.close()

    if not servers:
        return await message.answer("❌ Сервера ещё не добавлены.", reply_markup=kb_main())

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

@dp.message_handler(lambda m: m.text == "💼 Аккаунт")
async def menu_account(message: types.Message):
    user_states[message.from_user.id] = {"screen": "account"}
    # Выведем краткую инфу
    session = SessionLocal()
    u = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    session.close()
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

@dp.message_handler(lambda m: m.text == "💰 Баланс")
async def account_balance(message: types.Message):
    session = SessionLocal()
    u = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    session.close()
    bal = u.balance if u else 0
    await message.answer(f"💰 Твой баланс: <b>{bal}</b> орешков.", parse_mode=ParseMode.HTML, reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "💸 Пополнить баланс")
async def account_topup(message: types.Message):
    await message.answer(
        "💳 Пополнение в разработке.\n"
        "Скоро добавим EUR/UAH/RUB/crypto и автозачёт.",
        reply_markup=kb_account()
    )

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
    # Простая заглушка применения
    session = SessionLocal()
    promo = session.query(PromoCode).filter_by(code=code).first()
    u = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not promo:
        session.close()
        return await message.answer("❌ Промокод не найден.", reply_markup=kb_account())

    # Примитив: 1 активация списком
    if promo.max_uses is not None and promo.uses >= promo.max_uses:
        session.close()
        return await message.answer("⌛ Промокод исчерпан.", reply_markup=kb_account())

    # Начислим орешки, если тип discount/value — для примера
    if promo.promo_type in ("discount", "value"):
        u.balance += promo.value or 0

    promo.uses += 1
    session.commit()
    session.close()

    user_states[message.from_user.id] = {"screen": "account"}
    await message.answer("✅ Промокод применён!", reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "👥 Реферальная программа")
async def account_ref(message: types.Message):
    uid = message.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={uid}"
    await message.answer(
        "Приглашай друзей и получай бонусы!\n"
        f"🔗 Твоя реф-ссылка: {ref_link}",
        reply_markup=kb_account()
    )

@dp.message_handler(lambda m: m.text == "🏆 Топ игроков")
async def account_top(message: types.Message):
    session = SessionLocal()
    top = session.query(User).order_by(User.level.desc()).limit(15).all()
    session.close()
    text = "🏆 Топ 15 игроков:\n"
    for u in top:
        text += f"• {u.roblox_user or '—'} — уровень {u.level}\n"
    await message.answer(text, reply_markup=kb_account())

@dp.message_handler(lambda m: m.text == "💰 Донат-меню")
async def menu_shop(message: types.Message):
    user_states[message.from_user.id] = {"screen": "shop"}
    await message.answer("🛒 Магазин:", reply_markup=kb_shop())

@dp.message_handler(lambda m: m.text in ("💸 Купить кеш", "🛡 Купить привилегию", "🎒 Купить предмет"))
async def shop_items(message: types.Message):
    await message.answer("🧱 Раздел в разработке. Здесь появятся товары с гибкой настройкой.", reply_markup=kb_shop())

@dp.message_handler(lambda m: m.text == "🔙 Назад")
async def go_back(message: types.Message):
    # Возврат на уровень выше по текущему экрану
    screen = user_states.get(message.from_user.id, {}).get("screen", "main")
    if screen in ("account", "shop"):
        await show_main_menu(message.chat.id)
    elif screen in ("admin", "admin_users", "admin_servers", "admin_promos", "admin_store"):
        # назад из админских экранов → админ-меню
        user_states[message.from_user.id] = {"screen": "admin"}
        await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    else:
        await show_main_menu(message.chat.id)

# -----------------------
#   Админка
# -----------------------
@dp.message_handler(lambda m: m.text == "👑 Админ-панель")
async def enter_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: m.text == "↩️ Выйти в режим пользователя")
async def leave_admin(message: types.Message):
    await show_main_menu(message.chat.id)

@dp.message_handler(lambda m: m.text == "🖥 Сервера")
async def admin_servers(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Доступ запрещён.")
    user_states[message.from_user.id] = {"screen": "admin_servers"}
    await message.answer("🖥 Управление серверами:", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "➕ Добавить сервер")
async def admin_add_server(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    session = SessionLocal()
    last = session.query(Server).order_by(Server.number.desc()).first()
    next_num = (last.number + 1) if last else 1
    s = Server(number=next_num, link=None, closed_message="Сервер закрыт")
    session.add(s)
    session.commit()
    session.close()
    await message.answer(f"✅ Добавлен сервер {next_num}.", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "➖ Удалить последний сервер")
async def admin_del_last_server(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    session = SessionLocal()
    last = session.query(Server).order_by(Server.number.desc()).first()
    if not last:
        session.close()
        return await message.answer("❌ Нет серверов для удаления.", reply_markup=kb_admin_servers())
    session.delete(last)
    session.commit()
    session.close()
    await message.answer(f"🗑 Удалён сервер {last.number}.", reply_markup=kb_admin_servers())

@dp.message_handler(lambda m: m.text == "🔗 Управление ссылками серверов")
async def admin_server_links(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    # Выбор сервера (inline)
    session = SessionLocal()
    servers = session.query(Server).order_by(Server.number.asc()).all()
    session.close()
    if not servers:
        return await message.answer("Сервера отсутствуют.", reply_markup=kb_admin_servers())
    kb = InlineKeyboardMarkup()
    for s in servers:
        kb.add(InlineKeyboardButton(f"Сервер {s.number}", callback_data=f"pick_srv:{s.id}"))
    await message.answer("Выбери сервер для управления ссылкой:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("pick_srv:"))
async def cb_pick_server(call: CallbackQuery):
    srv_id = int(call.data.split(":")[1])
    # Сохраним выбранный сервер в state
    user_states[call.from_user.id] = {"screen": "admin_srv_edit", "srv_id": srv_id}
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📎 Добавить ссылку"), KeyboardButton("❌ Удалить ссылку"))
    kb.row(KeyboardButton("🔙 Назад (в админ-меню)"))
    await call.message.edit_text("Действие с выбранным сервером:", reply_markup=None)
    await bot.send_message(call.from_user.id, "Выбери действие:", reply_markup=kb)
    await call.answer()

@dp.message_handler(lambda m: m.text in ("📎 Добавить ссылку", "❌ Удалить ссылку"))
async def admin_srv_link_action(message: types.Message):
    state = user_states.get(message.from_user.id, {})
    if state.get("screen") != "admin_srv_edit":
        return
    if message.text == "📎 Добавить ссылку":
        user_states[message.from_user.id]["screen"] = "admin_srv_add_link"
        await message.answer("Вставь ссылку Roblox (формат из твоего примера):", reply_markup=kb_back())
    else:
        # Удалить
        session = SessionLocal()
        srv = session.query(Server).filter_by(id=state["srv_id"]).first()
        if not srv:
            session.close()
            return await message.answer("Сервер не найден.", reply_markup=kb_admin_main())
        srv.link = None
        session.commit()
        session.close()
        # Вернёмся в выбор действия
        user_states[message.from_user.id] = {"screen": "admin"}
        await message.answer("🗑 Ссылка удалена.", reply_markup=kb_admin_main())

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get("screen") == "admin_srv_add_link")
async def admin_srv_add_link(message: types.Message):
    if message.text == "🔙 Назад":
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())

    link = message.text.strip()
    # Сохраняем
    state = user_states.get(message.from_user.id, {})
    srv_id = state.get("srv_id")
    if not srv_id:
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("❌ Контекст сервера потерян.", reply_markup=kb_admin_main())

    session = SessionLocal()
    srv = session.query(Server).filter_by(id=srv_id).first()
    if not srv:
        session.close()
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("❌ Сервер не найден.", reply_markup=kb_admin_main())

    srv.link = link
    session.commit()
    session.close()

    user_states[message.from_user.id] = {"screen": "admin"}
    await message.answer("✅ Ссылка добавлена!", reply_markup=kb_admin_main())

# -----------------------
#   Общий “catch-back”
# -----------------------
@dp.message_handler()
async def fallback(message: types.Message):
    text = message.text or ""
    if text == "🔙 Назад (в админ-меню)":
        user_states[message.from_user.id] = {"screen": "admin"}
        return await message.answer("👑 Админ-панель", reply_markup=kb_admin_main())
    # По умолчанию — главное меню
    await show_main_menu(message.chat.id)
