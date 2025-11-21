from __future__ import annotations

import html
from typing import Sequence

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import and_, func, or_, select

from backend.services.nuts import add_nuts
from bot.db import (
    Achievement,
    AchievementConditionType,
    Admin,
    User,
    UserAchievement,
    async_session,
)
from bot.keyboards.admin_keyboards import (
    ACHIEVEMENT_CONDITION_FILTERS,
    ACHIEVEMENT_VISIBILITY_FILTERS,
    achievement_detail_inline,
    achievement_history_inline,
    achievement_list_inline,
    achievement_manage_inline,
    achievement_users_navigation_kb,
    admin_achievements_kb,
)
from bot.states.admin_states import AchievementsState
from bot.utils.time import to_msk

router = Router(name="admin_achievements")

DEFAULT_VISIBILITY_FILTER = "all"
DEFAULT_CONDITION_FILTER = "all"
HISTORY_LIMIT = 10
USERS_PAGE_SIZE = 10

CONDITION_TYPES: dict[str, dict[str, object]] = {
    AchievementConditionType.NONE.value: {
        "title": "Без условий",
        "needs_value": False,
        "needs_threshold": False,
    },
    AchievementConditionType.BALANCE_AT_LEAST.value: {
        "title": "Баланс монет",
        "needs_value": False,
        "needs_threshold": True,
        "unit": "монет",
    },
    AchievementConditionType.NUTS_AT_LEAST.value: {
        "title": "Баланс орешков",
        "needs_value": False,
        "needs_threshold": True,
        "unit": "орешков",
    },
    AchievementConditionType.PRODUCT_PURCHASE.value: {
        "title": "Покупка товара (ID)",
        "needs_value": True,
        "needs_threshold": False,
    },
    AchievementConditionType.PURCHASE_COUNT_AT_LEAST.value: {
        "title": "Количество завершённых покупок",
        "needs_value": False,
        "needs_threshold": True,
    },
    AchievementConditionType.PAYMENTS_SUM_AT_LEAST.value: {
        "title": "Сумма пополнений",
        "needs_value": False,
        "needs_threshold": True,
        "unit": "монет",
    },
    AchievementConditionType.REFERRAL_COUNT_AT_LEAST.value: {
        "title": "Количество приглашённых друзей",
        "needs_value": False,
        "needs_threshold": True,
    },
    AchievementConditionType.TIME_IN_GAME_AT_LEAST.value: {
        "title": "Время в игре",
        "needs_value": False,
        "needs_threshold": True,
        "unit": "минут",
    },
    AchievementConditionType.SPENT_SUM_AT_LEAST.value: {
        "title": "Сумма трат",
        "needs_value": False,
        "needs_threshold": True,
        "unit": "монет",
    },
    AchievementConditionType.PROMOCODE_REDEMPTION_COUNT_AT_LEAST.value: {
        "title": "Активации промокодов",
        "needs_value": False,
        "needs_threshold": True,
    },
}

CONDITION_ALIASES = {
    "нет": AchievementConditionType.NONE.value,
    "none": AchievementConditionType.NONE.value,
    "без": AchievementConditionType.NONE.value,
    "баланс": AchievementConditionType.BALANCE_AT_LEAST.value,
    "balance": AchievementConditionType.BALANCE_AT_LEAST.value,
    "nuts": AchievementConditionType.NUTS_AT_LEAST.value,
    "орешки": AchievementConditionType.NUTS_AT_LEAST.value,
    "покупка": AchievementConditionType.PRODUCT_PURCHASE.value,
    "product": AchievementConditionType.PRODUCT_PURCHASE.value,
    "товар": AchievementConditionType.PRODUCT_PURCHASE.value,
    "покупки": AchievementConditionType.PURCHASE_COUNT_AT_LEAST.value,
    "orders": AchievementConditionType.PURCHASE_COUNT_AT_LEAST.value,
    "платежи": AchievementConditionType.PAYMENTS_SUM_AT_LEAST.value,
    "пополнение": AchievementConditionType.PAYMENTS_SUM_AT_LEAST.value,
    "пополнения": AchievementConditionType.PAYMENTS_SUM_AT_LEAST.value,
    "рефералы": AchievementConditionType.REFERRAL_COUNT_AT_LEAST.value,
    "друзья": AchievementConditionType.REFERRAL_COUNT_AT_LEAST.value,
    "время": AchievementConditionType.TIME_IN_GAME_AT_LEAST.value,
    "игра": AchievementConditionType.TIME_IN_GAME_AT_LEAST.value,
    "play": AchievementConditionType.TIME_IN_GAME_AT_LEAST.value,
    "траты": AchievementConditionType.SPENT_SUM_AT_LEAST.value,
    "spend": AchievementConditionType.SPENT_SUM_AT_LEAST.value,
    "промокоды": AchievementConditionType.PROMOCODE_REDEMPTION_COUNT_AT_LEAST.value,
    "промокод": AchievementConditionType.PROMOCODE_REDEMPTION_COUNT_AT_LEAST.value,
    "promo": AchievementConditionType.PROMOCODE_REDEMPTION_COUNT_AT_LEAST.value,
}


