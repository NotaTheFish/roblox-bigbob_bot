from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.db import Achievement, Admin, async_session
from bot.keyboards.admin_keyboards import admin_achievements_kb
from bot.states.admin_states import AchievementsState


router = Router(name="admin_achievements")


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


@router.callback_query(F.data == "admin_achievements")
async def admin_achievements_menu(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    await call.message.edit_text(
        "🏆 Достижения",
        reply_markup=admin_achievements_kb(),
    )


@router.callback_query(F.data == "ach_add")
async def ach_add(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите название достижения:")
    await state.set_state(AchievementsState.waiting_for_name)


@router.message(StateFilter(AchievementsState.waiting_for_name))
async def ach_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание:")
    await state.set_state(AchievementsState.waiting_for_description)


@router.message(StateFilter(AchievementsState.waiting_for_description))
async def ach_set_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите награду (монеты):")
    await state.set_state(AchievementsState.waiting_for_reward)


@router.message(StateFilter(AchievementsState.waiting_for_reward))
async def ach_finish(message: types.Message, state: FSMContext):
    try:
        reward = int(message.text)
    except ValueError:
        return await message.answer("Введите число")

    data = await state.get_data()

    async with async_session() as session:
        achievement = Achievement(
            name=data["name"],
            description=data["description"],
            reward=reward,
        )
        session.add(achievement)
        await session.commit()

    await message.answer("✅ Достижение создано!")
    await state.clear()


@router.callback_query(F.data == "ach_list")
async def ach_list(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    async with async_session() as session:
        items = (await session.scalars(select(Achievement))).all()

    if not items:
        return await call.message.edit_text(
            "Нет достижений",
            reply_markup=admin_achievements_kb(),
        )

    text = "🏆 <b>Список достижений:</b>\n\n"
    for achievement in items:
        text += f"• {achievement.name} — {achievement.reward}💰\n"

    await call.message.edit_text(
        text,
        reply_markup=admin_achievements_kb(),
        parse_mode="HTML",
    )
