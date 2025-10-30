from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.db import SessionLocal, User, ShopItem
from bot.main_core import bot
from bot.config import ROOT_ADMIN_ID


# === Клавиатура магазина ===

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


# === Команда: открыть магазин ===

async def user_shop(message: types.Message):
    uid = message.from_user.id
    with SessionLocal() as s:
        items = s.query(ShopItem).all()

    if not items:
        return await message.answer("🛒 Магазин пуст, товары скоро появятся!")

    text = "🛍 <b>Магазин</b>\nВыберите товар:"
    await message.answer(text, reply_markup=user_shop_kb(items), parse_mode="HTML")


# === Callback: нажал купить ===

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
        f"Цена: <b>{item.price}💰</b>\n\nПодтвердить покупку?",
        parse_mode="HTML",
        reply_markup=kb
    )
    await call.answer()


# === Callback: отмена ===

async def cancel_buy(call: types.CallbackQuery):
    await call.message.answer("❌ Покупка отменена")
    await call.answer()


# === Завершение покупки ===

async def user_buy_finish(call: types.CallbackQuery):
    item_id = int(call.data.split(":")[1])
    uid = call.from_user.id

    with SessionLocal() as s:
        item = s.query(ShopItem).filter_by(id=item_id).first()
        user = s.query(User).filter_by(tg_id=uid).first()

        if user.balance < item.price:
            return await call.answer("❌ Не хватает денег!", show_alert=True)

        # списываем деньги
        user.balance -= item.price
        s.commit()

from bot.utils.achievement_checker import check_achievements
check_achievements(user)


    # выдача товара
    if item.item_type == "money":
        # покупка валюты — странно, но пусть будет
        user.balance += int(item.value)
        text = f"💰 Вы получили +{item.value} монет"
    elif item.item_type == "privilege":
        text = f"🛡 Вы купили привилегию: {item.value}\n⏳ Админ выдаст её вручную!"
        try:
            await bot.send_message(
                ROOT_ADMIN_ID,
                f"⚠️ Пользователь @{call.from_user.username} купил привилегию <b>{item.value}</b>",
                parse_mode="HTML"
            )
        except:
            pass
    else:  # roblox item
        text = f"🎁 Вы купили Roblox предмет: ID {item.value}\n⏳ Ожидайте выдачи!"
        try:
            await bot.send_message(
                ROOT_ADMIN_ID,
                f"🎁 @{call.from_user.username} купил Roblox Item ID <code>{item.value}</code>\n"
                f"Выдайте вручную (Roblox API подключим позже)",
                parse_mode="HTML"
            )
        except:
            pass

    await call.message.answer(f"✅ Покупка успешна!\n{text}", parse_mode="HTML")
    await call.answer()
