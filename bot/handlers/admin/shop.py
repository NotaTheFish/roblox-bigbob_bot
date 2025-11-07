from __future__ import annotations

import re
from typing import Optional

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.db import Admin, LogEntry, Product, Server, async_session
from bot.keyboards.admin_keyboards import admin_shop_menu_kb, shop_type_kb
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
@router.message(F.text == "Управление магазином")
async def admin_shop_menu(message: types.Message):
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "🛒 <b>Магазин</b>\nВыберите:",
        parse_mode="HTML",
        reply_markup=admin_shop_menu_kb(),
    )


# === CREATE ITEM FLOW ===
@router.message(F.text == "➕ Добавить товар")
async def shop_add(message: types.Message, state: FSMContext):
    if not message.from_user or not await is_admin(message.from_user.id):
        return

    await message.answer("Введите название товара:")
    await state.set_state(ShopCreateState.waiting_for_name)


@router.message(StateFilter(ShopCreateState.waiting_for_name))
async def shop_set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())

    await message.answer("Выберите тип товара:", reply_markup=shop_type_kb())
    await state.set_state(ShopCreateState.waiting_for_type)


@router.message(
    StateFilter(ShopCreateState.waiting_for_type),
    F.text.in_({"💰 Валюта", "🛡 Привилегия", "🎁 Roblox предмет"}),
)
async def shop_set_type(message: types.Message, state: FSMContext):
    if message.text == "💰 Валюта":
        item_type = "money"
        prompt = "Введите количество валюты:"
    elif message.text == "🛡 Привилегия":
        item_type = "privilege"
        prompt = "Введите название привилегии:"
    else:
        item_type = "item"
        prompt = "Введите Roblox Item ID:"

    await state.update_data(item_type=item_type)
    await message.answer(prompt)
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

    await message.answer("✅ Товар добавлен!", reply_markup=admin_shop_menu_kb())
    await state.clear()


# === LIST & DELETE ===
async def _build_shop_list() -> tuple[str | None, types.InlineKeyboardMarkup | None]:
    async with async_session() as session:
        products = (
            await session.execute(select(Product).order_by(Product.created_at))
        ).scalars().all()

        if not products:
            return None, None

        lines = ["📦 <b>Товары магазина:</b>"]
        builder = InlineKeyboardBuilder()

        for product in products:
            server = await session.get(Server, product.server_id) if product.server_id else None
            limit_text = "∞" if product.per_user_limit is None else str(product.per_user_limit)
            lines.append(
                f"• {product.name} — {product.price}💰 ({product.item_type})\n"
                f"  Лимит: {limit_text} | Реф. бонус: {product.referral_bonus}"
                + (f" | Сервер: {server.name}" if server else "")
            )
            builder.button(
                text=f"❌ {product.name}", callback_data=f"shop_del:{product.id}"
            )

    reply_markup = builder.as_markup() if builder.export() else None
    return "\n".join(lines), reply_markup


@router.message(F.text == "📦 Список товаров")
async def shop_list(message: types.Message):
    if not message.from_user or not await is_admin(message.from_user.id):
        return

    text, reply_markup = await _build_shop_list()

    if not text:
        await message.answer(
            "📦 Товары ещё не добавлены.",
            reply_markup=admin_shop_menu_kb(),
        )
        return

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    await message.answer(
        "Выберите следующее действие:",
        reply_markup=admin_shop_menu_kb(),
    )


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

    # <-- этот блок должен быть СЛЕВА, на том же уровне что и `async with`
    text, reply_markup = await _build_shop_list()

    if text:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    else:
        await call.message.edit_text("📦 Товары ещё не добавлены.")
        await call.message.answer(
            "Выберите следующее действие:",
            reply_markup=admin_shop_menu_kb(),
        )

    await call.answer("Удалено ✅")
