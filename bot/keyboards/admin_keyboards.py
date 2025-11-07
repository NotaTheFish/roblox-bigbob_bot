from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def admin_main_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="🎟 Промокоды")],
        [KeyboardButton(text="Управление магазином"), KeyboardButton(text="📜 Логи")],
        [KeyboardButton(text="🏆 Достижения"), KeyboardButton(text="Пополнение")],
        [KeyboardButton(text="Добавить сервер")],
        [KeyboardButton(text="↩️ В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_users_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🔁 Обновить список")],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_promos_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Создать промокод"), KeyboardButton(text="📄 Список промокодов")],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def promo_reward_type_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="💰 Валюта"), KeyboardButton(text="🎁 Roblox предмет")],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_shop_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📦 Список товаров")],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def shop_type_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="💰 Валюта"), KeyboardButton(text="🛡 Привилегия")],
        [KeyboardButton(text="🎁 Roblox предмет"), KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_achievements_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Создать"), KeyboardButton(text="📃 Список")],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
