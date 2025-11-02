from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.db import Admin, ShopItem, async_session
from bot.states.shop_states import ShopCreateState


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


# === ADMIN MENU ===

async def admin_shop_menu(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Добавить товар", callback_data="shop_add"),
        InlineKeyboardButton("📦 Список товаров", callback_data="shop_list"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu"),
    )
    await call.message.edit_text(
        "🛒 <b>Магазин</b>\nВыберите:",
        reply_markup=kb,
        parse_mode="HTML",
    )


# === CREATE ITEM ===

async def shop_add(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    await call.message.answer("Введите название товара:")
    await ShopCreateState.waiting_for_name.set()


async def shop_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Валюта", callback_data="shop_type_money"),
        InlineKeyboardButton("🛡 Привилегия", callback_data="shop_type_priv"),
        InlineKeyboardButton("🎁 Roblox Item", callback_data="shop_type_item"),
    )

    await message.answer("Выберите тип товара:", reply_markup=kb)
    await ShopCreateState.waiting_for_type.set()


async def shop_set_type(call: types.CallbackQuery, state: FSMContext):
    if "money" in call.data:
        item_type = "money"
        prompt = "Введите количество валюты:"
    elif "priv" in call.data:
        item_type = "privilege"
        prompt = "Введите название привилегии:"
    else:
        item_type = "item"
        prompt = "Введите Roblox Item ID:"

    await state.update_data(item_type=item_type)
    await call.message.answer(prompt)
    await ShopCreateState.waiting_for_value.set()


async def shop_set_value(message: types.Message, state: FSMContext):
    await state.update_data(value=message.text.strip())
    await message.answer("Введите цену товара (игровая валюта):")
    await ShopCreateState.waiting_for_price.set()


async def shop_finish(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        return await message.answer("Введите число")

    data = await state.get_data()

    async with async_session() as session:
        item = ShopItem(
            name=data["name"],
            item_type=data["item_type"],
            value=data["value"],
            price=price,
        )
        session.add(item)
        await session.commit()

    await message.answer("✅ Товар добавлен!")
    await state.finish()


# === SHOW ITEMS ===

async def shop_list(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    async with async_session() as session:
        items = (await session.scalars(select(ShopItem))).all()

    if not items:
        return await call.message.edit_text(
            "📦 Товары ещё не добавлены.",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("⬅️ Назад", callback_data="admin_shop")
            ),
        )

    text = "📦 <b>Товары магазина:</b>\n\n"
    kb = InlineKeyboardMarkup()

    for item in items:
        text += f"• {item.name} — {item.price}💰 ({item.item_type})\n"
        kb.add(InlineKeyboardButton(f"❌ {item.name}", callback_data=f"shop_del:{item.id}"))

    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_shop"))

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def shop_delete(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("Нет доступа", show_alert=True)

    if not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    item_id = int(call.data.split(":")[1])

    async with async_session() as session:
        item = await session.get(ShopItem, item_id)
        if item:
            await session.delete(item)
            await session.commit()

    await call.answer("Удалено ✅")
    await shop_list(call)


def register_admin_shop(dp: Dispatcher):
    dp.register_callback_query_handler(admin_shop_menu, lambda c: c.data == "admin_shop")
    dp.register_callback_query_handler(shop_add, lambda c: c.data == "shop_add")
    dp.register_message_handler(shop_set_name, state=ShopCreateState.waiting_for_name)
    dp.register_callback_query_handler(shop_set_type, lambda c: c.data.startswith("shop_type"), state=ShopCreateState.waiting_for_type)
    dp.register_message_handler(shop_set_value, state=ShopCreateState.waiting_for_value)
    dp.register_message_handler(shop_finish, state=ShopCreateState.waiting_for_price)
    dp.register_callback_query_handler(shop_list, lambda c: c.data == "shop_list")
    dp.register_callback_query_handler(shop_delete, lambda c: c.data.startswith("shop_del"))
