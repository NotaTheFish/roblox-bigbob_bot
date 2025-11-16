from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="🎟 Промокоды")],
        [KeyboardButton(text="🛠 Управление магазином"), KeyboardButton(text="📜 Логи")],
        [KeyboardButton(text="🏆 Достижения")],
        [KeyboardButton(text="Сервера")],
        [KeyboardButton(text="↩️ В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_users_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🔁 Обновить список")],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def promo_management_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать", callback_data="promo:menu:create")
    builder.button(text="🗑 Удалить", callback_data="promo:menu:delete")
    builder.button(text="📄 Все промокоды", callback_data="promo:menu:list")
    builder.button(text="✖️ Отмена", callback_data="promo:cancel")
    builder.adjust(2, 2)
    return builder.as_markup()


def promo_reward_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🥜 Орешки", callback_data="promo:create:type:nuts")
    builder.button(text="💸 Скидка", callback_data="promo:create:type:discount")
    builder.button(text="➡️ Далее", callback_data="promo:create:next:type")
    builder.button(text="✖️ Отмена", callback_data="promo:cancel")
    builder.adjust(2, 2)
    return builder.as_markup()


def promo_step_navigation_kb(next_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Далее", callback_data=next_callback)
    builder.button(text="✖️ Отмена", callback_data="promo:cancel")
    builder.adjust(2)
    return builder.as_markup()


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


def admin_servers_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Создать сервер"), KeyboardButton(text="🗑 Удалить сервер")],
        [KeyboardButton(text="🔗 Назначить ссылку"), KeyboardButton(text="🚫 Удалить ссылку")],
        [KeyboardButton(text="⬅️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
