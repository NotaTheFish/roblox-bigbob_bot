from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- Главное меню пользователя / админа ---

def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🛒 Магазин")],
        [KeyboardButton(text="🎮 Играть"), KeyboardButton(text="🆘 Поддержка")],
        [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="💳 Пополнить баланс")],
        [KeyboardButton(text="🎟 Промокод")]
    ]

    if is_admin:
        buttons.append([KeyboardButton(text="🛠 Режим админа")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# --- Подменю: Профиль ---

def profile_menu() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🔗 Реферальная ссылка"), KeyboardButton(text="💳 Пополнить баланс")],
        [KeyboardButton(text="🎟 Промокод"), KeyboardButton(text="🏆 Топ игроков")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# --- Подменю: Магазин ---

def shop_menu() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🎁 Предметы"), KeyboardButton(text="🛡 Привилегии")],
        [KeyboardButton(text="💰 Кеш"), KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# --- Поддержка ---

def support_menu() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="✍️ Написать в поддержку")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# --- Серверы Roblox ---

def play_menu() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🌐 Сервер #1"), KeyboardButton(text="🌐 Сервер #2")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
