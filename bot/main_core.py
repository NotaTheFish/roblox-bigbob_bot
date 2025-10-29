# bot/main_core.py

import random
import asyncio
from datetime import datetime, timedelta
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

# --- Временные состояния ---
# структура: user_states[user_id] = {"mode":"admin_servers", "step":"await_number", "payload": {...}}
user_states = {}

# --- Список админов (Telegram ID) ---
ADMIN_IDS = [5813380332, 1748138420]

# -----------------------------
# --- Пользовательские команды ---
# -----------------------------
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    session = SessionLocal()
    try:
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
    finally:
        session.close()

@dp.message_handler(commands=['verify'])
async def verify_cmd(message: types.Message):
    user_states[message.from_user.id] = {"mode": "verify", "step": "await_nick"}
    await message.answer("Напиши свой ник Roblox:")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "verify"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_nick")
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
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            # на всякий случай создаём
            user = User(telegram_id=user_id, verified=False)
            session.add(user)
            session.commit()

        if callback_query.data == "confirm_yes":
            nick = user_states.get(user_id, {}).get("nick")
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
    finally:
        session.close()
        await callback_query.answer()

@dp.message_handler(commands=['check'])
async def check_cmd(message: types.Message):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user or not user.roblox_user:
            await message.answer("❌ Сначала введи /verify и укажи ник")
            return

        # Здесь ты можешь реализовать реальную проверку через Roblox API — сейчас просто пометка.
        user.verified = True
        session.commit()

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Мой аккаунт", "Топ игроков")
        markup.add("Присоединиться к игре", "Войти в режим Админа")
        await message.answer("✅ Аккаунт подтверждён!\nВыбери действие:", reply_markup=markup)
    finally:
        session.close()

# -----------------------------
# --- Главное меню пользователя ---
# -----------------------------
@dp.message_handler(lambda msg: msg.text == "Мой аккаунт")
async def my_account(message: types.Message):
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user or not user.verified:
            await message.answer("❌ Аккаунт не подтверждён")
            return
        info = (
            f"👤 Ник: {user.roblox_user or '-'}\n"
            f"💰 Баланс: {getattr(user, 'balance', 0) or 0} орешков\n"
            f"💎 Кеш: {getattr(user, 'cash', 0) or 0}\n"
            f"📦 Предметы: {user.items or '-'}\n"
            f"🎮 Уровень: {getattr(user, 'level', 0) or 0}\n"
            f"⏱ Время в игре: {getattr(user, 'play_time', 0) or 0}\n"
            f"👥 Приглашённые: {getattr(user, 'referrals', 0) or 0}"
        )
        await message.answer(info)
    finally:
        session.close()

@dp.message_handler(lambda msg: msg.text == "Топ игроков")
async def top_players(message: types.Message):
    session = SessionLocal()
    try:
        top = session.query(User).order_by(User.level.desc()).limit(15).all()
        if not top:
            await message.answer("Нет игроков для отображения.")
            return
        text = "🏆 Топ 15 игроков:\n"
        for u in top:
            text += f"{u.roblox_user or '–'} — уровень {getattr(u, 'level', 0) or 0}\n"
        await message.answer(text)
    finally:
        session.close()

@dp.message_handler(lambda msg: msg.text == "Присоединиться к игре")
async def join_game(message: types.Message):
    session = SessionLocal()
    try:
        servers = session.query(Server).order_by(Server.number.asc()).all()
        if not servers:
            await message.answer("❌ Сервера не добавлены")
            return

        keyboard = InlineKeyboardMarkup()
        for s in servers:
            if s.link:
                # кнопка с URL — откроет Roblox
                keyboard.add(InlineKeyboardButton(f"Сервер {s.number}", url=s.link))
            else:
                keyboard.add(InlineKeyboardButton(f"Сервер {s.number} ❌", callback_data=f"server_closed_{s.number}"))
        await message.answer("Выбери сервер:", reply_markup=keyboard)
    finally:
        session.close()

@dp.callback_query_handler(lambda c: c.data.startswith("server_closed_"))
async def server_closed(callback_query: types.CallbackQuery):
    number = callback_query.data.split("_")[-1]
    await callback_query.answer(f"Сервер {number} закрыт")

