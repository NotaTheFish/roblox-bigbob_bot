from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.states.shop_states import ShopCreateState
from bot.db import SessionLocal, ShopItem, Admin
from bot.keyboards.admin_keyboards import admin_main_menu_kb
from bot.main_core import bot


def is_admin(uid):
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())


# === ADMIN MENU ===

async def admin_shop_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("➕ Добавить товар", callback_data="shop_add"),
        InlineKeyboardButton("📦 Список товаров", callback_data="shop_list"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")
    )
    await call.message.edit_text("🛒 <b>Магазин</b>\nВыберите:", reply_markup=kb, parse_mode="HTML")


# === CREATE ITEM ===

async def shop_add(call: types.CallbackQuery):
    await call.message.answer("Введите название товара:")
    await ShopCreateState.waiting_for_name.set()


async def shop_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)

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
        t = "money"
        text = "Введите количество валюты, которое получит пользователь:"
    elif "priv" in call.data:
        t = "privilege"
        text = "Введите название привилегии (админ должен выдать вручную):"
    else:
        t = "item"
        text = "Введите Roblox Item ID:"

    await state.update_data(item_type=t)
    await call.message.answer(text)
    await ShopCreateState.waiting_for_value.set()


async def shop_set_value(message: types.Message, state: FSMContext):
    await state.update_data(value=message.text)
    await message.answer("Введите цену товара (игровая валюта):")
    await ShopCreateState.waiting_for_price.set()


async def shop_finish(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
    except:
        return await message.answer("Введите число")

    data = await state.get_data()

    with SessionLocal() as s:
        item = ShopItem(
            name=data["name"],
            item_type=data["item_type"],
            value=data["value"],
            price=price
        )
        s.add(item)
        s.commit()

    await message.answer("✅ Товар добавлен!")
    await state.finish()


# === SHOW ITEMS ===

async def shop_list(call: types.CallbackQuery):
    with SessionLocal() as s:
        items = s.query(ShopItem).all()

    text = "📦 <b>Товары магазина:</b>\n\n"
    kb = InlineKeyboardMarkup()

    for i in items:
        text += f"• {i.name} — {i.price}💰 ({i.item_type})\n"
        kb.add(InlineKeyboardButton(f"❌ {i.name}", callback_data=f"shop_del:{i.id}"))

    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_shop"))

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def shop_delete(call: types.CallbackQuery):
    item_id = int(call.data.split(":")[1])
    with SessionLocal() as s:
        obj = s.query(ShopItem).filter_by(id=item_id).first()
        s.delete(obj)
        s.commit()

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
