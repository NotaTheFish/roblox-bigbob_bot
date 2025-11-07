from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def admin_main_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="🎁 Промокоды")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="💰 Пополнение")],
        [KeyboardButton(text="📜 Логи"), KeyboardButton(text="🏆 Достижения")],
        [KeyboardButton(text="⬅️ В меню")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


def promo_reward_type_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="💰 Валюта"), KeyboardButton(text="🎁 Roblox предмет")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


def admin_achievements_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Создать"), KeyboardButton(text="📃 Список")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
