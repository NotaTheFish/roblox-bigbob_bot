from datetime import datetime, timedelta

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.db import SessionLocal, PromoCode, Admin
from bot.keyboards.admin_keyboards import admin_main_menu_kb, promo_reward_type_kb
from bot.states.promo_states import PromoCreateState


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
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu"),
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
    promo_type = "money" if "money" in call.data else "item"
    await state.update_data(promo_type=promo_type)

    if promo_type == "money":
        await call.message.answer("💰 Введите сумму валюты для награды:")
    else:
        await call.message.answer("🎁 Введите ID Roblox-предмета:")

    await PromoCreateState.waiting_for_reward_value.set()


async def promo_set_reward_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    promo_type = data.get("promo_type", "money")

    if promo_type == "money":
        try:
            value = int(message.text)
        except ValueError:
            return await message.answer("Введите числовое значение")
    else:
        value = message.text.strip()
        if not value:
            return await message.answer("Введите значение награды")

    await state.update_data(value=value)
    await message.answer("📊 Введите лимит использований (число, 0 — без лимита):")
    await PromoCreateState.waiting_for_usage_limit.set()


async def promo_set_limit(message: types.Message, state: FSMContext):
    try:
        limit = int(message.text)
    except ValueError:
        return await message.answer("Введите ЧИСЛО")

    await state.update_data(max_uses=None if limit <= 0 else limit)
    await message.answer("⏳ На сколько дней действует промокод? (0 — без ограничения)")
    await PromoCreateState.waiting_for_expire_days.set()


async def promo_finish(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
    except ValueError:
        return await message.answer("Введите число дней")

    data = await state.get_data()

    expires_at = datetime.utcnow() + timedelta(days=days) if days > 0 else None

    with SessionLocal() as s:
        promo = PromoCode(
            code=data["code"],
            promo_type=data["promo_type"],
            value=data["value"],
            max_uses=data["max_uses"],
            uses=0,
            expires_at=expires_at,
        )
        s.add(promo)
        s.commit()

    await message.answer(
        f"✅ Промокод <code>{data['code']}</code> создан!",
        parse_mode="HTML",
    )
    await state.finish()


# ------------ Список промокодов ------------

async def promo_list(call: types.CallbackQuery):
    with SessionLocal() as s:
        promos = s.query(PromoCode).all()

    if not promos:
        return await call.message.edit_text(
            "📦 Промокодов нет.",
            reply_markup=admin_main_menu_kb(),
        )

    text = "🎫 <b>Активные промокоды:</b>\n\n"
    kb = InlineKeyboardMarkup()

    for p in promos:
        usage_info = f"{p.uses}/{p.max_uses}" if p.max_uses is not None else f"{p.uses}/∞"
        text += f"• <code>{p.code}</code> — {p.promo_type} ({usage_info})\n"
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


def register_admin_promo(dp: Dispatcher):
    dp.register_callback_query_handler(
        admin_promos_menu,
        lambda c: c.data == "admin_promos",
    )
    dp.register_callback_query_handler(
        promo_create_start,
        lambda c: c.data == "promo_create",
    )
    dp.register_message_handler(
        promo_set_code,
        state=PromoCreateState.waiting_for_code,
    )
    dp.register_callback_query_handler(
        promo_set_reward_type,
        lambda c: c.data.startswith("promo_reward"),
        state=PromoCreateState.waiting_for_reward_type,
    )
    dp.register_message_handler(
        promo_set_reward_value,
        state=PromoCreateState.waiting_for_reward_value,
    )
    dp.register_message_handler(
        promo_set_limit,
        state=PromoCreateState.waiting_for_usage_limit,
    )
    dp.register_message_handler(
        promo_finish,
        state=PromoCreateState.waiting_for_expire_days,
    )
    dp.register_callback_query_handler(
        promo_list,
        lambda c: c.data == "promo_list",
    )
    dp.register_callback_query_handler(
        promo_delete,
        lambda c: c.data.startswith("promo_del"),
    )
