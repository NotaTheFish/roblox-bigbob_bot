from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Iterable

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from bot.db import (
    Achievement,
    AchievementConditionType,
    GameProgress,
    Payment,
    PromocodeRedemption,
    Product,
    Purchase,
    Referral,
    User,
    UserAchievement,
    async_session,
)
from bot.utils.time import to_msk


router = Router(name="user_achievements")


@dataclass
class AchievementMetrics:
    balance: int = 0
    nuts_balance: int = 0
    purchase_count: int = 0
    payments_sum: int = 0
    referral_count: int = 0
    time_in_game_minutes: int | None = None
    spent_sum: int = 0
    promocode_redemptions: int = 0
    purchased_products: set[int] | None = None
    purchased_product_slugs: set[str] | None = None


@dataclass
class AchievementContext:
    user: User
    achievements: list[Achievement]
    owned: dict[int, UserAchievement]
    metrics: AchievementMetrics


def _achievements_entry_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 По категориям", callback_data="achievements:view:categories")
    builder.button(text="📜 Все достижения", callback_data="achievements:view:all")
    builder.adjust(1)
    return builder.as_markup()


def _achievements_categories_keyboard(
    categories: Iterable[tuple[str, str, int, int]]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slug, name, completed, total in categories:
        suffix = f" ({completed}/{total})" if total else ""
        builder.button(text=f"{name}{suffix}", callback_data=f"achievements:category:{slug}")
    builder.button(text="📜 Все достижения", callback_data="achievements:view:all")
    builder.button(text="⬅️ К выбору", callback_data="achievements:view:menu")
    builder.adjust(1)
    return builder.as_markup()


def _achievements_view_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 По категориям", callback_data="achievements:view:categories")
    builder.button(text="⬅️ К выбору", callback_data="achievements:view:menu")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("achievements"))
@router.message(F.text == "🏆 Достижения игрока")
async def achievements_entry(message: types.Message):
    if not message.from_user:
        return

    await message.answer(
        "🏆 <b>Достижения игрока</b>\nВыберите способ отображения:",
        parse_mode="HTML",
        reply_markup=_achievements_entry_keyboard(),
    )


@router.callback_query(F.data == "achievements:view:menu")
async def achievements_entry_callback(call: types.CallbackQuery):
    if not call.from_user or not call.message:
        return await call.answer()

    await call.message.edit_text(
        "🏆 <b>Достижения игрока</b>\nВыберите способ отображения:",
        reply_markup=_achievements_entry_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "achievements:view:all")
async def achievements_view_all(call: types.CallbackQuery):
    if not call.from_user or not call.message:
        return await call.answer()

    context = await _load_achievement_context(call.from_user.id)
    if not context:
        return await call.answer("Сначала нажмите /start", show_alert=True)

    text = _render_achievement_list(context)
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_achievements_view_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data == "achievements:view:categories")
async def achievements_view_categories(call: types.CallbackQuery):
    if not call.from_user or not call.message:
        return await call.answer()

    context = await _load_achievement_context(call.from_user.id)
    if not context:
        return await call.answer("Сначала нажмите /start", show_alert=True)

    categories = _group_by_category(context)
    text_lines = ["📂 <b>Категории достижений</b>"]
    for _, name, completed, total in categories:
        suffix = f" ({completed}/{total})" if total else ""
        text_lines.append(f"• {html.escape(name)}{suffix}")

    await call.message.edit_text(
        "\n".join(text_lines),
        reply_markup=_achievements_categories_keyboard(categories),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("achievements:category:"))
async def achievements_view_category(call: types.CallbackQuery):
    if not call.from_user or not call.message:
        return await call.answer()

    _, _, slug = (call.data or "").split(":", 2)
    context = await _load_achievement_context(call.from_user.id)
    if not context:
        return await call.answer("Сначала нажмите /start", show_alert=True)

    categories = _group_by_category(context)
    category_map = {cat_slug: name for cat_slug, name, _, _ in categories}
    category_name = category_map.get(slug)
    if not category_name:
        return await call.answer("Категория не найдена", show_alert=True)

    text = _render_category(context, slug, category_name)
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=_achievements_categories_keyboard(categories),
    )
    await call.answer()


