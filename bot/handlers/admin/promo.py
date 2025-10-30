from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.states.promo_states import PromoCreateState
from bot.keyboards.admin_keyboards import admin_main_menu_kb, promo_reward_type_kb
from bot.db import SessionLocal, PromoCode, Admin
from bot.main_core import bot


def is_admin(uid: int) -> bool:
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())


# ------------ Админ: меню промокодов ------------

async def admin_promos_menu(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Создать промокод", callback_data="promo_create"),
        InlineKeyboardButton("📄 Список промокодов", callback_data="promo_list"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")
    )

    await call.message.edit_text("🎁 <b>Промокоды</b>\nВыберите действие:", reply_markup=kb)


# ------------ Создание промокода ------------

async def promo_create_start(call: types.CallbackQuery):
    await call.message.answer("📝 Введите название промокода:")
    await PromoCreateState.waiting_for_code.set()


async def promo_set_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.upper())
    await message.answer("Выберите тип награды:", reply_markup=promo_reward_type_kb())
    await PromoCreateState.waiting_for_reward_type.set()


async def promo_set_reward_type(call: types.CallbackQuery, state: FSMContext):
    reward_type = "money" if "money" in call.data else "item"
    await state.update_data(reward_type=reward_type)

    if reward_type == "money":
        await call.message.answer("💰 Введите сумму валюты для награды:")
    else:
        await call.message.answer("🎁 Введите ID Roblox-предмета:")

    await PromoCreateState.waiting_for_reward_value.set()


async def promo_set_reward_value(message: types.Message, state: FSMContext):
    await state.update_data(reward_value=message.text)
    await message.answer("📊 Введите лимит использований (число):")
    await PromoCreateState.waiting_for_usage_limit.set()


async def promo_set_limit(message: types.Message, state: FSMContext):
    try:
        limit = int(message.text)
    except:
        return await message.answer("Введите ЧИСЛО")

    await state.update_data(limit=limit)
    await message.answer("⏳ На сколько дней действует промокод?")
    await PromoCreateState.waiting_for_expire_days.set()


async def promo_finish(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
    except:
        return await message.answer("Введите число дней")

    data = await state.get_data()

    with SessionLocal() as s:
        promo = PromoCode(
            code=data["code"],
            reward_type=data["reward_type"],
            reward_value=data["reward_value"],
            usage_limit=data["limit"],
            used_count=0,
            expire_days=days
        )
        s.add(promo)
        s.commit()

    await message.answer(f"✅ Промокод <code>{data['code']}</code> создан!", parse_mode="HTML")
    await state.finish()


# ------------ Список промокодов ------------

async def promo_list(call: types.CallbackQuery):
    with SessionLocal() as s:
        promos = s.query(PromoCode).all()

    if not promos:
        return await call.message.edit_text("📦 Промокодов нет.", reply_markup=admin_main_menu_kb())

    text = "🎫 <b>Активные промокоды:</b>\n\n"
    kb = InlineKeyboardMarkup()

    for p in promos:
        text += f"• <code>{p.code}</code> — {p.reward_type} ({p.used_count}/{p.usage_limit})\n"
        kb.add(InlineKeyboardButton(f"❌ {p.code}", callback_data=f"promo_del:{p.id}"))

    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_promos"))
    await call.message.edit_text(text, reply_markup=kb)


# ------------ Удаление ------------

async def promo_delete(call: types.CallbackQuery):
    promo_id = int(call.data.split(":")[1])

    with SessionLocal() as s:
        promo = s.query(PromoCode).filter_by(id=promo_id).first()
        if promo:
            s.delete(promo)
            s.commit()

    await call.answer("Удалено ✅")
    await promo_list(call)


def register_admin_promos(dp: Dispatcher):
    dp.register_callback_query_handler(admin_promos_menu, lambda c: c.data == "admin_promos")
    dp.register_callback_query_handler(promo_create_start, lambda c: c.data == "promo_create")
    dp.register_message_handler(promo_set_code, state=PromoCreateState.waiting_for_code)
    dp.register_callback_query_handler(promo_set_reward_type, lambda c: c.data.startswith("promo_reward"), state=PromoCreateState.waiting_for_reward_type)
    dp.register_message_handler(promo_set_reward_value, state=PromoCreateState.waiting_for_reward_value)
    dp.register_message_handler(promo_set_limit, state=PromoCreateState.waiting_for_usage_limit)
    dp.register_message_handler(promo_finish, state=PromoCreateState.waiting_for_expire_days)
    dp.register_callback_query_handler(promo_list, lambda c: c.data == "promo_list")
    dp.register_callback_query_handler(promo_delete, lambda c: c.data.startswith("promo_del"))
