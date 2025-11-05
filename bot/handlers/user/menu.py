from aiogram import F, Router, types
from sqlalchemy import func, select

from bot.db import Admin, Referral, ReferralReward, User, async_session
from bot.handlers.user.shop import user_shop
from bot.keyboards.main_menu import main_menu, profile_menu, shop_menu, support_menu, play_menu
from bot.utils.referrals import ensure_referral_code


router = Router(name="user_menu")


async def _is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# --- Открыть подменю ---

@router.message(F.text == "👤 Профиль")
async def open_profile_menu(message: types.Message):
    await message.answer("👤 Профиль", reply_markup=profile_menu())


@router.message(F.text == "🛒 Магазин")
async def open_shop_menu(message: types.Message):
    await message.answer("🛒 Магазин", reply_markup=shop_menu())


@router.message(F.text == "🆘 Поддержка")
async def open_support_menu(message: types.Message):
    await message.answer(
        "🆘 Поддержка\nНапишите ваш вопрос, нажав «✍️ Написать в поддержку».",
        reply_markup=support_menu(),
    )


@router.message(F.text == "🎮 Играть")
async def open_play_menu(message: types.Message):
    await message.answer("🎮 Выберите сервер:", reply_markup=play_menu())


@router.message(F.text == "🌐 Сервер #1")
async def play_server_one(message: types.Message):
    await message.answer("🌐 Сервер #1: ссылка появится позже")


@router.message(F.text == "🌐 Сервер #2")
async def play_server_two(message: types.Message):
    await message.answer("🌐 Сервер #2: ссылка появится позже")


@router.message(F.text == "🎁 Предметы")
async def open_shop_items(message: types.Message):
    await user_shop(message, "item")


@router.message(F.text == "🛡 Привилегии")
async def open_shop_privileges(message: types.Message):
    await user_shop(message, "privilege")


@router.message(F.text == "💰 Кеш")
async def open_shop_currency(message: types.Message):
    await user_shop(message, "money")


# --- Назад в главное меню ---

@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: types.Message):
    if not message.from_user:
        return
    is_admin = await _is_admin(message.from_user.id)
    await message.answer("↩ Главное меню", reply_markup=main_menu(is_admin=is_admin))


# --- Профиль / Рефералка ---

@router.message(F.text == "🔗 Реферальная ссылка")
async def profile_ref_link(message: types.Message):
    if not message.from_user:
        return

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
async def profile_promo(message: types.Message):
    await message.answer("🎟 Введите промокод командой: /promo CODE")


@router.message(F.text == "💳 Пополнить баланс")
async def profile_topup(message: types.Message):
    await message.answer("💳 Пополнение: используйте /topup")


@router.message(F.text == "🏆 Топ игроков")
async def profile_top(message: types.Message):
    await message.answer("🏆 Топ игроков: скоро добавим красивый вывод!")


@router.message(F.text == "✍️ Написать в поддержку")
async def support_contact(message: types.Message):
    await message.answer("✍️ Напишите @your_support или ответьте на это сообщение — мы поможем!")
