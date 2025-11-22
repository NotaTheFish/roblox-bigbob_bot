from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.config import (
    TON_INVOICE_TTL_SECONDS,
    TON_PAYMENT_MARKUP_PERCENT,
    WALLET_PAY_API_BASE,
    WALLET_PAY_API_KEY,
    WALLET_PAY_SHOP_ID,
)
from bot.constants.stars import STARS_PACKAGES, STARS_PACKAGES_BY_CODE
from bot.db import Invoice, User, async_session
from bot.keyboards.user_keyboards import stars_packages_kb, ton_packages_kb, topup_method_kb
from bot.services.settings import get_ton_rate
from bot.services.wallet import (
    WalletPayClient,
    WalletPayConfigurationError,
    WalletPayError,
)
from bot.states.user_states import TopUpState


router = Router(name="user_balance")
logger = logging.getLogger(__name__)

TON_DECIMAL_QUANT = Decimal("0.000000001")
TOPUP_UNAVAILABLE_TEXT = (
    "Этот способ пополнения временно недоступен. Пожалуйста, попробуйте позже."
)


async def _deny_topup(
    call: types.CallbackQuery,
    state: FSMContext,
    *,
    alert: bool = False,
    close_keyboard: bool = False,
) -> None:
    if close_keyboard and call.message:
        await call.message.edit_reply_markup(reply_markup=None)

    await state.clear()

    if call.message:
        await call.message.answer(TOPUP_UNAVAILABLE_TEXT)

    await call.answer(TOPUP_UNAVAILABLE_TEXT if alert else None, show_alert=alert)


def _build_payment_keyboard(
    invoice_link: str | None, *, label: str = "💫 Оплатить в Stars"
) -> InlineKeyboardMarkup | None:
    if not invoice_link:
        return None

    builder = InlineKeyboardBuilder()
    builder.button(text=label, url=invoice_link)
    return builder.as_markup()


def _quantize_ton_amount(value: Decimal) -> Decimal:
    return value.quantize(TON_DECIMAL_QUANT, rounding=ROUND_HALF_UP)


def _format_ton_amount(value: Decimal) -> str:
    quantized = _quantize_ton_amount(value)
    formatted = format(quantized, "f").rstrip("0").rstrip(".")
    return f"{formatted or '0'} TON"


def _calculate_ton_amount(nuts: int, rate: Decimal) -> Decimal:
    if rate <= 0:
        raise ValueError("TON rate must be positive")
    base = Decimal(nuts) / rate
    multiplier = Decimal("1") + (TON_PAYMENT_MARKUP_PERCENT / Decimal("100"))
    return _quantize_ton_amount(base * multiplier)


def _wallet_client() -> WalletPayClient:
    return WalletPayClient(
        api_base=WALLET_PAY_API_BASE,
        api_key=WALLET_PAY_API_KEY,
        store_id=WALLET_PAY_SHOP_ID,
    )


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
        "Выберите способ пополнения:", reply_markup=topup_method_kb()
    )
    await state.set_state(TopUpState.choosing_method)


@router.callback_query(
    F.data == "pay_cancel",
    StateFilter(
        TopUpState.choosing_method,
        TopUpState.waiting_for_package,
        TopUpState.waiting_for_ton_package,
    ),
)
async def topup_cancel(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("❌ Отменено")
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "topup:stars", StateFilter(TopUpState.choosing_method))
async def topup_choose_stars(call: types.CallbackQuery, state: FSMContext):
    if not call.message:
        return await call.answer()

    await _deny_topup(call, state, alert=True, close_keyboard=True)


@router.callback_query(F.data == "topup:ton", StateFilter(TopUpState.choosing_method))
async def topup_choose_ton(call: types.CallbackQuery, state: FSMContext):
    if not call.message:
        return await call.answer()

    await _deny_topup(call, state, alert=True, close_keyboard=True)


