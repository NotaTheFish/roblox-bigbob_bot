from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from bot.db import (
    Achievement,
    Admin,
    Referral,
    ReferralReward,
    User,
    UserAchievement,
    async_session,
)
from bot.handlers.user.shop import user_shop
from bot.keyboards.main_menu import main_menu, profile_menu, shop_menu
from bot.services.profile_renderer import ProfileView, render_profile
from bot.services.servers import get_ordered_servers, get_server_by_id
from bot.services.stats import format_top_users, get_top_users
from bot.services.user_titles import normalize_titles
from bot.states.user_states import ProfileEditState, PromoInputState
from bot.utils.referrals import ensure_referral_code
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE


router = Router(name="user_menu")

MAX_ABOUT_LENGTH = 500


def _profile_edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏷 Активный титул", callback_data="profile_edit:titles")],
            [
                InlineKeyboardButton(
                    text="🏆 Выбрать достижение", callback_data="profile_edit:achievement"
                )
            ],
            [InlineKeyboardButton(text="📝 Изменить «О себе»", callback_data="profile_edit:about")],
        ]
    )


def _user_profile_stmt(tg_id: int):
    return (
        select(User)
        .options(selectinload(User.selected_achievement))
        .where(User.tg_id == tg_id)
        .limit(1)
    )


def _shorten_button_text(text: str, limit: int = 32) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


async def _prompt_edit_menu(message: types.Message, state: FSMContext, text: str) -> None:
    await state.set_state(ProfileEditState.choosing_action)
    await state.update_data(title_options=[], achievement_options=[])
    await message.answer(text, reply_markup=_profile_edit_keyboard())


async def _set_profile_mode(state: FSMContext, active: bool) -> None:
    current_state = await state.get_state()

    if not active:
        profile_states = {
            PromoInputState.waiting_for_code.state,
            ProfileEditState.choosing_action.state,
            ProfileEditState.editing_about.state,
            ProfileEditState.choosing_title.state,
            ProfileEditState.choosing_achievement.state,
        }
        if current_state in profile_states:
            await state.clear()
        await state.update_data(in_profile=False)
        return

    await state.update_data(in_profile=True)


async def _is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# --- Открыть подменю ---

@router.message(F.text == "👤 Профиль")
async def open_profile_menu(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    await _set_profile_mode(state, True)

    async with async_session() as session:
        user = await session.scalar(_user_profile_stmt(message.from_user.id))

    if not user:
        return await message.answer("❗ Сначала нажмите /start")

    titles = normalize_titles(user.titles)
    profile_text = render_profile(
        ProfileView(
            heading="👤 <b>Ваш профиль</b>",
            tg_username=f"@{user.tg_username}" if user.tg_username else "",
            tg_id=user.tg_id,
            roblox_username=user.username or "",
            roblox_id=user.roblox_id or "",
            balance=user.balance,
            titles=titles,
            selected_title=user.selected_title,
            selected_achievement=(
                user.selected_achievement.name if user.selected_achievement else None
            ),
            about_text=user.about_text,
            created_at=user.created_at,
        )
    )

    await message.answer(profile_text, parse_mode="HTML", reply_markup=profile_menu())


@router.message(F.text == "🛒 Магазин")
async def open_shop_menu(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, False)
    await message.answer("🛒 Магазин", reply_markup=shop_menu())


@router.message(F.text == "🎮 Играть")
async def open_play_menu(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, False)

    servers = await get_ordered_servers()
    if not servers:
        await message.answer("ℹ️ Доступных серверов пока нет")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Сервер {idx}",
                    url=server.url,
                )
                if server.url
                else InlineKeyboardButton(
                    text=f"Сервер {idx}",
                    callback_data=f"server_closed:{server.id}",
                )
            ]
            for idx, server in enumerate(servers, start=1)
        ]
    )

    await message.answer("🎮 Выберите сервер:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("server_closed:"))
async def handle_server_closed(callback: types.CallbackQuery) -> None:
    data = callback.data or ""
    try:
        _, server_id_raw = data.split(":", 1)
        server_id = int(server_id_raw)
    except (ValueError, AttributeError):
        server_info = None
    else:
        server_info = await get_server_by_id(server_id)

    message = (
        (server_info.closed_message or SERVER_DEFAULT_CLOSED_MESSAGE)
        if server_info
        else SERVER_DEFAULT_CLOSED_MESSAGE
    )

    await callback.answer(message, show_alert=True)


@router.message(F.text == "🎁 Предметы")
async def open_shop_items(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, False)
    await user_shop(message, "item")


@router.message(F.text == "🛡 Привилегии")
async def open_shop_privileges(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, False)
    await user_shop(message, "privilege")


@router.message(F.text == "💰 Кеш")
async def open_shop_currency(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, False)
    await user_shop(message, "money")


# --- Назад в главное меню ---

@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    await _set_profile_mode(state, False)
    is_admin = await _is_admin(message.from_user.id)
    await message.answer("↩ Главное меню", reply_markup=main_menu(is_admin=is_admin))


# --- Профиль / Рефералка ---

@router.message(F.text == "🔗 Реферальная ссылка")
async def profile_ref_link(message: types.Message, state: FSMContext):
    if not message.from_user:
        return

    await _set_profile_mode(state, True)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            return await message.answer("❗ Сначала нажмите /start")

        code = await ensure_referral_code(session, user)

        invited = (
            await session.execute(
                select(func.count(Referral.id)).where(Referral.referrer_id == user.id)
            )
        ).scalar_one()

        total_rewards = (
            await session.execute(
                select(func.coalesce(func.sum(ReferralReward.amount), 0)).where(
                    ReferralReward.referrer_id == user.id,
                    ReferralReward.status == "granted",
                )
            )
        ).scalar_one()

        await session.commit()

    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}" if bot_info.username else code

    await message.answer(
        "🔗 <b>Ваша реферальная ссылка</b>\n"
        f"{link}\n\n"
        f"👥 Приглашено: {invited}\n"
        f"💰 Получено бонусов: {total_rewards}",
        parse_mode="HTML",
    )