def _normalize_visibility_filter(value: str) -> str:
    return value if value in ACHIEVEMENT_VISIBILITY_FILTERS else DEFAULT_VISIBILITY_FILTER


def _normalize_condition_filter(value: str) -> str:
    return value if value in ACHIEVEMENT_CONDITION_FILTERS else DEFAULT_CONDITION_FILTER


def _normalize_condition_type(value: str) -> str | None:
    candidate = value.strip().lower()
    if candidate in CONDITION_TYPES:
        return candidate
    return CONDITION_ALIASES.get(candidate)


def _condition_key(value: AchievementConditionType | str | None) -> str:
    if isinstance(value, AchievementConditionType):
        return value.value
    return (value or AchievementConditionType.NONE.value).lower()


def _parse_bool_answer(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"да", "yes", "y", "true", "1", "+", "ok"}


def _threshold_prompt(condition_type: str) -> str:
    unit = CONDITION_TYPES.get(condition_type, {}).get("unit")
    suffix = ""
    if unit:
        suffix = f" ({unit})"

    if condition_type == AchievementConditionType.TIME_IN_GAME_AT_LEAST.value:
        suffix = " (в минутах)"

    return f"Введите числовой порог условия{suffix}:"


def _describe_condition(achievement: Achievement) -> str:
    condition_type = _condition_key(achievement.condition_type)
    info = CONDITION_TYPES.get(condition_type)
    if not info:
        return "Неизвестное условие"

    if condition_type == "none":
        return info["title"]  # type: ignore[index]
    if condition_type == AchievementConditionType.PRODUCT_PURCHASE.value:
        value = achievement.condition_value
        label = "любой товар" if value in {None, 0} else value
        return f"{info['title']}: {label}"

    if info.get("needs_threshold"):
        threshold = achievement.condition_threshold or 0
        unit = info.get("unit")
        suffix = f" {unit}" if unit else ""
        return f"{info['title']} ≥ {threshold}{suffix}"

    return info["title"]  # type: ignore[index]


def _build_detail_text(achievement: Achievement, total: int | None) -> str:
    visibility = "открыто" if achievement.is_visible else "скрыто"
    hidden = "секретное" if achievement.is_hidden else "публичное"
    manual = "только вручную" if achievement.manual_grant_only else "автовыдача"
    return (
        f"🏆 <b>{html.escape(achievement.name)}</b>\n\n"
        f"Описание: {html.escape(achievement.description or '—')}\n"
        f"Награда: {achievement.reward}🥜\n"
        f"Условие: {_describe_condition(achievement)}\n"
        f"Статус: {visibility}, {hidden}, {manual}\n"
        f"Получили: {total or 0} пользователей"
    )


def _build_achievements_overview(achievements: Sequence[Achievement]) -> str:
    if not achievements:
        return "🏆 <b>Достижения</b>\n\nПока ничего не создано."

    lines = ["🏆 <b>Достижения</b>\n"]
    for achievement in achievements:
        visibility = "👁" if achievement.is_visible else "🚫"
        hidden = "🕵️" if achievement.is_hidden else ""
        manual = "🤝" if achievement.manual_grant_only else ""
        name = html.escape(achievement.name)
        lines.append(
            f"{visibility}{hidden}{manual} <b>{name}</b> — {achievement.reward}🥜\n"
            f"<i>{_describe_condition(achievement)}</i>\n"
        )
    return "\n".join(lines)


