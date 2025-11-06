from __future__ import annotations

from datetime import datetime, timedelta
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.db import Admin, PromoCode, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb, promo_reward_type_kb
from bot.states.promo_states import PromoCreateState


router = Router(name="admin_promo")


# ✅ Проверка администратора
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# ✅ Меню промокодов для админа
@router.callback_query(F.data == "admin_promos")
async def admin_promos_menu(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать промокод", callback_data="promo_create")
    builder.button(text="📄 Список промокодов", callback_data="promo_list")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    reply_markup = builder.as_markup() if builder.export() else None

    await call.message.edit_text(
        "🎁 <b>Промокоды</b>\nВыберите действие:",
        **({"reply_markup": reply_markup} if reply_markup else {}),
    )


# ✅ Старт создания промокода
@router.callback_query(F.data == "promo_create")
async def promo_create_start(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    await call.message.answer("📝 Введите название промокода:")
    await state.set_state(PromoCreateState.waiting_for_code)


# ✅ Ввод кода промо
@router.message(StateFilter(PromoCreateState.waiting_for_code))
async def promo_set_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.upper())
    await message.answer("Выберите тип награды:", reply_markup=promo_reward_type_kb())
    await state.set_state(PromoCreateState.waiting_for_reward_type)


# ✅ Выбор типа награды
@router.callback_query(
    StateFilter(PromoCreateState.waiting_for_reward_type),
    F.data.startswith("promo_reward"),
)
async def promo_set_reward_type(call: types.CallbackQuery, state: FSMContext):
    promo_type = "money" if "money" in call.data else "item"
    await state.update_data(promo_type=promo_type)

    if promo_type == "money":
        await call.message.answer("💰 Введите сумму валюты для награды:")
    else:
        await call.message.answer("🎁 Введите ID Roblox-предмета:")

    await state.set_state(PromoCreateState.waiting_for_reward_value)


# ✅ Ввод значения награды
@router.message(StateFilter(PromoCreateState.waiting_for_reward_value))
async def promo_set_reward_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    promo_type = data.get("promo_type", "money")

    if promo_type == "money":
        try:
            reward_amount = int(message.text)
        except ValueError:
            return await message.answer("Введите ЧИСЛО")
        value = str(reward_amount)
    else:
        value = message.text.strip()
        if not value:
            return await message.answer("Введите значение награды")
        reward_amount = 0

    await state.update_data(value=value, reward_amount=reward_amount)
    await message.answer("📊 Введите лимит использований (число, 0 — без ограничения):")
    await state.set_state(PromoCreateState.waiting_for_usage_limit)


# ✅ Ввод лимита
@router.message(StateFilter(PromoCreateState.waiting_for_usage_limit))
async def promo_set_limit(message: types.Message, state: FSMContext):
    try:
        limit = int(message.text)
    except ValueError:
        return await message.answer("Введите ЧИСЛО")

    await state.update_data(max_uses=None if limit <= 0 else limit)
    await message.answer("⏳ На сколько дней действует промокод? (0 — без ограничения)")
    await state.set_state(PromoCreateState.waiting_for_expire_days)


# ✅ Завершение создания
@router.message(StateFilter(PromoCreateState.waiting_for_expire_days))
async def promo_finish(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
    except ValueError:
        return await message.answer("Введите число дней")

    data = await state.get_data()
    expires_at = datetime.utcnow() + timedelta(days=days) if days > 0 else None

    async with async_session() as session:
        promo = PromoCode(
            code=data["code"],
            promo_type=data["promo_type"],
            value=data["value"],
            reward_amount=data.get("reward_amount", 0),
            reward_type="balance" if data["promo_type"] == "money" else "item",
            max_uses=data.get("max_uses"),
            uses=0,
            expires_at=expires_at,
            active=True,
        )
        session.add(promo)
        await session.commit()

    await message.answer(f"✅ Промокод <code>{data['code']}</code> создан!", parse_mode="HTML")
    await state.clear()


# ✅ Список промокодов
@router.callback_query(F.data == "promo_list")
async def promo_list(call: types.CallbackQuery):
    async with async_session() as session:
        promos = (await session.scalars(select(PromoCode))).all()

    if not promos:
        return await call.message.edit_text(
            "📦 Промокодов нет.",
            reply_markup=admin_main_menu_kb(),
        )

    text = "🎫 <b>Активные промокоды:</b>\n\n"
    builder = InlineKeyboardBuilder()

    for promo in promos:
        usage_info = (
            f"{promo.uses}/{promo.max_uses}"
            if promo.max_uses is not None else f"{promo.uses}/∞"
        )
        text += f"• <code>{promo.code}</code> — {promo.promo_type} ({usage_info})\n"
        builder.button(
            text=f"❌ {promo.code}", callback_data=f"promo_del:{promo.id}"
        )

    builder.button(text="⬅️ Назад", callback_data="admin_promos")
    reply_markup = builder.as_markup() if builder.export() else None
    await call.message.edit_text(
        text,
        **({"reply_markup": reply_markup} if reply_markup else {}),
    )


# ✅ Удаление промокода
@router.callback_query(F.data.startswith("promo_del"))
async def promo_delete(call: types.CallbackQuery):
    promo_id = int(call.data.split(":")[1])

    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if promo:
            await session.delete(promo)
            await session.commit()

    await call.answer("✅ Удалено")
    await promo_list(call)
