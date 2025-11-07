import asyncio
from random import randint

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select

from bot.db import Admin, User, async_session
from bot.keyboards.main_menu import main_menu
from bot.keyboards.verify_kb import verify_button, verify_check_button
from bot.states.verify_state import VerifyState
from bot.utils.roblox import get_roblox_profile


router = Router(name="user_verify")


# === Start verification ===
@router.callback_query(F.data == "start_verify", StateFilter(None))
async def start_verify(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите ваш Roblox ник:")
    await state.set_state(VerifyState.waiting_for_username)


# === User enters Roblox nickname ===
@router.message(StateFilter(VerifyState.waiting_for_username))
async def set_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    code = randint(10000, 99999)

    if not message.from_user:
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            return

        user.username = username
        user.code = str(code)
        await session.commit()

    text = (
        f"✅ Ваш Roblox ник: <b>{username}</b>\n\n"
        f"Теперь вставьте этот код в <b>описание</b> или <b>статус</b> Roblox:\n"
        f"<code>{code}</code>\n\n"
        "После вставки нажмите кнопку ниже 👇"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=verify_check_button())
    await state.set_state(VerifyState.waiting_for_check)


# === Check verification ===
@router.callback_query(F.data == "check_verify", StateFilter(VerifyState.waiting_for_check))
async def check_verify(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("⏳ Проверяем ваш Roblox профиль…\nЭто может занять до 5 секунд 🔥")

    if not call.from_user:
        return await call.message.answer("❌ Пользователь не найден. Нажмите /start")

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user:
            return await call.message.answer("❌ Профиль не найден. Нажмите /start")
        username = user.username
        code = user.code

    await asyncio.sleep(2)  # имитация загрузки

    desc, status = get_roblox_profile(username)
    if desc is None:
        return await call.message.answer("❌ Не удалось найти профиль Roblox.\nПроверьте ник и попробуйте снова.")

    full_text = f"{desc} {status}"

    if code and code in full_text:
        is_admin = False
        async with async_session() as session:
            db_user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
            if db_user:
                db_user.verified = True
                is_admin = bool(
                    await session.scalar(select(Admin).where(Admin.telegram_id == call.from_user.id))
                )
                await session.commit()

        await state.clear()
        await call.message.answer(
            "✅ Аккаунт Roblox успешно подтверждён!\nДобро пожаловать! 🎉",
            reply_markup=main_menu(is_admin=is_admin),
        )
        return

    await call.message.answer(
        "❌ Код не найден. Убедитесь, что он в описании или статусе и попробуйте снова."
    )
    await call.message.answer(
        "Нажмите «🔍 Проверить» снова, когда будете готовы:",
        reply_markup=verify_check_button(),
    )


# === Cancel verification ===
@router.callback_query(F.data == "cancel_verify")
async def cancel_verify(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Верификация отменена", reply_markup=verify_button())