@router.callback_query(
    F.data.startswith("stars_pack:"), StateFilter(TopUpState.waiting_for_package)
)
async def topup_create_stars_invoice(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        await call.answer("Ошибка — перезапустите бота", show_alert=True)
        return

    await _deny_topup(call, state, alert=True, close_keyboard=True)
    return  # Логика ниже сохранена для будущего включения платежей

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
            payment_method="stars",
            amount_rub=package.stars_price,
            amount_nuts=package.nuts_amount,
            currency_code="STAR",
            currency_amount=package.stars_price,
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


@router.callback_query(
    F.data.startswith("ton_pack:"), StateFilter(TopUpState.waiting_for_ton_package)
)
async def topup_create_ton_invoice(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        await call.answer("Ошибка — перезапустите бота", show_alert=True)
        return

    await _deny_topup(call, state, alert=True, close_keyboard=True)
    return  # Логика ниже сохранена для будущего включения платежей

    package_code = call.data.split(":", maxsplit=1)[1]
    package = STARS_PACKAGES_BY_CODE.get(package_code)
    if not package:
        await call.answer("Этот пакет недоступен", show_alert=True)
        return

    if not WALLET_PAY_API_KEY or not WALLET_PAY_SHOP_ID:
        await call.answer("Оплата через @wallet не настроена", show_alert=True)
        return

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
        if not user:
            await state.clear()
            await call.message.answer("Сначала нажмите /start, чтобы зарегистрироваться")
            await call.answer()
            return

        ton_rate = await get_ton_rate(session)
        if not ton_rate:
            await call.answer("Оплата в TON временно недоступна", show_alert=True)
            return

        try:
            ton_amount = _calculate_ton_amount(package.nuts_amount, ton_rate)
        except ValueError:
            await call.answer("Неверный курс для TON оплаты", show_alert=True)
            return

        external_invoice_id = f"ton:{uuid4().hex}"

        try:
            wallet_invoice = await _wallet_client().create_invoice(
                external_invoice_id=external_invoice_id,
                amount=ton_amount,
                currency_code="TON",
                description=f"{package.title}",
                expires_in=max(TON_INVOICE_TTL_SECONDS, 60),
                customer_telegram_id=user.tg_id,
                metadata={
                    "package_code": package.code,
                    "nuts_amount": package.nuts_amount,
                },
            )
        except WalletPayConfigurationError:
            await call.answer("Оплата через @wallet не настроена", show_alert=True)
            return
        except WalletPayError as exc:
            logger.exception("Wallet Pay invoice error: %s", exc)
            await call.answer("Не удалось создать счёт", show_alert=True)
            return

        expires_at = wallet_invoice.expires_at
        if not expires_at:
            expires_at = datetime.now(tz=timezone.utc) + timedelta(
                seconds=TON_INVOICE_TTL_SECONDS
            )

        invoice = Invoice(
            user_id=user.id,
            telegram_id=user.tg_id,
            provider="wallet_pay",
            provider_invoice_id=wallet_invoice.provider_invoice_id,
            external_invoice_id=external_invoice_id,
            payment_method="ton",
            amount_rub=0,
            amount_nuts=package.nuts_amount,
            currency_code=wallet_invoice.currency_code,
            currency_amount=ton_amount,
            ton_rate_at_invoice=ton_rate,
            ttl_metadata={
                "ttl_seconds": TON_INVOICE_TTL_SECONDS,
                "wallet_expires_at": expires_at.isoformat(),
            },
            rate_snapshot={
                "ton_to_nuts_rate": str(ton_rate),
                "markup_percent": str(TON_PAYMENT_MARKUP_PERCENT),
            },
            metadata_json={
                "package_code": package.code,
                "wallet_pay_link": wallet_invoice.pay_link,
                "wallet_status": wallet_invoice.status,
            },
            expires_at=expires_at,
        )
        session.add(invoice)
        await session.commit()

    keyboard = _build_payment_keyboard(
        wallet_invoice.pay_link, label="⚡ Оплатить в @wallet"
    )
    text = (
        f"⚡ Счёт #{invoice.id} на {package.title}\n"
        f"К оплате: {_format_ton_amount(ton_amount)}\n"
        "После успешной оплаты орехи будут зачислены автоматически."
    )

    await call.message.answer(text, reply_markup=keyboard)
    await state.clear()
    await call.answer("Счёт создан", show_alert=False)