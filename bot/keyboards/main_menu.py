from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- Главное меню пользователя / админа ---

def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row(
        KeyboardButton("👤 Профиль"),
        KeyboardButton("🛒 Магазин"),
    )
    kb.row(
        KeyboardButton("🎮 Играть"),
        KeyboardButton("🆘 Поддержка"),
    )
    kb.row(
        KeyboardButton("🏆 Топ игроков"),
        KeyboardButton("💳 Пополнить баланс"),
    )
    kb.row(
        KeyboardButton("🎟 Промокод"),
    )

    if is_admin:
        kb.add(KeyboardButton("🛠 Режим админа"))

    return kb


# --- Подменю: Профиль ---

def profile_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🔗 Реферальная ссылка"),
        KeyboardButton("💳 Пополнить баланс"),
    )
    kb.row(
        KeyboardButton("🎟 Промокод"),
        KeyboardButton("🏆 Топ игроков"),
    )
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb


# --- Подменю: Магазин ---

def shop_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🎁 Предметы"),
        KeyboardButton("🛡 Привилегии"),
    )
    kb.row(
        KeyboardButton("💰 Кеш"),
        KeyboardButton("⬅️ Назад"),
    )
    return kb


# --- Поддержка ---

def support_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("✍️ Написать в поддержку"))
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb


# --- Серверы Roblox ---

def play_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🌐 Сервер #1"),
        KeyboardButton("🌐 Сервер #2"),
    )
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb
