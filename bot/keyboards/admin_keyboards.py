from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
        InlineKeyboardButton("🛒 Магазин", callback_data="admin_shop"),
        InlineKeyboardButton("💰 Пополнение", callback_data="admin_payments"),
        InlineKeyboardButton("📜 Логи", callback_data="admin_logs"),
        InlineKeyboardButton("⬅️ В меню", callback_data="back_to_menu"),
    )
    return kb
