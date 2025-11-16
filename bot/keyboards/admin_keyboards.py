from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


ACHIEVEMENT_VISIBILITY_FILTERS = {
    "all": "Все",
    "visible": "Видимые",
    "hidden": "Скрытые",
}

ACHIEVEMENT_CONDITION_FILTERS = {
    "all": "Все условия",
    "none": "Без условий",
    "balance_at_least": "Баланс",
    "nuts_at_least": "Орешки",
    "product_purchase": "Покупка",
}


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
        [KeyboardButton(text="🎯 Фильтры"), KeyboardButton(text="📚 История")],
        [KeyboardButton(text="🎁 Выдать награду"), KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def achievement_list_inline(
    visibility_filter: str = "all", condition_filter: str = "all"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value, label in ACHIEVEMENT_VISIBILITY_FILTERS.items():
        suffix = " ✅" if value == visibility_filter else ""
        builder.button(
            text=f"👁 {label}{suffix}",
            callback_data=f"ach:list:filter:{value}:{condition_filter}",
        )
    builder.adjust(3)

    for value, label in ACHIEVEMENT_CONDITION_FILTERS.items():
        suffix = " ✅" if value == condition_filter else ""
        builder.button(
            text=f"🎯 {label}{suffix}",
            callback_data=f"ach:list:filter:{visibility_filter}:{value}",
        )
    builder.adjust(2, 3)

    builder.button(text="📚 История", callback_data="ach:history:1")
    builder.button(text="🎁 Выдать", callback_data="ach:grant:start")
    builder.adjust(2)
    builder.button(
        text="⚙️ Управление",
        callback_data=f"ach:manage:{visibility_filter}:{condition_filter}",
    )

    return builder.as_markup()


def achievement_detail_inline(
    achievement_id: int,
    is_visible: bool,
    return_callback: str = "ach:list:filter:all:all",
    visibility_filter: str = "all",
    condition_filter: str = "all",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="👁 Скрыть" if is_visible else "👁 Показать",
        callback_data=
        f"ach:toggle:{achievement_id}:{visibility_filter}:{condition_filter}",
    )
    builder.button(text="✏️ Редактировать", callback_data=f"ach:edit:{achievement_id}")
    builder.button(
        text="🗑 Удалить",
        callback_data=f"ach:delete:{achievement_id}:{visibility_filter}:{condition_filter}",
    )
    builder.button(
        text="👥 Получившие",
        callback_data=f"ach:users:{achievement_id}:1:{visibility_filter}:{condition_filter}",
    )
    builder.button(text="⬅️ К списку", callback_data=return_callback)
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def achievement_users_navigation_kb(
    achievement_id: int,
    page: int,
    has_prev: bool,
    has_next: bool,
    visibility_filter: str = "all",
    condition_filter: str = "all",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_prev:
        builder.button(
            text="⬅️",
            callback_data=f"ach:users:{achievement_id}:{page - 1}:{visibility_filter}:{condition_filter}",
        )
    builder.button(
        text="⬅️ К достижению",
        callback_data=f"ach:details:{achievement_id}:{visibility_filter}:{condition_filter}",
    )
    if has_next:
        builder.button(
            text="➡️",
            callback_data=f"ach:users:{achievement_id}:{page + 1}:{visibility_filter}:{condition_filter}",
        )
    builder.adjust(3)
    return builder.as_markup()


def achievement_manage_inline(
    achievement_rows: list[tuple[int, str]],
    visibility_filter: str,
    condition_filter: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if achievement_rows:
        for ach_id, name in achievement_rows:
            builder.button(
                text=f"#{ach_id} {name[:18]}",
                callback_data=f"ach:details:{ach_id}:{visibility_filter}:{condition_filter}",
            )
    else:
        builder.button(text="Нет достижений", callback_data="ach:list:noop")
    builder.button(
        text="⬅️ Назад",
        callback_data=f"ach:list:filter:{visibility_filter}:{condition_filter}",
    )
    builder.adjust(1)
    return builder.as_markup()


def achievement_history_inline(return_callback: str = "ach:list:filter:all:all") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К списку", callback_data=return_callback)
    return builder.as_markup()


def admin_servers_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Создать сервер"), KeyboardButton(text="🗑 Удалить сервер")],
        [KeyboardButton(text="🔗 Назначить ссылку"), KeyboardButton(text="🚫 Удалить ссылку")],
        [KeyboardButton(text="⬅️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
