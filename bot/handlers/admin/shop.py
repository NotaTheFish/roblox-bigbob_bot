from __future__ import annotations

import re
from typing import Optional

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.db import Admin, LogEntry, Product, Server, async_session
from bot.states.shop_states import ShopCreateState


router = Router(name="admin_shop")


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


async def _get_or_create_default_server(session) -> Server:
    server = await session.scalar(select(Server).where(Server.slug == "default"))
    if not server:
        server = Server(name="Главный сервер", slug="default", status="active")
        session.add(server)
        await session.flush()
    return server


def _slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "product"


async def _ensure_unique_slug(session, server_id: Optional[int], base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while True:
        exists = await session.scalar(
            select(Product).where(Product.server_id == server_id, Product.slug == slug)
        )
        if not exists:
            return slug
        counter += 1
        slug = f"{base_slug}-{counter}"


# === ADMIN MENU ===
@router.callback_query(F.data == "admin_shop")
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


# === CREATE ITEM FLOW ===
@router.callback_query(F.data == "shop_add")
async def shop_add(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user or not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    await call.message.answer("Введите название товара:")
    await state.set_state(ShopCreateState.waiting_for_name)


@router.message(StateFilter(ShopCreateState.waiting_for_name))
async def shop_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Валюта", callback_data="shop_type_money"),
        InlineKeyboardButton("🛡 Привилегия", callback_data="shop_type_priv"),
        InlineKeyboardButton("🎁 Roblox Item", callback_data="shop_type_item"),
    )

    await message.answer("Выберите тип товара:", reply_markup=kb)
    await state.set_state(ShopCreateState.waiting_for_type)


@router.callback_query(
    StateFilter(ShopCreateState.waiting_for_type),
    F.data.startswith("shop_type"),
)
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
    await state.set_state(ShopCreateState.waiting_for_value)


@router.message(StateFilter(ShopCreateState.waiting_for_value))
async def shop_set_value(message: types.Message, state: FSMContext):
    await state.update_data(value=message.text.strip())
    await message.answer("Введите цену товара (игровая валюта):")
    await state.set_state(ShopCreateState.waiting_for_price)


@router.message(StateFilter(ShopCreateState.waiting_for_price))
async def shop_set_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите положительное число")

    await state.update_data(price=price)
    await message.answer("Сколько раз можно купить? (0 — без ограничений)")
    await state.set_state(ShopCreateState.waiting_for_limit)


@router.message(StateFilter(ShopCreateState.waiting_for_limit))
async def shop_set_limit(message: types.Message, state: FSMContext):
    try:
        raw = int(message.text)
        per_user_limit = None if raw <= 0 else raw
    except ValueError:
        return await message.answer("Введите число")

    await state.update_data(per_user_limit=per_user_limit)
    await message.answer("Введите бонус рефереру (0 — нет бонуса):")
    await state.set_state(ShopCreateState.waiting_for_referral_bonus)


@router.message(StateFilter(ShopCreateState.waiting_for_referral_bonus))
async def shop_finish(message: types.Message, state: FSMContext):
    try:
        referral_bonus = int(message.text)
        if referral_bonus < 0:
            raise ValueError
    except ValueError:
        return await message.answer("Введите неотрицательное число")

    data = await state.get_data()

    async with async_session() as session:
        server = await _get_or_create_default_server(session)
        base_slug = _slugify(data["name"])
        slug = await _ensure_unique_slug(session, server.id, base_slug)

        product = Product(
            server_id=server.id,
            slug=slug,
            name=data["name"],
            item_type=data["item_type"],
            value=data["value"],
            price=data["price"],
            per_user_limit=data.get("per_user_limit"),
            referral_bonus=referral_bonus,
            status="active",
        )
        session.add(product)
        await session.flush()

        session.add(
            LogEntry(
                server_id=server.id,
                event_type="product_created",
                message=f"Создан товар {product.name}",
                data={
                    "product_id": product.id,
                    "slug": slug,
                    "limit": data.get("per_user_limit"),
                    "referral_bonus": referral_bonus,
                },
            )
        )

        await session.commit()

    await message.answer("✅ Товар добавлен!")
    await state.clear()


# === LIST & DELETE ===
@router.callback_query(F.data == "shop_list")
async def shop_list(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    async with async_session() as session:
        products = (await session.execute(select(Product).order_by(Product.created_at))).scalars().all()
        if not products:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_shop"))
            return await call.message.edit_text("📦 Товары ещё не добавлены.", reply_markup=kb)

        lines = ["📦 <b>Товары магазина:</b>"]
        kb = InlineKeyboardMarkup()

        for product in products:
            server = await session.get(Server, product.server_id) if product.server_id else None
            limit_text = "∞" if product.per_user_limit is None else str(product.per_user_limit)
            lines.append(
                f"• {product.name} — {product.price}💰 ({product.item_type})\n"
                f"  Лимит: {limit_text} | Реф. бонус: {product.referral_bonus}"
                + (f" | Сервер: {server.name}" if server else "")
            )
            kb.add(
                InlineKeyboardButton(
                    f"❌ {product.name}", callback_data=f"shop_del:{product.id}"
                )
            )
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_shop"))

    await call.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("shop_del"))
async def shop_delete(call: types.CallbackQuery):
    if not call.from_user or not await is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)

    item_id = int(call.data.split(":")[1])

    async with async_session() as session:
        product = await session.get(Product, item_id)
        if product:
            session.add(
                LogEntry(
                    server_id=product.server_id,
                    event_type="product_deleted",
                    message=f"Удалён товар {product.name}",
                    data={"product_id": product.id},
                )
            )
            await session.delete(product)
            await session.commit()

    await call.answer("Удалено ✅")
    await shop_list(call)
