from __future__ import annotations

from datetime import datetime
from typing import Optional

from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import (
    LogEntry,
    Product,
    Purchase,
    Referral,
    ReferralReward,
    User,
    async_session,
)
from bot.utils.achievement_checker import check_achievements


def user_shop_kb(items: list[Product]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for item in items:
        kb.add(
            InlineKeyboardButton(
                f"{item.name} — {item.price}💰",
                callback_data=f"user_buy:{item.id}",
            )
        )
    return kb


async def user_shop(message: types.Message, item_type: Optional[str] = None):
    async with async_session() as session:
        stmt = select(Product).where(Product.status == "active")
        if item_type:
            stmt = stmt.where(Product.item_type == item_type)
        items = (await session.execute(stmt.order_by(Product.price))).scalars().all()

    if not items:
        if item_type:
            return await message.answer("📦 В этой категории пока пусто.")
        return await message.answer("🛒 Магазин пуст, товары скоро появятся!")

    header = "🛍 <b>Магазин</b>\nВыберите товар:"
    if item_type == "money":
        header = "💰 <b>Виртуальная валюта</b>"
    elif item_type == "privilege":
        header = "🛡 <b>Привилегии</b>"
    elif item_type == "item":
        header = "🎁 <b>Roblox-предметы</b>"

    await message.answer(
        header,
        reply_markup=user_shop_kb(items),
        parse_mode="HTML",
    )


async def _check_purchase_limits(session, user: User, product: Product) -> Optional[str]:
    if product.per_user_limit is not None:
        count_stmt = select(func.count(Purchase.id)).where(
            Purchase.user_id == user.id,
            Purchase.product_id == product.id,
            Purchase.status != "cancelled",
        )
        purchases_count = (await session.execute(count_stmt)).scalar_one()
        if purchases_count >= product.per_user_limit:
            return "⚠️ Вы достигли лимита покупок этого товара"

    if product.stock_limit is not None:
        quantity_stmt = select(func.coalesce(func.sum(Purchase.quantity), 0)).where(
            Purchase.product_id == product.id,
            Purchase.status != "cancelled",
        )
        sold_quantity = (await session.execute(quantity_stmt)).scalar_one()
        if sold_quantity >= product.stock_limit:
            return "❌ Этот товар распродан"
    return None


async def user_buy_confirm(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("❌ Пользователь не найден", show_alert=True)

    item_id = int(call.data.split(":")[1])

    async with async_session() as session:
        product = await session.get(Product, item_id)
        user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))

        if not product or product.status != "active":
            return await call.answer("❌ Товар не найден", show_alert=True)

        if not user:
            return await call.answer("❌ Профиль не найден. Нажмите /start", show_alert=True)

        limit_error = await _check_purchase_limits(session, user, product)
        if limit_error:
            return await call.answer(limit_error, show_alert=True)

        if user.balance < product.price:
            return await call.answer("💸 Недостаточно валюты!", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Подтвердить покупку", callback_data=f"user_buy_ok:{item_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy"),
    )

    await call.message.answer(
        f"Вы покупаете: <b>{product.name}</b>\n"
        f"Цена: <b>{product.price}💰</b>\n\nПодтвердить?",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await call.answer()


async def cancel_buy(call: types.CallbackQuery):
    await call.message.answer("❌ Покупка отменена")
    await call.answer()


async def user_buy_finish(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("❌ Пользователь не найден", show_alert=True)

    item_id = int(call.data.split(":")[1])
    uid = call.from_user.id

    async with async_session() as session:
        product = await session.scalar(
            select(Product).where(Product.id == item_id, Product.status == "active")
        )
        user = await session.scalar(select(User).where(User.tg_id == uid))

        if not product or not user:
            return await call.answer("❌ Ошибка. Попробуйте снова.", show_alert=True)

        limit_error = await _check_purchase_limits(session, user, product)
        if limit_error:
            return await call.answer(limit_error, show_alert=True)

        if user.balance < product.price:
            return await call.answer("❌ Не хватает валюты!", show_alert=True)

        user.balance -= product.price
        purchase = Purchase(
            user_id=user.id,
            telegram_id=user.tg_id,
            server_id=product.server_id,
            product_id=product.id,
            quantity=1,
            unit_price=product.price,
            total_price=product.price,
            status="pending",
        )
        session.add(purchase)
        await session.flush()

        if product.item_type == "money":
            try:
                reward_amount = int(product.value or 0)
            except (TypeError, ValueError):
                reward_amount = 0
            user.balance += reward_amount
            purchase.status = "completed"
            purchase.notes = "balance_grant"
            reward_text = f"💰 +{reward_amount}"
        elif product.item_type == "privilege":
            reward_text = f"🛡 Привилегия: {product.value}\n⏳ Админ выдаст вручную!"
        else:
            reward_text = f"🎁 Roblox Item ID {product.value}\n⏳ Ожидайте выдачи!"

        session.add(
            LogEntry(
                user_id=user.id,
                telegram_id=user.tg_id,
                server_id=product.server_id,
                request_id=purchase.request_id,
                event_type="purchase_created",
                message=f"Покупка {product.name}",
                data={"product_id": product.id, "status": purchase.status},
            )
        )

        referral_message = ""
        referral = await session.scalar(select(Referral).where(Referral.referred_id == user.id))
        if referral and product.referral_bonus > 0:
            reward = ReferralReward(
                referral_id=referral.id,
                referrer_id=referral.referrer_id,
                purchase_id=purchase.id,
                amount=product.referral_bonus,
                status="granted",
                granted_at=datetime.utcnow(),
                metadata={"product_id": product.id},
            )
            session.add(reward)
            referrer = referral.referrer
            if referrer:
                referrer.balance += product.referral_bonus
                referral_message = (
                    f"\n👥 Ваш реферер получил {product.referral_bonus} монет за покупку."
                )

        await session.commit()

    await check_achievements(user)

    if product.item_type in {"privilege", "item"}:
        notify_text = (
            f"⚠️ @{call.from_user.username or call.from_user.id} купил {product.name}\n"
            f"Тип: {product.item_type}\nЗначение: {product.value}\n"
            f"ID заявки: {purchase.request_id}"
        )
        await bot.send_message(ROOT_ADMIN_ID, notify_text, parse_mode="HTML")

    await call.message.answer(
        f"✅ Покупка успешна!\n{reward_text}{referral_message}",
        parse_mode="HTML",
    )
    await call.answer()


def register_user_shop(dp: Dispatcher):
    dp.register_message_handler(user_shop, commands=["shop"])
    dp.register_callback_query_handler(
        user_buy_confirm,
        lambda c: c.data.startswith("user_buy:"),
    )
    dp.register_callback_query_handler(
        user_buy_finish,
        lambda c: c.data.startswith("user_buy_ok:"),
    )