# -----------------------------
# --- Режим Админа (главное меню) ---
# -----------------------------
@dp.message_handler(lambda msg: msg.text == "Войти в режим Админа")
async def enter_admin_mode(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ты не Админ")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Пользователи", "Сервера")
    markup.add("Промокоды", "Магазин")
    markup.add("Выйти из Админа")
    await message.answer("✅ Режим Админа активирован", reply_markup=markup)

# -----------------------------
# --- Админ: навигация и обработчики ---
# -----------------------------
# Пользователи: просмотреть всех / найти / дать бонус
@dp.message_handler(lambda msg: msg.text == "Пользователи")
async def admin_users_list(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ты не Админ")
        return

    session = SessionLocal()
    try:
        users = session.query(User).order_by(User.id.desc()).limit(100).all()
        if not users:
            await message.answer("Нет пользователей в базе.")
            return

        text = "👥 Пользователи (последние 100):\n"
        for u in users:
            text += f"{u.id}: {u.roblox_user or '-'} (TG: {u.telegram_id})\n"

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Найти пользователя", callback_data="admin_find_user"))
        keyboard.add(InlineKeyboardButton("Дать бонус", callback_data="admin_give_bonus"))
        # удаление — отдельными кнопками на каждый может быть тяжело; сделаем через поиск/ID
        await message.answer(text, reply_markup=keyboard)
    finally:
        session.close()

@dp.callback_query_handler(lambda c: c.data == "admin_find_user")
async def admin_find_user_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_states[admin_id] = {"mode": "admin_user_find", "step": "await_query"}
    await callback_query.message.answer("Введи Telegram ID или ник Roblox пользователя:")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_give_bonus")
async def admin_give_bonus_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_states[admin_id] = {"mode": "admin_give_bonus", "step": "await_user"}
    await callback_query.message.answer("Введи Telegram ID или ник Roblox пользователя, которому дать бонус:")
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_user_find"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_query")
async def admin_find_user_receive(message: types.Message):
    query = message.text.strip()
    session = SessionLocal()
    try:
        user = None
        if query.isdigit():
            user = session.query(User).filter_by(telegram_id=int(query)).first()
        if not user:
            user = session.query(User).filter_by(roblox_user=query).first()
        if not user:
            await message.answer("Пользователь не найден.")
        else:
            info = (
                f"ID: {user.id}\n"
                f"Telegram: {user.telegram_id}\n"
                f"Roblox: {user.roblox_user}\n"
                f"Баланс: {getattr(user,'balance',0)} орешков\n"
                f"Кеш: {getattr(user,'cash',0)}\n"
                f"Предметы: {user.items}\n"
                f"Уровень: {getattr(user,'level',0)}\n"
                f"Время: {getattr(user,'play_time',0)}\n"
                f"Рефералы: {getattr(user,'referrals',0)}"
            )
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Удалить пользователя", callback_data=f"admin_delete_user_{user.id}"))
            await message.answer(info, reply_markup=keyboard)
    finally:
        session.close()
        user_states.pop(message.from_user.id, None)

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_give_bonus"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_user")
async def admin_give_bonus_receive_user(message: types.Message):
    admin_id = message.from_user.id
    query = message.text.strip()
    session = SessionLocal()
    try:
        user = None
        if query.isdigit():
            user = session.query(User).filter_by(telegram_id=int(query)).first()
        if not user:
            user = session.query(User).filter_by(roblox_user=query).first()

        if not user:
            await message.answer("Пользователь не найден.")
            user_states.pop(admin_id, None)
            return

        user_states[admin_id]["target_user_id"] = user.id
        user_states[admin_id]["step"] = "await_amount"
        await message.answer("Укажи сумму в орешках для начисления (целое число):")
    finally:
        session.close()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_give_bonus"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_amount")