@router.message(F.text == "🎟 Промокод")
async def profile_promo(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, True)
    await state.set_state(PromoInputState.waiting_for_code)
    await message.answer("🎟 Введите код прямо в чат")


@router.message(F.text == "💳 Пополнить баланс")
async def profile_topup(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, True)
    await message.answer("💳 Пополнение: используйте /topup")


@router.message(F.text == "🏆 Топ игроков")
async def profile_top(message: types.Message, state: FSMContext):
    await _set_profile_mode(state, True)
    top_users = await get_top_users()
    await message.answer(format_top_users(top_users))


@router.message(F.text == "✏️ Редактировать профиль")
async def profile_edit(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    await _set_profile_mode(state, True)

    async with async_session() as session:
        exists = await session.scalar(select(User.id).where(User.tg_id == message.from_user.id))

    if not exists:
        return await message.answer("❗ Сначала нажмите /start")

    await _prompt_edit_menu(message, state, ✏️ Что хотите изменить?")


@router.callback_query(F.data == "profile_edit:about")
async def profile_edit_about(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not call.message:
        return await call.answer()

    async with async_session() as session:
        exists = await session.scalar(select(User.id).where(User.tg_id == call.from_user.id))

    if not exists:
        await state.clear()
        await call.message.answer("❗ Сначала нажмите /start")
        return await call.answer()

    await state.set_state(ProfileEditState.editing_about)
    await state.update_data(title_options=[], achievement_options=[])
    await call.message.answer(
        (
            "📝 Отправьте новый текст «О себе» (до 500 символов).\n"
            "Чтобы очистить описание, отправьте «-».\n"
            "Для отмены напишите «Отмена»."
        )
    )
    await call.answer()


@router.message(StateFilter(ProfileEditState.editing_about))
async def profile_save_about(message: types.Message, state: FSMContext):
    if not message.from_user:
        await state.clear()
        return

    raw_text = (message.text or "").strip()
    lower_text = raw_text.lower()

    if lower_text in {"отмена", "cancel"}:
        await _prompt_edit_menu(message, state, "✏️ Редактирование отменено")
        return

    if raw_text == "-":
        about_value = None
    else:
        if not raw_text:
            return await message.answer("❌ Текст не должен быть пустым")
        if len(raw_text) > MAX_ABOUT_LENGTH:
            return await message.answer(
                f"❌ Описание не должно превышать {MAX_ABOUT_LENGTH} символов"
            )
        about_value = raw_text

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        if not user:
            await state.clear()
            return await message.answer("❗ Сначала нажмите /start")

        user.about_text = about_value
        await session.commit()

    await _prompt_edit_menu(message, state, "✅ Описание обновлено")


@router.callback_query(F.data == "profile_edit:titles")
async def profile_pick_title(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not call.message:
        return await call.answer()

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))

    if not user:
        await state.clear()
        await call.message.answer("❗ Сначала нажмите /start")
        return await call.answer()

    titles = normalize_titles(user.titles)
    if not titles:
        return await call.answer("У вас пока нет титулов", show_alert=True)

    builder = InlineKeyboardBuilder()
    for idx, title in enumerate(titles):
        builder.button(
            text=_shorten_button_text(title), callback_data=f"profile_title:{idx}"
        )
    builder.button(text="❌ Без титула", callback_data="profile_title:clear")
    builder.adjust(1)

    await state.update_data(title_options=titles)
    await state.set_state(ProfileEditState.choosing_title)
    await call.message.answer("Выберите титул:", reply_markup=builder.as_markup())
    await call.answer()


@router.callback_query(
    StateFilter(ProfileEditState.choosing_title), F.data.startswith("profile_title:")
)
async def profile_apply_title(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not call.message:
        return await call.answer()

    data = await state.get_data()
    titles: list[str] = data.get("title_options", [])

    _, raw_idx = (call.data or "").split(":", 1)
    new_title: str | None
    if raw_idx == "clear":
        new_title = None
    else:
        try:
            idx = int(raw_idx)
            new_title = titles[idx]
        except (ValueError, IndexError):
            return await call.answer("Некорректный выбор", show_alert=True)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user:
            await state.clear()
            await call.message.answer("❗ Сначала нажмите /start")
            return await call.answer()

        user.selected_title = new_title
        await session.commit()

    await _prompt_edit_menu(call.message, state, "✅ Активный титул обновлён")
    await call.answer("Сохранено")


@router.callback_query(F.data == "profile_edit:achievement")
async def profile_pick_achievement(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not call.message:
        return await call.answer()

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))

        if not user:
            await state.clear()
            await call.message.answer("❗ Сначала нажмите /start")
            return await call.answer()

        rows = (
            await session.execute(
                select(Achievement.id, Achievement.name)
                .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
                .where(UserAchievement.user_id == user.id)
                .order_by(Achievement.name)
            )
        ).all()

    if not rows:
        return await call.answer("У вас пока нет достижений", show_alert=True)

    builder = InlineKeyboardBuilder()
    achievement_options: list[tuple[int, str | None]] = []
    for idx, row in enumerate(rows):
        achievement_options.append((row.id, row.name))
        builder.button(
            text=_shorten_button_text(row.name or f"Достижение {idx + 1}"),
            callback_data=f"profile_achievement:{idx}",
        )
    builder.button(text="❌ Без достижения", callback_data="profile_achievement:clear")
    builder.adjust(1)

    await state.update_data(achievement_options=achievement_options)
    await state.set_state(ProfileEditState.choosing_achievement)
    await call.message.answer("Выберите достижение:", reply_markup=builder.as_markup())
    await call.answer()


@router.callback_query(
    StateFilter(ProfileEditState.choosing_achievement),
    F.data.startswith("profile_achievement:"),
)
async def profile_apply_achievement(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not call.message:
        return await call.answer()

    data = await state.get_data()
    options: list[tuple[int, str | None]] = data.get("achievement_options", [])

    _, raw_idx = (call.data or "").split(":", 1)
    new_achievement_id: int | None
    if raw_idx == "clear":
        new_achievement_id = None
    else:
        try:
            idx = int(raw_idx)
            option = options[idx]
            new_achievement_id = int(option[0])
        except (ValueError, IndexError, TypeError):
            return await call.answer("Некорректный выбор", show_alert=True)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user:
            await state.clear()
            await call.message.answer("❗ Сначала нажмите /start")
            return await call.answer()

        user.selected_achievement_id = new_achievement_id
        await session.commit()

    await _prompt_edit_menu(call.message, state, "✅ Выбранное достижение обновлено")
    await call.answer("Сохранено")