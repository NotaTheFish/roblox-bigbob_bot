from typing import Optional

from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.bot_instance import bot
from bot.config import ROOT_ADMIN_ID
from bot.db import SessionLocal, User, ShopItem
from bot.utils.achievement_checker import check_achievements


def user_shop_kb(items: list[ShopItem]) -> InlineKeyboardMarkup:
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
    with SessionLocal() as s:
        query = s.query(ShopItem)
        if item_type:
            query = query.filter_by(item_type=item_type)
        items = query.all()

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


async def user_buy_confirm(call: types.CallbackQuery):
    item_id = int(call.data.split(":")[1])

    with SessionLocal() as s:
        item = s.query(ShopItem).filter_by(id=item_id).first()
        user = s.query(User).filter_by(tg_id=call.from_user.id).first()

    if not item:
        return await call.answer("❌ Товар не найден", show_alert=True)

    if not user:
        return await call.answer("❌ Профиль не найден. Нажмите /start", show_alert=True)

    if user.balance < item.price:
        return await call.answer("💸 Недостаточно валюты!", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Подтвердить покупку", callback_data=f"user_buy_ok:{item_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy"),
    )

    await call.message.answer(
        f"Вы покупаете: <b>{item.name}</b>\n"
        f"Цена: <b>{item.price}💰</b>\n\nПодтвердить?",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await call.answer()


async def cancel_buy(call: types.CallbackQuery):
    await call.message.answer("❌ Покупка отменена")
    await call.answer()


async def user_buy_finish(call: types.CallbackQuery):
    item_id = int(call.data.split(":")[1])
    uid = call.from_user.id

    with SessionLocal() as s:
        item = s.query(ShopItem).filter_by(id=item_id).first()
        user = s.query(User).filter_by(tg_id=uid).first()

        if not item or not user:
            return await call.answer("❌ Ошибка. Попробуйте снова.", show_alert=True)

        if user.balance < item.price:
            return await call.answer("❌ Не хватает валюты!", show_alert=True)

        user.balance -= item.price
        
        if item.item_type == "money":
            try:
                reward_amount = int(item.value)
            except (TypeError, ValueError):
                reward_amount = 0
            user.balance += reward_amount
            reward_text = f"💰 +{reward_amount}"

        elif item.item_type == "privilege":
            reward_text = f"🛡 Привилегия: {item.value}\n⏳ Админ выдаст вручную!"

        else:
            reward_text = f"🎁 Roblox Item ID {item.value}\n⏳ Ожидайте выдачи!"

        s.commit()

    check_achievements(user)

    if item.item_type in {"privilege", "item"}:
        notify_text = (
            f"⚠️ @{call.from_user.username or call.from_user.id} купил {item.name}\n"
            f"Тип: {item.item_type}\nЗначение: {item.value}"
        )
        await bot.send_message(
            ROOT_ADMIN_ID,
            notify_text,
            parse_mode="HTML",
        )

    await call.message.answer(f"✅ Покупка успешна!\n{reward_text}", parse_mode="HTML")
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
    dp.register_callback_query_handler(
        cancel_buy,
        lambda c: c.data == "cancel_buy",
    )