async def admin_give_bonus_receive_amount(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    try:
        amount = int(message.text.strip())
    except:
        await message.answer("Неверная сумма. Введи целое число.")
        return

    session = SessionLocal()
    try:
        user = session.query(User).filter_by(id=st["target_user_id"]).first()
        if not user:
            await message.answer("Пользователь не найден.")
        else:
            user.balance = (getattr(user, "balance", 0) or 0) + amount
            session.commit()
            await message.answer(f"✅ {amount} орешков начислено пользователю {user.roblox_user or user.telegram_id}.")
    finally:
        session.close()
        user_states.pop(admin_id, None)

@dp.callback_query_handler(lambda c: c.data.startswith("admin_delete_user_"))
async def admin_delete_user_confirm(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_id = int(callback_query.data.split("_")[-1])
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            await callback_query.answer("Пользователь не найден.")
            return
        session.delete(user)
        session.commit()
        await callback_query.answer(f"Пользователь {user.roblox_user or user.telegram_id} удалён.")
        await callback_query.message.answer(f"Пользователь {user.roblox_user or user.telegram_id} удалён из БД.")
    finally:
        session.close()

# -----------------------------
# --- Админ: Сервера (CRUD) ---
# -----------------------------
@dp.message_handler(lambda msg: msg.text == "Сервера")
async def admin_servers_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ты не Админ")
        return
    session = SessionLocal()
    try:
        servers = session.query(Server).order_by(Server.number.asc()).all()
        text = "🎮 Сервера:\n"
        for s in servers:
            text += f"{s.id}: Сервер {s.number} — {'🔗' if s.link else '❌'}\n"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Добавить сервер", callback_data="admin_add_server"))
        if servers:
            keyboard.add(InlineKeyboardButton("Удалить последний сервер", callback_data="admin_del_last_server"))
        await message.answer(text, reply_markup=keyboard)
    finally:
        session.close()

@dp.callback_query_handler(lambda c: c.data == "admin_add_server")
async def admin_add_server_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_states[admin_id] = {"mode": "admin_servers_add", "step": "await_number"}
    await callback_query.message.answer("Укажи номер сервера (целое число, например 1):")
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_servers_add"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_number")
async def admin_add_server_number(message: types.Message):
    admin_id = message.from_user.id
    try:
        number = int(message.text.strip())
    except:
        await message.answer("Неверный номер. Введи целое число.")
        return

    session = SessionLocal()
    try:
        exists = session.query(Server).filter_by(number=number).first()
        if exists:
            await message.answer("Сервер с таким номером уже есть.")
            user_states.pop(admin_id, None)
            return
        # добавляем заготовку сервера (без ссылки)
        new = Server(number=number, link=None)
        session.add(new)
        session.commit()
        await message.answer(f"Сервер {number} создан (без ссылки). Теперь можно добавить ссылку через 'Сервера' -> редактирование.")
    finally:
        session.close()
        user_states.pop(admin_id, None)

@dp.callback_query_handler(lambda c: c.data == "admin_del_last_server")
async def admin_delete_last_server(callback_query: types.CallbackQuery):
    session = SessionLocal()
    try:
        last = session.query(Server).order_by(Server.number.desc()).first()
        if not last:
            await callback_query.answer("Нет серверов для удаления.")
            return
        number = last.number
        session.delete(last)
        session.commit()
        await callback_query.answer(f"Последний сервер {number} удалён.")
        await callback_query.message.answer(f"Последний сервер {number} удалён.")
    finally:
        session.close()

# -----------------------------
# --- Админ: Промокоды (CRUD) ---
# -----------------------------
@dp.message_handler(lambda msg: msg.text == "Промокоды")
async def admin_promos_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ты не Админ")
        return
    session = SessionLocal()
    try:
        codes = session.query(PromoCode).order_by(PromoCode.id.desc()).all()
        text = "🎟 Промокоды:\n"
        for c in codes:
            expires = c.expires_at.strftime("%Y-%m-%d %H:%M") if c.expires_at else "—"
            maxu = "∞" if c.max_uses == 0 else str(c.max_uses)
            text += f"{c.id}: {c.code} | {c.type}={c.value} | used {c.uses}/{maxu} | exp {expires}\n"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Создать промокод", callback_data="admin_create_promo"))
        if codes:
            keyboard.add(InlineKeyboardButton("Удалить промокод", callback_data="admin_delete_promo"))
        await message.answer(text, reply_markup=keyboard)
    finally:
        session.close()

@dp.callback_query_handler(lambda c: c.data == "admin_create_promo")
async def admin_create_promo_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_states[admin_id] = {"mode": "admin_create_promo", "step": "await_type"}
    await callback_query.message.answer("Выбери тип промокода: напиши `cash` (кеш), `item` (предмет), `discount` (скидка в %), `admin` (доступ в админку).")
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_create_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_type")
async def admin_create_promo_type(message: types.Message):
    admin_id = message.from_user.id
    ptype = message.text.strip().lower()
    if ptype not in ("cash", "item", "discount", "admin"):
        await message.answer("Неверный тип. Выбери: cash, item, discount, admin.")
        return
    user_states[admin_id].update({"ptype": ptype, "step": "await_value"})
    await message.answer("Укажи значение:\n- cash: количество кеша (целое),\n- item: id предмета (целое),\n- discount: процент (целое),\n- admin: укажи 1 (игнорируется значение).")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_create_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_value")
async def admin_create_promo_value(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    try:
        value = int(message.text.strip())
    except:
        if st["ptype"] == "admin":
            value = 0
        else:
            await message.answer("Неверное значение. Введи целое число.")
            return

    st["value"] = value
    st["step"] = "await_max_uses"
    await message.answer("Укажи максимальное количество активаций (число) или 0 для неограниченно:")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_create_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_max_uses")
async def admin_create_promo_max_uses(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    try:
        max_uses = int(message.text.strip())
    except:
        await message.answer("Неверное значение. Введи целое число.")
        return
    st["max_uses"] = max_uses
    st["step"] = "await_expiry_type"
    await message.answer("Выбери срок действия: напиши `minutes`, `hours`, `days`, или `never`:")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_create_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_expiry_type")
async def admin_create_promo_expiry_type(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    choice = message.text.strip().lower()
    if choice not in ("minutes", "hours", "days", "never"):
        await message.answer("Неверный выбор. minutes/hours/days/never")
        return
    st["expiry_choice"] = choice
    if choice == "never":
        st["expires_at"] = None
        st["step"] = "await_code"
        await message.answer("Теперь введи сам промокод (например bigbob2025):")
        return
    st["step"] = "await_expiry_amount"
    await message.answer(f"Укажи количество {choice} (целое число):")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_create_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_expiry_amount")
async def admin_create_promo_expiry_amount(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    try:
        amount = int(message.text.strip())
    except:
        await message.answer("Неверное значение. Введи целое число.")
        return

    choice = st["expiry_choice"]
    now = datetime.utcnow()
    if choice == "minutes":
        expires = now + timedelta(minutes=amount)
    elif choice == "hours":
        expires = now + timedelta(hours=amount)
    else:
        expires = now + timedelta(days=amount)
    st["expires_at"] = expires
    st["step"] = "await_code"
    await message.answer("Теперь введи сам промокод (например bigbob2025):")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_create_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_code")
async def admin_create_promo_code(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    code = message.text.strip()
    session = SessionLocal()
    try:
        exists = session.query(PromoCode).filter_by(code=code).first()
        if exists:
            await message.answer("Промокод с таким кодом уже существует.")
            user_states.pop(admin_id, None)
            return
        promo = PromoCode(
            code=code,
            type=st["ptype"],
            value=st["value"],
            uses=0,
            max_uses=st["max_uses"],
            expires_at=st.get("expires_at")
        )
        session.add(promo)
        session.commit()
        await message.answer(f"Промокод {code} создан ✅")
    finally:
        session.close()
        user_states.pop(admin_id, None)

@dp.callback_query_handler(lambda c: c.data == "admin_delete_promo")
async def admin_delete_promo_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_states[admin_id] = {"mode": "admin_delete_promo", "step": "await_code"}
    await callback_query.message.answer("Введи код промокода для удаления:")
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_delete_promo"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_code")
async def admin_delete_promo_receive(message: types.Message):
    admin_id = message.from_user.id
    code = message.text.strip()
    session = SessionLocal()
    try:
        promo = session.query(PromoCode).filter_by(code=code).first()
        if not promo:
            await message.answer("Промокод не найден.")
            user_states.pop(admin_id, None)
            return
        session.delete(promo)
        session.commit()
        await message.answer(f"Промокод {code} удалён.")
    finally:
        session.close()
        user_states.pop(admin_id, None)

# -----------------------------
# --- Админ: Магазин (CRUD) ---
# -----------------------------
@dp.message_handler(lambda msg: msg.text == "Магазин")
async def admin_shop_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Ты не Админ")
        return
    session = SessionLocal()
    try:
        items = session.query(Item).order_by(Item.id.asc()).all()
        text = "🛒 Товары:\n"
        for i in items:
            text += f"{i.id}: {i.name} — {i.price} орешков — {'активен' if i.available else 'выключен'}\n"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Добавить товар", callback_data="admin_add_item"))
        if items:
            keyboard.add(InlineKeyboardButton("Удалить товар", callback_data="admin_del_item"))
        await message.answer(text, reply_markup=keyboard)
    finally:
        session.close()

@dp.callback_query_handler(lambda c: c.data == "admin_add_item")
async def admin_add_item_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    user_states[admin_id] = {"mode": "admin_add_item", "step": "await_name"}
    await callback_query.message.answer("Введи название товара:")
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_add_item"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_name")
async def admin_add_item_name(message: types.Message):
    admin_id = message.from_user.id
    name = message.text.strip()
    user_states[admin_id] = {"mode": "admin_add_item", "step": "await_price", "name": name}
    await message.answer("Укажи цену в орешках (целое число):")

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get("mode") == "admin_add_item"
                    and user_states.get(msg.from_user.id, {}).get("step") == "await_price")
async def admin_add_item_price(message: types.Message):
    admin_id = message.from_user.id
    st = user_states.get(admin_id)
    if not st:
        await message.answer("Сессия прервана.")
        return
    try:
        price = int(message.text.strip())
    except:
        await message.answer("Неверная цена. Введи целое число.")
        return
    session = SessionLocal()
    try:
        item = Item(name=st["name"], price=price, available=True)
        session.add(item)
        session.commit()
        await message.answer(f"Товар '{st['name']}' добавлен по цене {price} орешков.")
    finally:
        session.close()
        user_states.pop(admin_id, None)

@dp.callback_query_handler(lambda c: c.data == "admin_del_item")
async def admin_del_item_start(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    session = SessionLocal()
    try:
        items = session.query(Item).all()
        if not items:
            await callback_query.message.answer("Нет товаров для удаления.")
            await callback_query.answer()
            return
        keyboard = InlineKeyboardMarkup()
        for i in items:
            keyboard.add(InlineKeyboardButton(f"Удалить {i.name}", callback_data=f"admin_del_item_{i.id}"))
        await callback_query.message.answer("Выбери товар для удаления:", reply_markup=keyboard)
    finally:
        session.close()
        await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("admin_del_item_"))
async def admin_del_item_confirm(callback_query: types.CallbackQuery):
    item_id = int(callback_query.data.split("_")[-1])
    session = SessionLocal()
    try:
        item = session.query(Item).filter_by(id=item_id).first()
        if not item:
            await callback_query.answer("Товар не найден.")
            return
        session.delete(item)
        session.commit()
        await callback_query.answer(f"Товар {item.name} удалён.")
        await callback_query.message.answer(f"Товар {item.name} удалён из магазина.")
    finally:
        session.close()

# -----------------------------
# --- Flask endpoint для сервера Roblox ---
# -----------------------------
@app.route('/update_player', methods=["POST"])
def update_player():
    data = request.json
    try:
        session = SessionLocal()
        user = session.query(User).filter_by(roblox_user=data.get("username")).first()
        if user is None:
            # Автосоздание нового пользователя, если нужно
            user = User(
                telegram_id=None,
                roblox_user=data.get("username"),
                verified=False,
                balance=0,
                cash=data.get("cash", 0),
                items=data.get("items", ""),
                level=data.get("level", 0),
                play_time=data.get("play_time", 0),
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

# -----------------------------
# --- Webhook обработчик ---
# -----------------------------
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    # Получаем update от Telegram и передаем в aiogram
    update = types.Update.to_object(request.get_json(force=True))
    asyncio.create_task(dp.process_update(update))
    return "OK", 200

# -----------------------------
# --- Запуск вебхука ---
# -----------------------------
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
