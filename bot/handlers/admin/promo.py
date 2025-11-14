from __future__ import annotations

from datetime import datetime, timedelta
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.db import Admin, PromoCode, async_session
from bot.keyboards.admin_keyboards import (
    promo_management_menu_kb,
    promo_reward_type_kb,
    promo_step_navigation_kb,
)
from bot.states.promo_states import PromoCreateState


router = Router(name="admin_promo")


# ✅ Проверка администратора
async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


async def _is_valid_admin_message(message: types.Message) -> bool:
    return bool(message.from_user) and await is_admin(message.from_user.id)


async def _ensure_admin_callback(call: types.CallbackQuery) -> bool:
    if not call.from_user:
        return False

    if not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return False

    return True


# ✅ Меню промокодов для админа
@router.message(F.text == "🎟 Промокоды")
async def admin_promos_menu(message: types.Message):
    if not await _is_valid_admin_message(message):
        return

    await message.answer(
        "🎟 <b>Промокоды</b>\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=promo_management_menu_kb(),
    )


# ✅ Старт создания промокода
@router.callback_query(F.data == "promo:menu:create")
async def promo_create_start(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    await state.set_state(PromoCreateState.waiting_for_code)
    await call.message.answer(
        "📝 Введите название промокода, затем нажмите «Далее».",
        reply_markup=promo_step_navigation_kb("promo:create:next:code"),
    )
    await call.answer()


@router.callback_query(F.data == "promo:cancel")
async def promo_cancel(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    await state.clear()
    await call.message.answer(
        "Действие отменено.",
        reply_markup=promo_management_menu_kb(),
    )
    await call.answer("Отменено")


# ✅ Ввод кода промо
@router.message(StateFilter(PromoCreateState.waiting_for_code))
async def promo_set_code(message: types.Message, state: FSMContext):
    if not await _is_valid_admin_message(message):
        return

    code = (message.text or "").strip()
    if not code:
        await message.answer("Введите название промокода.")
        return

    await state.update_data(code=code.upper())
    await message.answer("Код сохранён. Нажмите «Далее», чтобы продолжить.")


@router.callback_query(F.data == "promo:create:next:code")
async def promo_ask_reward_type(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    if await state.get_state() != PromoCreateState.waiting_for_code:
        await call.answer("Этот шаг уже завершён.")
        return

    data = await state.get_data()
    if not data.get("code"):
        await call.answer("Сначала отправьте название промокода.", show_alert=True)
        return

    await state.set_state(PromoCreateState.waiting_for_reward_type)
    await call.message.answer(
        "Выберите тип награды и нажмите «Далее».",
        reply_markup=promo_reward_type_kb(),
    )
    await call.answer()


# ✅ Выбор типа награды
@router.callback_query(
    F.data.in_({"promo:create:type:money", "promo:create:type:item"})
)
async def promo_select_reward_type(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    if await state.get_state() != PromoCreateState.waiting_for_reward_type:
        await call.answer("Этот шаг уже завершён.")
        return

    promo_type = "money" if call.data.endswith("money") else "item"
    await state.update_data(promo_type=promo_type)
    await call.answer("Тип награды выбран. Нажмите «Далее».")


@router.callback_query(F.data == "promo:create:next:reward_type")
async def promo_reward_type_next(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    if await state.get_state() != PromoCreateState.waiting_for_reward_type:
        await call.answer("Шаг уже завершён.")
        return

    data = await state.get_data()
    promo_type = data.get("promo_type")
    if not promo_type:
        await call.answer("Сначала выберите тип награды.", show_alert=True)
        return

    await state.set_state(PromoCreateState.waiting_for_reward_value)
    if promo_type == "money":
        prompt = "💰 Введите сумму валюты для награды, затем нажмите «Далее»."
    else:
        prompt = "🎁 Введите ID Roblox-предмета, затем нажмите «Далее»."

    await call.message.answer(
        prompt,
        reply_markup=promo_step_navigation_kb("promo:create:next:value"),
    )
    await call.answer()


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
    await message.answer("Нажмите «Далее», чтобы перейти к лимиту использований.")


@router.callback_query(F.data == "promo:create:next:value")
async def promo_next_to_limit(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    if await state.get_state() != PromoCreateState.waiting_for_reward_value:
        await call.answer("Шаг уже завершён.")
        return

    data = await state.get_data()
    if not data.get("value"):
        await call.answer("Сначала отправьте значение награды.", show_alert=True)
        return

    await state.set_state(PromoCreateState.waiting_for_usage_limit)
    await call.message.answer(
        "📊 Введите лимит использований (число, 0 — без ограничения) и нажмите «Далее».",
        reply_markup=promo_step_navigation_kb("promo:create:next:limit"),
    )
    await call.answer()


# ✅ Ввод лимита
@router.message(StateFilter(PromoCreateState.waiting_for_usage_limit))
async def promo_set_limit(message: types.Message, state: FSMContext):
    try:
        limit = int(message.text)
    except ValueError:
        return await message.answer("Введите ЧИСЛО")

    await state.update_data(max_uses=None if limit <= 0 else limit)
    await message.answer("Лимит сохранён. Нажмите «Далее», чтобы продолжить.")


@router.callback_query(F.data == "promo:create:next:limit")
async def promo_next_to_expire(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    if await state.get_state() != PromoCreateState.waiting_for_usage_limit:
        await call.answer("Шаг уже завершён.")
        return

    data = await state.get_data()
    if "max_uses" not in data:
        await call.answer("Сначала укажите лимит использований.", show_alert=True)
        return

    await state.set_state(PromoCreateState.waiting_for_expire_days)
    await call.message.answer(
        "⏳ На сколько дней действует промокод? (0 — без ограничения) и нажмите «Далее».",
        reply_markup=promo_step_navigation_kb("promo:create:next:finish"),
    )
    await call.answer()


# ✅ Завершение создания
@router.message(StateFilter(PromoCreateState.waiting_for_expire_days))
async def promo_finish(message: types.Message, state: FSMContext):
    if not await _is_valid_admin_message(message):
        return

    try:
        days = int(message.text)
    except ValueError:
        return await message.answer("Введите число дней")

    await state.update_data(expire_days=days)
    await message.answer("Срок действия сохранён. Нажмите «Далее», чтобы завершить.")


@router.callback_query(F.data == "promo:create:next:finish")
async def promo_finalize(call: types.CallbackQuery, state: FSMContext):
    if not await _ensure_admin_callback(call):
        return

    if await state.get_state() != PromoCreateState.waiting_for_expire_days:
        await call.answer("Шаг уже завершён.")
        return

    data = await state.get_data()
    if "expire_days" not in data:
        await call.answer("Сначала отправьте срок действия.", show_alert=True)
        return

    days = data["expire_days"]
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

    await state.clear()
    await call.message.answer(
        f"✅ Промокод <code>{data['code']}</code> создан!\n"
        "💬 Подскажите игрокам: «Введите код прямо в чат».",
        parse_mode="HTML",
        reply_markup=promo_management_menu_kb(),
    )
    await call.answer("Промокод создан")


# ✅ Список промокодов
async def _build_promo_list(
    with_delete_buttons: bool = True,
) -> tuple[str | None, types.InlineKeyboardMarkup | None]:
    async with async_session() as session:
        promos = (await session.scalars(select(PromoCode))).all()

    if not promos:
        return None, None

    text = "🎫 <b>Активные промокоды:</b>\n\n"
    builder = InlineKeyboardBuilder() if with_delete_buttons else None

    for promo in promos:
        usage_info = (
            f"{promo.uses}/{promo.max_uses}"
            if promo.max_uses is not None else f"{promo.uses}/∞"
        )
        text += f"• <code>{promo.code}</code> — {promo.promo_type} ({usage_info})\n"
        if builder is not None:
            builder.button(
                text=f"❌ {promo.code}", callback_data=f"promo_del:{promo.id}"
            )

    reply_markup = builder.as_markup() if builder and builder.export() else None
    return text, reply_markup


@router.callback_query(F.data == "promo:menu:list")
async def promo_list(call: types.CallbackQuery):
    if not await _ensure_admin_callback(call):
        return

    text, _ = await _build_promo_list(with_delete_buttons=False)

    if not text:
        await call.message.answer(
            "📦 Промокодов нет.",
            reply_markup=promo_management_menu_kb(),
        )
    else:
        await call.message.answer(
            text,
            parse_mode="HTML",
        )
        await call.message.answer(
            "Выберите следующее действие:",
            reply_markup=promo_management_menu_kb(),
        )

    await call.answer()


@router.callback_query(F.data == "promo:menu:delete")
async def promo_delete_menu(call: types.CallbackQuery):
    if not await _ensure_admin_callback(call):
        return

    text, reply_markup = await _build_promo_list(with_delete_buttons=True)

    if not text:
        await call.message.answer(
            "📦 Промокодов нет.",
            reply_markup=promo_management_menu_kb(),
        )
    else:
        await call.message.answer(
            text + "\nНажмите на промокод ниже, чтобы удалить его.",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    await call.answer()


# ✅ Удаление промокода
@router.callback_query(F.data.startswith("promo_del"))
async def promo_delete(call: types.CallbackQuery):
    if not await _ensure_admin_callback(call):
        return

    promo_id = int(call.data.split(":")[1])

    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if promo:
            await session.delete(promo)
            await session.commit()

    text, reply_markup = await _build_promo_list(with_delete_buttons=True)

    if text:
        await call.message.edit_text(
            text + "\nНажмите на промокод ниже, чтобы удалить его.",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    else:
        await call.message.edit_text("📦 Промокодов нет.")
        await call.message.answer(
            "Выберите следующее действие:",
            reply_markup=promo_management_menu_kb(),
        )

    await call.answer("✅ Удалено")