async def _load_achievement_context(tg_id: int) -> AchievementContext | None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None

        achievements = (await session.scalars(select(Achievement))).all()
        owned_rows = (
            await session.execute(
                select(UserAchievement)
                .where(UserAchievement.user_id == user.id)
                .order_by(UserAchievement.earned_at)
            )
        ).scalars()
        owned: dict[int, UserAchievement] = {row.achievement_id: row for row in owned_rows}
        metrics = await _load_metrics(session, user)

    return AchievementContext(
        user=user,
        achievements=achievements,
        owned=owned,
        metrics=metrics,
    )


async def _load_metrics(session, user: User) -> AchievementMetrics:
    metrics = AchievementMetrics(
        balance=user.balance or 0,
        nuts_balance=user.nuts_balance or 0,
    )

    metrics.purchase_count = (
        await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.user_id == user.id, Purchase.status == "completed"
            )
        )
        or 0
    )

    metrics.payments_sum = (
        await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.user_id == user.id, Payment.status.in_(["applied", "processed"])
            )
        )
        or 0
    )

    metrics.referral_count = (
        await session.scalar(
            select(func.count(Referral.id)).where(
                Referral.referrer_id == user.id, Referral.confirmed.is_(True)
            )
        )
        or 0
    )

    metrics.time_in_game_minutes = await _load_playtime_minutes(session, user)

    metrics.spent_sum = (
        await session.scalar(
            select(func.coalesce(func.sum(Purchase.total_price), 0)).where(
                Purchase.user_id == user.id, Purchase.status == "completed"
            )
        )
        or 0
    )

    metrics.promocode_redemptions = (
        await session.scalar(
            select(func.count(PromocodeRedemption.id)).where(
                PromocodeRedemption.user_id == user.id
            )
        )
        or 0
    )

    product_rows = await session.execute(
        select(Product.id, Product.slug)
        .join(Purchase, Purchase.product_id == Product.id)
        .where(Purchase.user_id == user.id, Purchase.status == "completed")
    )
    purchased_products: set[int] = set()
    purchased_product_slugs: set[str] = set()
    for prod_id, slug in product_rows:
        if prod_id is not None:
            purchased_products.add(prod_id)
        if slug:
            purchased_product_slugs.add(slug)
    metrics.purchased_products = purchased_products
    metrics.purchased_product_slugs = purchased_product_slugs

    return metrics


async def _load_playtime_minutes(session, user: User) -> int | None:
    if not user.roblox_id:
        return None

    progress = await session.scalar(
        select(GameProgress.progress)
        .where(GameProgress.roblox_user_id == str(user.roblox_id))
        .order_by(GameProgress.updated_at.desc())
        .limit(1)
    )
    if not isinstance(progress, dict):
        return None

    for key in (
        "time_in_game",
        "timeInGame",
        "play_time",
        "playTime",
        "playtime",
        "minutes_played",
    ):
        value = progress.get(key)
        if isinstance(value, (int, float)):
            return int(value)

    return None


def _group_by_category(context: AchievementContext) -> list[tuple[str, str, int, int]]:
    groups: dict[str, list[Achievement]] = {}
    titles: dict[str, str] = {}
    for achievement in context.achievements:
        raw_name = "Без категории"
        if isinstance(achievement.metadata_json, dict):
            raw_name = achievement.metadata_json.get("category") or raw_name
        slug = _slugify_category(raw_name)
        groups.setdefault(slug, []).append(achievement)
        titles[slug] = raw_name or "Без категории"

    result: list[tuple[str, str, int, int]] = []
    for slug, items in groups.items():
        total = len(items)
        completed = sum(1 for item in items if item.id in context.owned)
        result.append((slug, titles[slug], completed, total))

    result.sort(key=lambda row: row[1].lower())
    return result


def _render_achievement_list(context: AchievementContext) -> str:
    lines = ["🏆 <b>Все достижения</b>\n"]
    for achievement in sorted(context.achievements, key=lambda a: a.name.lower()):
        lines.append(_format_achievement_line(achievement, context))
    return "\n\n".join(lines)


def _render_category(context: AchievementContext, slug: str, title: str) -> str:
    items = [
        ach
        for ach in context.achievements
        if _slugify_category(_category_name(ach)) == slug
    ]
    lines = [f"📂 <b>{html.escape(title)}</b>\n"]
    for achievement in sorted(items, key=lambda a: a.name.lower()):
        lines.append(_format_achievement_line(achievement, context))
    return "\n\n".join(lines)


