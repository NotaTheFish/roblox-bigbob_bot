from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="🎁 Промокоды", callback_data="admin_promos")
    builder.button(text="🛒 Магазин", callback_data="admin_shop")
    builder.button(text="💰 Пополнение", callback_data="admin_payments")
    builder.button(text="📜 Логи", callback_data="admin_logs")
    builder.button(text="⬅️ В меню", callback_data="back_to_menu")
    builder.button(text="🏆 Достижения", callback_data="admin_achievements")
    builder.adjust(2)
    return builder.as_markup()


def promo_reward_type_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Валюта", callback_data="promo_reward_money")
    builder.button(text="🎁 Roblox предмет", callback_data="promo_reward_item")
    builder.adjust(2)
    return builder.as_markup()


def admin_achievements_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать", callback_data="ach_add"),
        InlineKeyboardButton(text="📃 Список", callback_data="ach_list"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu"),
    )
    return builder.as_markup()

