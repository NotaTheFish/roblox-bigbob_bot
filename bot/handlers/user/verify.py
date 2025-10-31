from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from bot.states.verify_state import VerifyState
from bot.keyboards.verify_kb import verify_button, verify_check_button
from bot.utils.roblox import get_roblox_profile
from bot.db import SessionLocal, User
from random import randint
from time import sleep

# === Start verify ===
async def start_verify(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите ваш Roblox ник:")
    await VerifyState.waiting_for_username.set()


# === User enters nickname ===
async def set_username(message: types.Message, state: FSMContext):
    username = message.text.strip()

    code = randint(10000, 99999)
    
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=message.from_user.id).first()
        user.username = username
        user.code = str(code)
        s.commit()

    text = (
        f"✅ Ваш Roblox ник: <b>{username}</b>\n\n"
        f"Теперь вставьте этот код в <b>описание</b> или <b>статус</b> Roblox:\n"
        f"<code>{code}</code>\n\n"
        "После вставки нажмите кнопку ниже 👇"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=verify_check_button())
    await VerifyState.waiting_for_check.set()


# === Check verification ===
async def check_verify(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("⏳ Проверяем ваш Roblox профиль…\nЭто может занять до 5 секунд 🔥")

    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=call.from_user.id).first()
        username = user.username
        code = user.code

    sleep(2)  # имитация загрузки

    desc, status = get_roblox_profile(username)

    if desc is None:
        return await call.message.answer("❌ Не удалось найти профиль Roblox.\nПроверьте ник и попробуйте снова.")

    full_text = f"{desc} {status}"

    if code and code in full_text:
        with SessionLocal() as s:
            user = s.query(User).filter_by(tg_id=call.from_user.id).first()
            user.verified = True
            s.commit()

        await call.message.answer("✅ Аккаунт Roblox успешно подтверждён!\nДобро пожаловать! 🎉")
        await state.finish()
        return
    
    await call.message.answer("❌ Код не найден. Убедитесь, что он в описании или статусе и попробуйте снова.")
    await call.message.answer("Нажмите «🔍 Проверить» снова, когда будете готовы:", reply_markup=verify_check_button())


# === Cancel ===
async def cancel_verify(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.answer("❌ Верификация отменена", reply_markup=verify_button())


def register_verify(dp: Dispatcher):
    dp.register_callback_query_handler(start_verify, lambda c: c.data == "start_verify", state="*")
    dp.register_message_handler(set_username, state=VerifyState.waiting_for_username)
    dp.register_callback_query_handler(check_verify, lambda c: c.data == "check_verify", state=VerifyState.waiting_for_check)
    dp.register_callback_query_handler(cancel_verify, lambda c: c.data == "cancel_verify", state="*")
