from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from bot.states.user_states import TopUpState
from bot.keyboards.user_keyboards import payment_methods_kb
from bot.db import SessionLocal, TopUpRequest, User
from bot.config import ROOT_ADMIN_ID
from bot.main_core import bot


async def topup_start(message: types.Message):
    await message.answer("Выберите способ оплаты:", reply_markup=payment_methods_kb())
    await TopUpState.waiting_for_method.set()


async def topup_pick_method(call: types.CallbackQuery, state: FSMContext):
    if call.data == "pay_cancel":
        await call.message.answer("❌ Отменено")
        return await state.finish()

    currency = call.data.replace("pay_", "")
    await state.update_data(currency=currency)

    await call.message.answer("Введите сумму пополнения (в той валюте, что выбрали):")
    await TopUpState.waiting_for_amount.set()
    await call.answer()


async def topup_enter_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            return await message.answer("Введите положительное число")
    except:
        return await message.answer("Введите ЧИСЛО")

    data = await state.get_data()
    currency = data["currency"]
    user_id = message.from_user.id

    with SessionLocal() as s:
        req = TopUpRequest(user_id=user_id, amount=amount, currency=currency)
        s.add(req)
        s.commit()
        request_id = req.id

    await message.answer(f"✅ Заявка №{request_id} создана!\n⏳ Ожидайте подтверждения администратора.")

    # уведомление админу
    await bot.send_message(
        ROOT_ADMIN_ID,
        f"💰 Заявка на пополнение #{request_id}\n"
        f"Пользователь: @{message.from_user.username} ({user_id})\n"
        f"Сумма: {amount} {currency.upper()}",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"topup_ok:{request_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"topup_no:{request_id}")
        )
    )

    await state.finish()
