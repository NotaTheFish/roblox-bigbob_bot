from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import LogEntry, TopUpRequest, User, async_session
from bot.keyboards.user_keyboards import payment_methods_kb
from bot.states.user_states import TopUpState


router = Router(name="user_balance")


@router.message(Command("topup", "balance"))
async def topup_start(message: types.Message, state: FSMContext):
    await message.answer("Выберите способ оплаты:", reply_markup=payment_methods_kb())
    await state.set_state(TopUpState.waiting_for_method)


@router.callback_query(F.data == "pay_cancel", StateFilter(TopUpState.waiting_for_method))
async def topup_cancel(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("❌ Отменено")
    await state.clear()
    await call.answer()


@router.callback_query(F.data.startswith("pay_"), StateFilter(TopUpState.waiting_for_method))
async def topup_pick_method(call: types.CallbackQuery, state: FSMContext):
    currency = call.data.replace("pay_", "")
    await state.update_data(currency=currency)
    await call.message.answer("Введите сумму пополнения (в выбранной валюте):")
    await state.set_state(TopUpState.waiting_for_amount)
    await call.answer()


@router.message(StateFilter(TopUpState.waiting_for_amount))
async def topup_enter_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            return await message.answer("Введите положительное число")
    except ValueError:
        return await message.answer("Введите ЧИСЛО")

    data = await state.get_data()
    currency = data.get("currency", "rub")

    if not message.from_user:
        await state.clear()
        return await message.answer("Ошибка — нажмите /start")

    user_id = message.from_user.id

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await state.clear()
            return await message.answer("Сначала нажмите /start, чтобы зарегистрироваться")

        req = TopUpRequest(
            user_id=user.id,
            telegram_id=user.tg_id,
            amount=amount,
            currency=currency,
        )
        session.add(req)
        await session.flush()

        session.add(
            LogEntry(
                user_id=user.id,
                telegram_id=user.tg_id,
                request_id=req.request_id,
                event_type="topup_requested",
                message=f"Заявка на пополнение на {amount} {currency}",
                data={"topup_request_id": req.id},
            )
        )

        await session.commit()
        request_id = req.id

    await message.answer(
        f"✅ Заявка №{request_id} создана!\n⏳ Ожидайте подтверждения администратора.",
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"topup_ok:{request_id}")
    builder.button(text="❌ Отклонить", callback_data=f"topup_no:{request_id}")
    builder.adjust(2)
    reply_markup = builder.as_markup() if builder.export() else None

    await message.bot.send_message(
        ROOT_ADMIN_ID,
        f"💰 Заявка на пополнение #{request_id}\n"
        f"Пользователь: @{message.from_user.username or message.from_user.id}\n"
        f"Сумма: {amount} {currency.upper()}\n"
        f"Request ID: {req.request_id}",
        **({"reply_markup": reply_markup} if reply_markup else {}),
    )

    await state.clear()
