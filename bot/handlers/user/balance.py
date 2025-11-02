from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import TopUpRequest, User, async_session
from bot.keyboards.user_keyboards import payment_methods_kb
from bot.states.user_states import TopUpState


async def topup_start(message: types.Message):
    await message.answer("Выберите способ оплаты:", reply_markup=payment_methods_kb())
    await TopUpState.waiting_for_method.set()


async def topup_pick_method(call: types.CallbackQuery, state: FSMContext):
    if call.data == "pay_cancel":
        await call.message.answer("❌ Отменено")
        await state.finish()
        return await call.answer()

    currency = call.data.replace("pay_", "")
    await state.update_data(currency=currency)

    await call.message.answer("Введите сумму пополнения (в выбранной валюте):")
    await TopUpState.waiting_for_amount.set()
    await call.answer()


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
        await state.finish()
        return await message.answer("Ошибка — нажмите /start")

    user_id = message.from_user.id

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await state.finish()
            return await message.answer("Сначала нажмите /start, чтобы зарегистрироваться")

        req = TopUpRequest(user_id=user_id, amount=amount, currency=currency)
        session.add(req)
        await session.commit()
        request_id = req.id

    await message.answer(
        f"✅ Заявка №{request_id} создана!\n⏳ Ожидайте подтверждения администратора.",
    )

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"topup_ok:{request_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"topup_no:{request_id}"),
    )

    await bot.send_message(
        ROOT_ADMIN_ID,
        f"💰 Заявка на пополнение #{request_id}\n"
        f"Пользователь: @{message.from_user.username or message.from_user.id}\n"
        f"Сумма: {amount} {currency.upper()}",
        reply_markup=kb,
    )

    await state.finish()


def register_user_balance(dp: Dispatcher):
    dp.register_message_handler(topup_start, commands=["topup", "balance"])
    dp.register_callback_query_handler(
        topup_pick_method,
        lambda c: c.data.startswith("pay_"),
        state=TopUpState.waiting_for_method,
    )
    dp.register_message_handler(
        topup_enter_amount,
        state=TopUpState.waiting_for_amount,
    )
