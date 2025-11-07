from aiogram import F, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import func, select
from bot.db import Admin, Referral, ReferralReward, User, async_session
from bot.handlers.user.shop import user_shop
from bot.keyboards.main_menu import main_menu, profile_menu, shop_menu
from bot.states.user_states import PromoInputState
from bot.utils.referrals import ensure_referral_code
from bot.services.stats import format_top_users, get_top_users
from bot.services.servers import get_ordered_servers, get_server_by_id
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE


router = Router(name="user_menu")


async def _set_profile_mode(state: FSMContext, active: bool) -> None:
    current_state = await state.get_state()

    if not active:
        if current_state == PromoInputState.waiting_for_code.state:
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
    await _set_profile_mode(state, True)
    await message.answer("👤 Профиль", reply_markup=profile_menu())


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
                    text=server.name,
                    url=server.url,
                )
                if server.url
                else InlineKeyboardButton(
                    text=server.name,
                    callback_data=f"server_closed:{server.id}",
                )
            ]
            for server in servers
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
    await _set_profile_mode(state, True)
    await message.answer(
        "✏️ Редактирование профиля: функциональность появится в ближайшее время"
    )