from aiogram import types, Dispatcher
from bot.keyboards.admin_keyboards import admin_main_menu_kb
from bot.db import SessionLocal, Admin
from bot.main_core import bot

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

    mapping = {
        "admin_users": "📍 Раздел: Пользователи",
        "admin_promos": "📍 Раздел: Промокоды",
        "admin_shop": "📍 Раздел: Магазин",
        "admin_payments": "📍 Раздел: Пополнение",
        "admin_logs": "📍 Раздел: Логи",
        "back_to_menu": "↩ Главное меню",
    }

    label = mapping.get(call.data, "Раздел недоступен")

    await call.message.edit_text(label, reply_markup=admin_main_menu_kb())
    await call.answer()

# Регистрация
def register_admin_menu(dp: Dispatcher):
    dp.register_message_handler(admin_panel, commands=["admin"])
    dp.register_callback_query_handler(admin_menu_callbacks,
        lambda c: c.data.startswith("admin_") or c.data == "back_to_menu"
    )
