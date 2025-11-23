from __future__ import annotations

from typing import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.admin_logs import LogCategory
from bot.services.settings import BOT_STATUS_STOPPED


LOGS_REFRESH_BUTTON = "🔄 Обновить"
LOGS_SEARCH_BUTTON = "🔍 Поиск по пользователю"
LOGS_ADMIN_PICK_BUTTON = "👮 Выбрать админа"
LOGS_PREV_BUTTON = "⬅️ Предыдущая"
LOGS_NEXT_BUTTON = "➡️ Следующая"
LOGS_ACHIEVEMENTS_BUTTON = "🏆 Достижения"

LOGS_REFRESH_CALLBACK = "logs:refresh"
LOGS_SEARCH_CALLBACK = "logs:search"
LOGS_ADMIN_PICK_CALLBACK = "logs:pick_admin"
LOGS_PREV_CALLBACK = "logs:prev"
LOGS_NEXT_CALLBACK = "logs:next"


USERS_BROADCAST_BUTTON = "📢 Оповестить"

ACHIEVEMENT_VISIBILITY_FILTERS = {
    "all": "Все",
    "visible": "Видимые",
    "hidden": "Скрытые",
}

ACHIEVEMENT_CONDITION_FILTERS = {
    "all": "Все условия",
    "none": "Без условия",
    "time_in_game_at_least": "Время в игре",
    "payments_sum_at_least": "Пополнения",
    "balance_at_least": "Баланс",
    "spent_sum_at_least": "Траты",
    "purchase_count_at_least": "Кол-во покупок",
    "product_purchase": "Покупка",
    "nuts_at_least": "Орешки",
    "referral_count_at_least": "Рефералы",
    "promocode_redemption_count_at_least": "Промокоды",
}


