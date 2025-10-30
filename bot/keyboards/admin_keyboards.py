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
        InlineKeyboardButton("🏆 Достижения", callback_data="admin_achievements")
    )
    return kb

def promo_reward_type_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Валюта", callback_data="promo_reward_money"),
        InlineKeyboardButton("🎁 Roblox предмет", callback_data="promo_reward_item")
    )
    return kb

def admin_achievements_kb():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Создать", callback_data="ach_add"),
        InlineKeyboardButton("📃 Список", callback_data="ach_list"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu"),
    )
    return kb