async def _load_achievements(
    visibility_filter: str = DEFAULT_VISIBILITY_FILTER,
    condition_filter: str = DEFAULT_CONDITION_FILTER,
) -> list[Achievement]:
    async with async_session() as session:
        stmt = select(Achievement).order_by(
            Achievement.created_at.desc().nullslast(), Achievement.id.desc()
        )
        if visibility_filter == "visible":
            stmt = stmt.where(Achievement.is_visible.is_(True))
        elif visibility_filter == "hidden":
            stmt = stmt.where(Achievement.is_visible.is_(False))

        achievements = (await session.scalars(stmt)).all()

    if condition_filter == "all":
        return achievements

    filtered: list[Achievement] = []
    for achievement in achievements:
        ach_type = _condition_key(achievement.condition_type)
        if condition_filter == "none" and ach_type == "none":
            filtered.append(achievement)
        elif condition_filter != "none" and ach_type == condition_filter:
            filtered.append(achievement)
    return filtered


async def _send_achievement_list(
    message: types.Message,
    *,
    visibility_filter: str = DEFAULT_VISIBILITY_FILTER,
    condition_filter: str = DEFAULT_CONDITION_FILTER,
    as_edit: bool = False,
) -> None:
    achievements = await _load_achievements(visibility_filter, condition_filter)
    text = _build_achievements_overview(achievements)
    markup = achievement_list_inline(visibility_filter, condition_filter)
    if as_edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def _send_history(target: types.Message, *, as_edit: bool = False) -> None:
    async with async_session() as session:
        stmt = (
            select(
                UserAchievement,
                User.bot_nickname,
                User.username,
                User.tg_username,
                Achievement.name,
            )
            .join(User, User.id == UserAchievement.user_id)
            .join(Achievement, Achievement.id == UserAchievement.achievement_id)
            .order_by(UserAchievement.earned_at.desc())
            .limit(HISTORY_LIMIT)
        )
        rows = (await session.execute(stmt)).all()

    if not rows:
        text = "Пока нет выдач достижений зафиксированных системой."
    else:
        lines = ["📚 <b>Последние выдачи</b>\n"]
        for entry, bot_nickname, username, tg_username, ach_name in rows:
            user_label = bot_nickname or username
            if not user_label and tg_username:
                user_label = f"@{tg_username}"
            user_label = user_label or entry.tg_id
            lines.append(
                f"{to_msk(entry.earned_at):%d.%m %H:%M} — {html.escape(str(user_label))}"
                f" получил {html.escape(ach_name)} ({entry.source})"
            )
        text = "\n".join(lines)

    markup = achievement_history_inline()
    if as_edit:
        await target.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")


async def _send_achievement_management(
    target: types.Message,
    *,
    visibility_filter: str = DEFAULT_VISIBILITY_FILTER,
    condition_filter: str = DEFAULT_CONDITION_FILTER,
    as_edit: bool = False,
) -> None:
    achievements = await _load_achievements(visibility_filter, condition_filter)
    rows = [(ach.id, ach.name) for ach in achievements]
    text = "Выберите достижение для управления"
    markup = achievement_manage_inline(rows[:25], visibility_filter, condition_filter)
    if as_edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


@router.message(F.text == "🏆 Достижения")
async def admin_achievements_menu(message: types.Message):
    if not message.from_user or not await is_admin(message.from_user.id):
        return

    await message.answer(
        "🏆 Достижения",
        reply_markup=admin_achievements_kb(),
    )


@router.message(F.text == "📃 Список")
async def ach_list(message: types.Message):
    if not message.from_user or not await is_admin(message.from_user.id):
        return
    await _send_achievement_list(message)


@router.message(F.text == "📚 История")
async def ach_history_message(message: types.Message):
    if not message.from_user or not await is_admin(message.from_user.id):
        return
    await _send_history(message)


@router.message(F.text == "⚙️ Управление")
async def ach_manage_menu(message: types.Message):
    if not message.from_user or not await is_admin(message.from_user.id):
        return
    await _send_achievement_management(message)