def admin_main_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="🎟 Промокоды")],
        [KeyboardButton(text="🛠 Управление магазином"), KeyboardButton(text="📜 Логи")],
        [KeyboardButton(text="🏆 Достижения")],
        [KeyboardButton(text="🖥️ Сервера")],
        [KeyboardButton(text="↩️ В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_logs_menu_kb(*, is_root: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=LOGS_REFRESH_BUTTON), KeyboardButton(text=LOGS_SEARCH_BUTTON)],
        [KeyboardButton(text=LOGS_PREV_BUTTON), KeyboardButton(text=LOGS_NEXT_BUTTON)],
    ]
    if is_root:
        buttons.append([KeyboardButton(text=LOGS_ADMIN_PICK_BUTTON)])
    buttons.append([KeyboardButton(text="↩️ Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


_LOG_CATEGORY_LABELS = {
    LogCategory.TOPUPS: "💰 Пополнения",
    LogCategory.ACHIEVEMENTS: "🏆 Достижения",
    LogCategory.PURCHASES: "🛒 Покупки",
    LogCategory.PROMOCODES: "🎟 Промокоды",
    LogCategory.ADMIN_ACTIONS: "👮 Админ-действия",
}

_LOG_CATEGORY_ORDER = (
    LogCategory.TOPUPS,
    LogCategory.ACHIEVEMENTS,
    LogCategory.PURCHASES,
    LogCategory.PROMOCODES,
    LogCategory.ADMIN_ACTIONS,
)


def admin_logs_filters_inline(selected: LogCategory) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in _LOG_CATEGORY_ORDER:
        label = _LOG_CATEGORY_LABELS[category]
        suffix = " ✅" if category == selected else ""
        builder.button(
            text=f"{label}{suffix}",
            callback_data=f"logs:category:{category.value}",
        )
    builder.adjust(2, 2, 1)

    return builder.as_markup()


def admin_logs_controls_inline(
    *,
    selected: LogCategory,
    has_prev: bool,
    has_next: bool,
    is_root: bool,
) -> InlineKeyboardMarkup:
    return admin_logs_filters_inline(selected)


def admin_demote_confirm_kb(target_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"demote_admin_confirm:{target_id}")
    builder.button(text="✖️ Отмена", callback_data="demote_admin_cancel")
    builder.adjust(2)
    return builder.as_markup()


def admin_users_menu_kb(
    *, bot_status: str | None = None, is_root: bool = False
) -> ReplyKeyboardMarkup:
    top_row = [KeyboardButton(text="🚫 Бан-лист")]

    if is_root:
        status_label = (
            "🛑 Остановить" if bot_status != BOT_STATUS_STOPPED else "▶️ Запустить"
        )
        top_row.append(KeyboardButton(text=status_label))

    buttons = [top_row]
    buttons.append(
        [
            KeyboardButton(text="🔁 Обновить список"),
            KeyboardButton(text=USERS_BROADCAST_BUTTON),
        ]
    )
    buttons.append([KeyboardButton(text="↩️ Назад")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def broadcast_cancel_kb() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="✖️ Отмена")]]
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
        [KeyboardButton(text="📃 Список"), KeyboardButton(text="⚙️ Управление")],
        [KeyboardButton(text="📚 История"), KeyboardButton(text="🎁 Выдать награду")],
        [KeyboardButton(text="↩️ Назад")],
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

    return builder.as_markup()


def achievement_detail_inline(
    achievement_id: int,
    is_visible: bool,
    return_callback: str = "ach:list:filter:all:all",
    visibility_filter: str = "all",
    condition_filter: str = "all",
    page: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_suffix = f":{page}" if page is not None else ""
    delete_suffix = f":{page}" if page is not None else ""
    builder.button(
        text="👁 Скрыть" if is_visible else "👁 Показать",
        callback_data=(
            f"ach:toggle:{achievement_id}:{visibility_filter}:{condition_filter}{toggle_suffix}"
        ),
    )
    builder.button(text="✏️ Редактировать", callback_data=f"ach:edit:{achievement_id}")
    builder.button(
        text="🗑 Удалить",
        callback_data=(
            f"ach:delete:{achievement_id}:{visibility_filter}:{condition_filter}{delete_suffix}"
        ),
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
    *,
    page: int,
    has_prev: bool,
    has_next: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if achievement_rows:
        for ach_id, name in achievement_rows:
            builder.row(
                InlineKeyboardButton(
                    text=name[:18],
                    callback_data=(
                        f"ach:details:{ach_id}:{visibility_filter}:{condition_filter}:{page}"
                    ),
                )
            )
    else:
        builder.row(
            InlineKeyboardButton(text="Нет достижений", callback_data="ach:list:noop")
        )

    navigation_buttons: list[InlineKeyboardButton] = []
    if has_prev:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="⬅", callback_data=f"ach:manage:{visibility_filter}:{condition_filter}:{page - 1}"
            )
        )
    if has_next:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="➡", callback_data=f"ach:manage:{visibility_filter}:{condition_filter}:{page + 1}"
            )
        )
    if navigation_buttons:
        builder.row(*navigation_buttons)

    builder.row(
        InlineKeyboardButton(
            text="➕ Создать достижение",
            callback_data=f"ach:manage:create:{visibility_filter}:{condition_filter}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"ach:list:filter:{visibility_filter}:{condition_filter}",
        )
    )
    return builder.as_markup()


def achievement_history_inline(return_callback: str = "ach:list:filter:all:all") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К списку", callback_data=return_callback)
    return builder.as_markup()


def admin_servers_menu_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="➕ Создать сервер"),
            KeyboardButton(text="🗑 Удалить сервер"),
        ],
        [
            KeyboardButton(text="🔗 Назначить ссылку"),
            KeyboardButton(text="🚫 Удалить ссылку"),
        ],
        [KeyboardButton(text="↩️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_server_picker_kb(
    button_items: Sequence[tuple[int, str]]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for position, label in button_items:
        builder.button(text=label, callback_data=f"servers_pick:{position}")
    builder.adjust(2)
    return builder.as_markup()


def admin_server_navigation_kb() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="↩️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)