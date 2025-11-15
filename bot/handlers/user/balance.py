from __future__ import annotations

import logging
from uuid import uuid4

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.constants.stars import STARS_PACKAGES_BY_CODE
from bot.db import Invoice, User, async_session
from bot.keyboards.user_keyboards import stars_packages_kb
from bot.states.user_states import TopUpState


router = Router(name="user_balance")
logger = logging.getLogger(__name__)


def _build_payment_keyboard(invoice_link: str | None) -> InlineKeyboardMarkup | None:
    if not invoice_link:
        return None

    builder = InlineKeyboardBuilder()
    builder.button(text="💫 Оплатить в Stars", url=invoice_link)
    return builder.as_markup()


async def _create_invoice_link(
    bot: Bot,
    *,
    product_id: str,
    provider_invoice_id: str,
) -> str | None:
    create_link = getattr(bot, "create_invoice_link", None)
    if not callable(create_link):
        return None

    try:
        return await create_link(product_id=product_id, payload=provider_invoice_id)
    except TypeError:  # pragma: no cover - depends on aiogram version
        logger.warning("Bot.create_invoice_link signature mismatch", exc_info=True)
    except Exception:  # pragma: no cover - network/runtime errors
        logger.exception("Failed to request Telegram invoice link")
    return None


@router.message(Command("topup", "balance"))
async def topup_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Выберите пакет пополнения:", reply_markup=stars_packages_kb()
    )
    await state.set_state(TopUpState.waiting_for_package)


@router.callback_query(F.data == "pay_cancel", StateFilter(TopUpState.waiting_for_package))
async def topup_cancel(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("❌ Отменено")
    await state.clear()
    await call.answer()


@router.callback_query(
    F.data.startswith("stars_pack:"), StateFilter(TopUpState.waiting_for_package)
)
async def topup_create_stars_invoice(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        await call.answer("Ошибка — перезапустите бота", show_alert=True)
        return

    package_code = call.data.split(":", maxsplit=1)[1]
    package = STARS_PACKAGES_BY_CODE.get(package_code)
    if not package:
        await call.answer("Этот пакет недоступен", show_alert=True)
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user:
            await state.clear()
            await call.message.answer("Сначала нажмите /start, чтобы зарегистрироваться")
            await call.answer()
            return

        provider_invoice_id = f"stars:{uuid4().hex}"
        invoice = Invoice(
            user_id=user.id,
            telegram_id=user.tg_id,
            provider="telegram_stars",
            provider_invoice_id=provider_invoice_id,
            amount_rub=package.stars_price,
            amount_nuts=package.nuts_amount,
            metadata_json={
                "package_code": package.code,
                "product_id": package.product_id,
            },
        )
        session.add(invoice)
        await session.flush()

        invoice_link = await _create_invoice_link(
            call.bot,
            product_id=package.product_id,
            provider_invoice_id=provider_invoice_id,
        )

        keyboard = _build_payment_keyboard(invoice_link)
        text = (
            f"💫 Счёт #{invoice.id} на {package.title}\n"
            f"К оплате: {package.stars_price}⭐️\n"
            "После успешной оплаты орехи будут зачислены автоматически."
        )

        await session.commit()

    await call.message.answer(text, reply_markup=keyboard)
    await state.clear()
    await call.answer("Счёт создан", show_alert=False)