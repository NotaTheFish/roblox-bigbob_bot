from aiogram import types, Dispatcher

from bot.db import SessionLocal, Admin
from bot.keyboards.admin_keyboards import admin_main_menu_kb

# Проверка администратора
def is_admin(uid: int) -> bool:
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())

# Команда для входа в админ панель
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ У вас нет доступа")

    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb()
    )

# Обработка кнопок панели (пока заглушки)
async def admin_menu_callbacks(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Нет доступа", show_alert=True)

    if call.data == "back_to_menu":
        await call.message.edit_text(
            "👑 <b>Админ-панель</b>\nВыберите раздел:",
            reply_markup=admin_main_menu_kb(),
        )
    elif call.data == "admin_logs":
        await call.message.edit_text(
            "📜 Раздел логов появится позже.",
            reply_markup=admin_main_menu_kb(),
        )

    await call.answer()

# Регистрация
def register_admin_menu(dp: Dispatcher):
    dp.register_message_handler(admin_panel, commands=["admin"])
    dp.register_callback_query_handler(
        admin_menu_callbacks,
        lambda c: c.data in {"admin_logs", "back_to_menu"},
    )
