from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from bot.states.admin_states import AchievementsState
from bot.db import SessionLocal, Achievement, UserAchievement, Admin
from bot.keyboards.admin_keyboards import admin_achievements_kb
from bot.bot_instance import bot

def is_admin(uid):
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())


async def admin_achievements_menu(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    await call.message.edit_text("🏆 Достижения", reply_markup=admin_achievements_kb())


async def ach_add(call: types.CallbackQuery):
    await call.message.answer("Введите название достижения:")
    await AchievementsState.waiting_for_name.set()


async def ach_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание:")
    await AchievementsState.waiting_for_description.set()


async def ach_set_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите награду (монеты):")
    await AchievementsState.waiting_for_reward.set()


async def ach_finish(message: types.Message, state: FSMContext):
    try:
        reward = int(message.text)
    except:
        return await message.answer("Введите число")

    data = await state.get_data()

    with SessionLocal() as s:
        ach = Achievement(
            name=data["name"],
            description=data["description"],
            reward=reward
        )
        s.add(ach)
        s.commit()

    await message.answer("✅ Достижение создано!")
    await state.finish()


async def ach_list(call: types.CallbackQuery):
    with SessionLocal() as s:
        items = s.query(Achievement).all()

    if not items:
        return await call.message.edit_text("Нет достижений", reply_markup=admin_achievements_kb())

    text = "🏆 <b>Список достижений:</b>\n\n"
    for a in items:
        text += f"• {a.name} — {a.reward}💰\n"

    await call.message.edit_text(text, reply_markup=admin_achievements_kb(), parse_mode="HTML")


def register_admin_achievements(dp: Dispatcher):
    dp.register_callback_query_handler(admin_achievements_menu, lambda c: c.data == "admin_achievements")
    dp.register_callback_query_handler(ach_add, lambda c: c.data == "ach_add")
    dp.register_message_handler(ach_set_name, state=AchievementsState.waiting_for_name)
    dp.register_message_handler(ach_set_description, state=AchievementsState.waiting_for_description)
    dp.register_message_handler(ach_finish, state=AchievementsState.waiting_for_reward)
    dp.register_callback_query_handler(ach_list, lambda c: c.data == "ach_list")
 
