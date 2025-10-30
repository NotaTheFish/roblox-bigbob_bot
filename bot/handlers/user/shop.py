from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.db import SessionLocal, User, ShopItem
from bot.main_core import bot
from bot.config import ROOT_ADMIN_ID
from bot.utils.achievement_checker import check_achievements


def user_shop_kb(items):
    kb = InlineKeyboardMarkup()
    for item in items:
        kb.add(
            InlineKeyboardButton(
                f"{item.name} — {item.price}💰",
                callback_data=f"user_buy:{item.id}"
            )
        )
    return kb


async def user_shop(message: types.Message):
    with SessionLocal() as s:
        items = s.query(ShopItem).all()

    if not items:
        return await message.answer("🛒 Магазин пуст, товары скоро появятся!")

    await message.answer(
        "🛍 <b>Магазин</b>\nВыберите товар:",
        reply_markup=user_shop_kb(items),
        parse_mode="HTML"
    )


async def user_buy_confirm(call: types.CallbackQuery):
    item_id = int(call.data.split(":")[1])

    with SessionLocal() as s:
        item = s.query(ShopItem).filter_by(id=item_id).first()
        user = s.query(User).filter_by(tg_id=call.from_user.id).first()

    if not item:
        return await call.answer("❌ Товар не найден")

    if user.balance < item.price:
        return await call.answer("💸 Недостаточно валюты!", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Подтвердить покупку", callback_data=f"user_buy_ok:{item_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_buy")
    )

    await call.message.answer(
        f"Вы покупаете: <b>{item.name}</b>\n"
        f"Цена: <b>{item.price}💰</b>\n\nПодтвердить?",
        parse_mode="HTML",
        reply_markup=kb
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

        if user.balance < item.price:
            return await call.answer("❌ Не хватает валюты!", show_alert=True)

        user.balance -= item.price
        s.commit()

        check_achievements(user)

        if item.item_type == "money":
            user.balance += int(item.value)
            s.commit()
            text = f"💰 +{item.value}"

        elif item.item_type == "privilege":
            text = f"🛡 Привилегия: {item.value}\n⏳ Админ выдаст вручную!"
            await bot.send_message(
                ROOT_ADMIN_ID,
                f"⚠️ @{call.from_user.username} купил привилегию <b>{item.value}</b>",
                parse_mode="HTML"
            )

        else:
            text = f"🎁 Roblox Item ID {item.value}\n⏳ Ожидайте выдачи!"
            await bot.send_message(
                ROOT_ADMIN_ID,
                f"🎁 @{call.from_user.username} купил Roblox Item <code>{item.value}</code>",
                parse_mode="HTML"
            )

    await call.message.answer(f"✅ Покупка успешна!\n{text}", parse_mode="HTML")
    await call.answer()


def register_admin_shop(dp: Dispatcher):
    dp.register_message_handler(user_shop, commands=["shop"])
    dp.register_callback_query_handler(user_buy_confirm, lambda c: c.data.startswith("user_buy:"))
    dp.register_callback_query_handler(user_buy_finish, lambda c: c.data.startswith("user_buy_ok:"))
    dp.register_callback_query_handler(cancel_buy, lambda c: c.data == "cancel_buy")