@router.message(F.text == "🎁 Выдать награду")
async def ach_manual_grant_entry(message: types.Message, state: FSMContext):
    if not message.from_user or not await is_admin(message.from_user.id):
        return
    await message.answer(
        "Отправьте Telegram ID пользователя или @username, которому хотите вручить достижение:"
    )
    await state.set_state(AchievementsState.manual_grant_user)


@router.callback_query(F.data == "ach:grant:start")
async def ach_manual_grant_from_callback(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    await call.answer()
    await call.message.answer(
        "Отправьте Telegram ID пользователя или @username для выдачи достижения."
    )
    await state.set_state(AchievementsState.manual_grant_user)


@router.callback_query(F.data.startswith("ach:list:filter:"))
async def ach_list_callback(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    parts = call.data.split(":")
    if len(parts) != 5:
        await call.answer("Некорректные данные", show_alert=True)
        return
    _, _, _, visibility_raw, condition_raw = parts
    visibility = _normalize_visibility_filter(visibility_raw)
    condition = _normalize_condition_filter(condition_raw)
    await _send_achievement_list(
        call.message,
        visibility_filter=visibility,
        condition_filter=condition,
        as_edit=True,
    )
    await call.answer("Список обновлён")


@router.callback_query(
    F.data.startswith("ach:manage:") & ~F.data.startswith("ach:manage:create")
)
async def ach_manage_callback(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("Некорректные данные", show_alert=True)
        return
    _, _, visibility_raw, condition_raw = parts
    visibility = _normalize_visibility_filter(visibility_raw)
    condition = _normalize_condition_filter(condition_raw)
    await _send_achievement_management(
        call.message,
        visibility_filter=visibility,
        condition_filter=condition,
        as_edit=True,
    )
    await call.answer()


@router.callback_query(F.data.startswith("ach:manage:create"))
async def ach_manage_create_callback(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return

    parts = call.data.split(":")
    if len(parts) not in (3, 5):
        await call.answer("Некорректные данные", show_alert=True)
        return

    visibility_raw = parts[3] if len(parts) == 5 else "all"
    condition_raw = parts[4] if len(parts) == 5 else "all"
    _normalize_visibility_filter(visibility_raw)
    _normalize_condition_filter(condition_raw)

    await call.answer()
    await state.set_state(AchievementsState.waiting_for_name)
    await state.update_data(mode="create")
    await call.message.answer("Введите название достижения:")


@router.callback_query(F.data.startswith("ach:details:"))
async def ach_details_callback(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    parts = call.data.split(":")
    if len(parts) != 5:
        await call.answer("Некорректный идентификатор", show_alert=True)
        return
    _, _, ach_id_str, visibility_raw, condition_raw = parts
    try:
        ach_id_int = int(ach_id_str)
    except ValueError:
        await call.answer("Некорректный идентификатор", show_alert=True)
        return
    visibility = _normalize_visibility_filter(visibility_raw)
    condition = _normalize_condition_filter(condition_raw)

    async with async_session() as session:
        achievement = await session.get(Achievement, ach_id_int)
        if not achievement:
            await call.answer("Достижение не найдено", show_alert=True)
            return
        total = await session.scalar(
            select(func.count()).where(UserAchievement.achievement_id == ach_id_int)
        )

    text = _build_detail_text(achievement, total)
    return_callback = f"ach:manage:{visibility}:{condition}"
    markup = achievement_detail_inline(
        achievement.id,
        achievement.is_visible,
        return_callback,
        visibility,
        condition,
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "ach:list:noop")
async def ach_list_noop(call: types.CallbackQuery):
    await call.answer()


@router.callback_query(F.data.startswith("ach:toggle:"))
async def ach_toggle_visibility(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    parts = call.data.split(":")
    if len(parts) != 5:
        await call.answer("Некорректные данные", show_alert=True)
        return
    _, _, ach_id_str, visibility_raw, condition_raw = parts
    try:
        ach_id = int(ach_id_str)
    except ValueError:
        await call.answer("Некорректный идентификатор", show_alert=True)
        return
    visibility = _normalize_visibility_filter(visibility_raw)
    condition = _normalize_condition_filter(condition_raw)

    async with async_session() as session:
        achievement = await session.get(Achievement, ach_id)
        if not achievement:
            await call.answer("Достижение не найдено", show_alert=True)
            return
        achievement.is_visible = not achievement.is_visible
        await session.commit()
        total = await session.scalar(
            select(func.count()).where(UserAchievement.achievement_id == ach_id)
        )

    text = _build_detail_text(achievement, total)
    markup = achievement_detail_inline(
        ach_id,
        achievement.is_visible,
        f"ach:manage:{visibility}:{condition}",
        visibility,
        condition,
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await call.answer("Видимость обновлена")


@router.callback_query(F.data.startswith("ach:delete:"))
async def ach_delete_callback(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    parts = call.data.split(":")
    if len(parts) != 5:
        await call.answer("Некорректные данные", show_alert=True)
        return
    _, _, ach_id_str, visibility_raw, condition_raw = parts
    try:
        ach_id = int(ach_id_str)
    except ValueError:
        await call.answer("Некорректный идентификатор", show_alert=True)
        return
    visibility = _normalize_visibility_filter(visibility_raw)
    condition = _normalize_condition_filter(condition_raw)

    async with async_session() as session:
        achievement = await session.get(Achievement, ach_id)
        if not achievement:
            await call.answer("Достижение не найдено", show_alert=True)
            return
        await session.delete(achievement)
        await session.commit()

    await call.message.edit_text(
        "Достижение удалено.",
        reply_markup=achievement_history_inline(
            f"ach:list:filter:{visibility}:{condition}"
        ),
    )
    await call.answer("Удалено")


@router.callback_query(F.data.startswith("ach:users:"))
async def ach_users_callback(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    parts = call.data.split(":")
    if len(parts) != 6:
        await call.answer("Некорректные данные", show_alert=True)
        return
    _, _, ach_id_str, page_str, visibility_raw, condition_raw = parts
    try:
        ach_id_int = int(ach_id_str)
        page = max(1, int(page_str))
    except ValueError:
        await call.answer("Некорректные данные", show_alert=True)
        return
    visibility = _normalize_visibility_filter(visibility_raw)
    condition = _normalize_condition_filter(condition_raw)

    offset = (page - 1) * USERS_PAGE_SIZE
    limit = USERS_PAGE_SIZE + 1

    async with async_session() as session:
        stmt = (
            select(UserAchievement, User.bot_nickname, User.username, User.tg_username)
            .join(User, User.id == UserAchievement.user_id)
            .where(UserAchievement.achievement_id == ach_id_int)
            .order_by(UserAchievement.earned_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await session.execute(stmt)).all()

    has_next = len(rows) > USERS_PAGE_SIZE
    rows = rows[:USERS_PAGE_SIZE]

    if not rows:
        text = "Пока никто не получал это достижение"
    else:
        text_lines = ["👥 <b>Получатели</b>\n"]
        for entry, bot_nickname, username, tg_username in rows:
            label = bot_nickname or username
            if not label and tg_username:
                label = f"@{tg_username}"
            label = label or f"tg:{entry.tg_id}"
            text_lines.append(
                f"{to_msk(entry.earned_at):%d.%m %H:%M} — {html.escape(str(label))} ({entry.source})"
            )
        text = "\n".join(text_lines)

    markup = achievement_users_navigation_kb(
        ach_id_int,
        page,
        has_prev=page > 1,
        has_next=has_next,
        visibility_filter=visibility,
        condition_filter=condition,
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("ach:history:"))
async def ach_history_callback(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    await call.answer()
    await _send_history(call.message, as_edit=True)


@router.callback_query(F.data.startswith("ach:edit:"))
async def ach_edit_callback(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not await is_admin(call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return
    if not call.message:
        return
    try:
        ach_id = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("Некорректный идентификатор", show_alert=True)
        return

    async with async_session() as session:
        achievement = await session.get(Achievement, ach_id)
        if not achievement:
            await call.answer("Достижение не найдено", show_alert=True)
            return

    await state.set_state(AchievementsState.waiting_for_name)
    await state.update_data(mode="edit", editing_id=ach_id)
    await call.message.answer(
        f"Редактирование достижения #{ach_id}.\nВведите новое название (сейчас: {achievement.name}):"
    )
    await call.answer()


@router.message(StateFilter(AchievementsState.waiting_for_name))
async def ach_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AchievementsState.waiting_for_description)
    await message.answer("Введите описание:")


@router.message(StateFilter(AchievementsState.waiting_for_description))
async def ach_set_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AchievementsState.waiting_for_reward)
    await message.answer("Введите награду (целое число орешков):")


@router.message(StateFilter(AchievementsState.waiting_for_reward))
async def ach_set_reward(message: types.Message, state: FSMContext):
    try:
        reward = int(message.text)
        if reward <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число")
        return

    await state.update_data(reward=reward)
    await state.set_state(AchievementsState.waiting_for_condition_type)
    options = "\n".join(
        f"- {key} — {value['title']}" for key, value in CONDITION_TYPES.items()
    )
    await message.answer(
        "Укажите тип условия выдачи (например, balance_at_least):\n" + options
    )


@router.message(StateFilter(AchievementsState.waiting_for_condition_type))
async def ach_set_condition_type(message: types.Message, state: FSMContext):
    normalized = _normalize_condition_type(message.text)
    if not normalized:
        await message.answer("Неизвестный тип условия, попробуйте ещё раз")
        return

    await state.update_data(condition_type=normalized)
    info = CONDITION_TYPES[normalized]
    if info["needs_value"]:  # type: ignore[index]
        await state.set_state(AchievementsState.waiting_for_condition_value)
        await message.answer(
            "Введите числовое значение условия (например, ID товара или 0 для любых):"
        )
        return
    if info["needs_threshold"]:  # type: ignore[index]
        await state.set_state(AchievementsState.waiting_for_condition_threshold)
        await message.answer(_threshold_prompt(normalized))
        return

    await state.set_state(AchievementsState.waiting_for_visibility)
    await message.answer("Сделать достижение видимым сразу? (да/нет)")


@router.message(StateFilter(AchievementsState.waiting_for_condition_value))
async def ach_set_condition_value(message: types.Message, state: FSMContext):
    raw_value = message.text.strip()
    if raw_value == "-":
        value: int | None = None
    else:
        try:
            value = int(raw_value)
        except ValueError:
            await message.answer("Введите целое число или '-' для пропуска")
            return

    await state.update_data(condition_value=value)
    info = CONDITION_TYPES[(await state.get_data())["condition_type"]]
    if info["needs_threshold"]:  # type: ignore[index]
        await state.set_state(AchievementsState.waiting_for_condition_threshold)
        condition_type = (await state.get_data())["condition_type"]
        await message.answer(_threshold_prompt(condition_type))
    else:
        await state.set_state(AchievementsState.waiting_for_visibility)
        await message.answer("Сделать достижение видимым сразу? (да/нет)")


@router.message(StateFilter(AchievementsState.waiting_for_condition_threshold))
async def ach_set_condition_threshold(message: types.Message, state: FSMContext):
    try:
        threshold = int(message.text)
    except ValueError:
        await message.answer("Введите целое число")
        return
    await state.update_data(condition_threshold=threshold)
    await state.set_state(AchievementsState.waiting_for_visibility)
    await message.answer("Сделать достижение видимым сразу? (да/нет)")


@router.message(StateFilter(AchievementsState.waiting_for_visibility))
async def ach_set_visibility(message: types.Message, state: FSMContext):
    await state.update_data(is_visible=_parse_bool_answer(message.text))
    await state.set_state(AchievementsState.waiting_for_hidden)
    await message.answer("Должно ли достижение быть секретным? (да/нет)")


@router.message(StateFilter(AchievementsState.waiting_for_hidden))
async def ach_set_hidden(message: types.Message, state: FSMContext):
    await state.update_data(is_hidden=_parse_bool_answer(message.text))
    await state.set_state(AchievementsState.waiting_for_manual_grant)
    await message.answer("Выдавать только вручную? (да/нет)")


@router.message(StateFilter(AchievementsState.waiting_for_manual_grant))
async def ach_set_manual_grant(message: types.Message, state: FSMContext):
    await state.update_data(manual_grant_only=_parse_bool_answer(message.text))

    data = await state.get_data()
    mode = data.get("mode", "create")
    condition_type = data.get("condition_type", AchievementConditionType.NONE.value)
    condition_value = data.get("condition_value")
    condition_threshold = data.get("condition_threshold")
    description = data.get("description")
    is_visible = data.get("is_visible", True)
    is_hidden = data.get("is_hidden", False)
    manual_grant_only = data.get("manual_grant_only", False)

    async with async_session() as session:
        if mode == "edit":
            achievement = await session.get(Achievement, data.get("editing_id"))
            if not achievement:
                await message.answer("Не удалось найти достижение для обновления")
                await state.clear()
                return
            achievement.name = data["name"]
            achievement.description = description
            achievement.reward = data["reward"]
            achievement.condition_type = condition_type
            achievement.condition_value = condition_value
            achievement.condition_threshold = condition_threshold
            achievement.is_visible = is_visible
            achievement.is_hidden = is_hidden
            achievement.manual_grant_only = manual_grant_only
            await session.commit()
            await message.answer("Достижение обновлено", reply_markup=admin_achievements_kb())
        else:
            achievement = Achievement(
                name=data["name"],
                description=description,
                reward=data["reward"],
                condition_type=condition_type,
                condition_value=condition_value,
                condition_threshold=condition_threshold,
                is_visible=is_visible,
                is_hidden=is_hidden,
                manual_grant_only=manual_grant_only,
            )
            session.add(achievement)
            await session.commit()
            await message.answer("✅ Достижение создано!", reply_markup=admin_achievements_kb())

    await state.clear()


@router.message(StateFilter(AchievementsState.manual_grant_user))
async def ach_manual_grant_user(message: types.Message, state: FSMContext):
    reference = message.text.strip()
    async with async_session() as session:
        stmt = select(User)
        if reference.startswith("@"):
            username = reference[1:].lower()
            stmt = stmt.where(func.lower(User.tg_username) == username)
        else:
            try:
                numeric = int(reference)
            except ValueError:
                await message.answer("Введите @username или числовой Telegram ID")
                return
            stmt = stmt.where(or_(User.tg_id == numeric, User.id == numeric))
        user = await session.scalar(stmt)

    if not user:
        await message.answer("Пользователь не найден")
        return

    await state.update_data(target_user_id=user.id, target_user_tg=user.tg_id)
    await state.set_state(AchievementsState.manual_grant_achievement)
    await message.answer(
        "Введите ID достижения, которое хотите выдать (посмотрите его в списке):"
    )


@router.message(StateFilter(AchievementsState.manual_grant_achievement))
async def ach_manual_grant_achievement(message: types.Message, state: FSMContext):
    try:
        achievement_id = int(message.text)
    except ValueError:
        await message.answer("Введите целочисленный ID достижения")
        return

    data = await state.get_data()
    async with async_session() as session:
        achievement = await session.get(Achievement, achievement_id)
        if not achievement:
            await message.answer("Достижение не найдено")
            return
        existing = await session.scalar(
            select(UserAchievement).where(
                and_(
                    UserAchievement.user_id == data["target_user_id"],
                    UserAchievement.achievement_id == achievement_id,
                )
            )
        )
    if existing:
        await message.answer("Пользователь уже получил это достижение")
        await state.clear()
        return

    await state.update_data(target_achievement_id=achievement_id)
    await state.set_state(AchievementsState.manual_grant_comment)
    await message.answer("Добавьте комментарий (или отправьте '-' чтобы пропустить):")


@router.message(StateFilter(AchievementsState.manual_grant_comment))
async def ach_manual_grant_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    if comment == "-":
        comment = None

    data = await state.get_data()
    async with async_session() as session:
        user = await session.get(User, data["target_user_id"])
        achievement = await session.get(Achievement, data["target_achievement_id"])
        if not user or not achievement:
            await message.answer("Не удалось загрузить данные, попробуйте снова")
            await state.clear()
            return
        user_achievement = UserAchievement(
            tg_id=data["target_user_tg"],
            user_id=user.id,
            achievement_id=achievement.id,
            source="manual",
            comment=comment,
        )
        session.add(user_achievement)
        await add_nuts(
            session,
            user=user,
            amount=achievement.reward,
            source="achievement",
            transaction_type="achievement",
            reason=f"Admin grant: {achievement.name}",
            metadata={"achievement_id": achievement.id, "issued_by": message.from_user.id if message.from_user else None},
        )
        await session.commit()

    await message.answer(
        "Достижение вручено вручную, пользователь получит награду.",
        reply_markup=admin_achievements_kb(),
    )
    await state.clear()