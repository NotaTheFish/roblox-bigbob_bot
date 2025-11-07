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


@router.message(F.text == "🏆 Достижения")
async def admin_achievements_menu(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "🏆 Достижения",
        reply_markup=admin_achievements_kb(),
    )


@router.message(F.text == "➕ Создать")
async def ach_add(message: types.Message, state: FSMContext):
    if not message.from_user or not await is_admin(message.from_user.id):
        return

    await message.answer("Введите название достижения:")
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

    await message.answer("✅ Достижение создано!", reply_markup=admin_achievements_kb())
    await state.clear()


@router.message(F.text == "📃 Список")
async def ach_list(message: types.Message):
    if not message.from_user or not await is_admin(message.from_user.id):
        return

    async with async_session() as session:
        items = (await session.scalars(select(Achievement))).all()

    if not items:
        await message.answer(
            "Нет достижений",
            reply_markup=admin_achievements_kb(),
        )
        return

    text = "🏆 <b>Список достижений:</b>\n\n"
    for achievement in items:
        text += f"• {achievement.name} — {achievement.reward}💰\n"

    await message.answer(
        text,
        reply_markup=admin_achievements_kb(),
        parse_mode="HTML",
    )