def _format_achievement_line(achievement: Achievement, context: AchievementContext) -> str:
    owned_entry = context.owned.get(achievement.id)
    status_icon = "✅" if owned_entry else "❌"
    hidden_icon = " 🕵️" if achievement.is_hidden else ""
    name = html.escape(achievement.name)
    reward = achievement.reward or 0
    lines = [f"{status_icon} <b>{name}</b>{hidden_icon} — {reward}🥜"]

    if achievement.description:
        lines.append(f"<i>{html.escape(achievement.description)}</i>")

    if owned_entry and owned_entry.earned_at:
        lines.append(f"Получено: {to_msk(owned_entry.earned_at):%d.%m.%Y %H:%M} МСК")
    else:
        lines.append("Не получено")

    progress_text = _format_progress(achievement, context)
    if progress_text:
        lines.append(progress_text)

    return "\n".join(lines)


def _format_progress(achievement: Achievement, context: AchievementContext) -> str | None:
    current, target = _achievement_progress(achievement, context)
    if current is None or target is None:
        return None

    if target <= 0:
        return None

    return f"Прогресс: {current}/{target}"


def _normalize_product_condition_value(
    raw_value: object,
) -> tuple[int | None, str | None]:
    if raw_value is None:
        return None, None

    if isinstance(raw_value, int):
        return raw_value, None

    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            return None, None
        if value.isdigit():
            return int(value), None
        return None, value

    return None, None


def _achievement_progress(
    achievement: Achievement, context: AchievementContext
) -> tuple[int | None, int | None]:
    condition_type = achievement.condition_type or AchievementConditionType.NONE
    if isinstance(condition_type, str):
        try:
            condition_type = AchievementConditionType(condition_type)
        except ValueError:
            return None, None

    threshold = achievement.condition_threshold or 0
    metrics = context.metrics

    if condition_type is AchievementConditionType.BALANCE_AT_LEAST:
        return metrics.balance, threshold
    if condition_type is AchievementConditionType.NUTS_AT_LEAST:
        return metrics.nuts_balance, threshold
    if condition_type is AchievementConditionType.PURCHASE_COUNT_AT_LEAST:
        return metrics.purchase_count, threshold
    if condition_type is AchievementConditionType.PAYMENTS_SUM_AT_LEAST:
        return metrics.payments_sum, threshold
    if condition_type is AchievementConditionType.REFERRAL_COUNT_AT_LEAST:
        return metrics.referral_count, threshold
    if condition_type is AchievementConditionType.TIME_IN_GAME_AT_LEAST:
        return metrics.time_in_game_minutes, threshold
    if condition_type is AchievementConditionType.SPENT_SUM_AT_LEAST:
        return metrics.spent_sum, threshold
    if condition_type is AchievementConditionType.PROMOCODE_REDEMPTION_COUNT_AT_LEAST:
        return metrics.promocode_redemptions, threshold
    if condition_type is AchievementConditionType.PRODUCT_PURCHASE:
        product_id, product_slug = _normalize_product_condition_value(
            achievement.condition_value
        )
        if product_id is None and not product_slug:
            return None, None
        purchased = (
            1
            if (
                product_id in (metrics.purchased_products or set())
                or product_slug in (metrics.purchased_product_slugs or set())
            )
            else 0
        )
        return purchased, 1
    if condition_type is AchievementConditionType.PROFILE_PHRASE_STREAK:
        phrase: str | None = None
        if isinstance(achievement.metadata_json, dict):
            value = achievement.metadata_json.get("phrase")
            if isinstance(value, str):
                phrase = value.strip()
        if not phrase:
            return None, threshold

        about_text = (context.user.about_text or "").lower()
        updated_at = context.user.about_text_updated_at
        if phrase.lower() not in about_text or not updated_at:
            return 0, threshold

        elapsed = datetime.now(timezone.utc) - updated_at
        elapsed_hours = int(elapsed.total_seconds() // 3600)
        return elapsed_hours, threshold

    return None, None


def _slugify_category(raw: str) -> str:
    value = (raw or "").strip().lower()
    value = re.sub(r"[^a-z0-9а-яё]+", "-", value, flags=re.IGNORECASE).strip("-")
    return value or "category"


def _category_name(achievement: Achievement) -> str:
    if isinstance(achievement.metadata_json, dict):
        return achievement.metadata_json.get("category") or "Без категории"
    return "Без категории"
