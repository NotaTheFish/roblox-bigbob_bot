from __future__ import annotations

import re
from typing import Final

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.db import Admin, LogEntry, Server, async_session
from bot.keyboards.admin_keyboards import admin_main_menu_kb
from bot.states.server_states import ServerCreateState


router = Router(name="admin_servers")

SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9-]{3,64}$")
SKIP_CHAT_ID_VALUES: Final[set[str]] = {"-", "нет", "пропустить"}


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


@router.message(F.text == "Добавить сервер")
async def server_create_start(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.set_state(ServerCreateState.waiting_for_name)
    await message.answer("Введите название сервера:")


@router.message(StateFilter(ServerCreateState.waiting_for_name))
async def server_set_name(message: types.Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("Название не может быть пустым. Повторите ввод:")
        return

    await state.update_data(name=name)
    await state.set_state(ServerCreateState.waiting_for_slug)
    await message.answer(
        "Введите slug сервера (латиница, цифры и дефис, от 3 до 64 символов):"
    )


@router.message(StateFilter(ServerCreateState.waiting_for_slug))
async def server_set_slug(message: types.Message, state: FSMContext) -> None:
    slug_raw = message.text.strip().lower() if message.text else ""
    if not SLUG_PATTERN.fullmatch(slug_raw):
        await message.answer(
            "Slug должен содержать только латиницу, цифры и дефисы (3-64 символа)."
        )
        return

    async with async_session() as session:
        exists = await session.scalar(select(Server.id).where(Server.slug == slug_raw))

    if exists:
        await message.answer("Такой slug уже используется. Укажите другой:")
        return

    await state.update_data(slug=slug_raw)
    await state.set_state(ServerCreateState.waiting_for_link)
    await message.answer("Отправьте ссылку на сервер (например, приглашение):")


@router.message(StateFilter(ServerCreateState.waiting_for_link))
async def server_set_link(message: types.Message, state: FSMContext) -> None:
    link = message.text.strip() if message.text else ""
    if not link:
        await message.answer("Ссылка не может быть пустой. Укажите ссылку:")
        return

    await state.update_data(link=link)
    await state.set_state(ServerCreateState.waiting_for_chat_id)
    await message.answer(
        "Укажите chat_id для уведомлений (опционально). Отправьте '-' чтобы пропустить."
    )


@router.message(StateFilter(ServerCreateState.waiting_for_chat_id))
async def server_set_chat_id(message: types.Message, state: FSMContext) -> None:
    raw_value = message.text.strip() if message.text else ""
    chat_id = None

    if raw_value:
        if raw_value.lower() in SKIP_CHAT_ID_VALUES:
            chat_id = None
        else:
            try:
                chat_id = int(raw_value)
            except ValueError:
                await message.answer("Введите числовой chat_id или '-' для пропуска:")
                return

            async with async_session() as session:
                chat_exists = await session.scalar(
                    select(Server.id).where(Server.telegram_chat_id == chat_id)
                )

            if chat_exists:
                await message.answer(
                    "Этот chat_id уже привязан к другому серверу. Укажите другой или '-'"
                )
                return

    await state.update_data(chat_id=chat_id)
    data = await state.get_data()

    async with async_session() as session:
        server = Server(
            name=data["name"],
            slug=data["slug"],
            telegram_chat_id=data.get("chat_id"),
            url=data["link"],
            status="active",
        )
        session.add(server)
        await session.flush()

        session.add(
            LogEntry(
                server_id=server.id,
                event_type="server_created",
                message=f"Сервер {server.name} создан через админку",
                data={
                    "slug": server.slug,
                    "chat_id": server.telegram_chat_id,
                    "url": data["link"],
                },
            )
        )

        await session.commit()
        server_id = server.id

    await state.clear()
    await message.answer(
        (
            "✅ Сервер <b>{name}</b> создан.\n"
            "ID: <code>{server_id}</code>\n"
            "Slug: <code>{slug}</code>"
        ).format(name=data["name"], server_id=server_id, slug=data["slug"]),
        parse_mode="HTML",
        reply_markup=admin_main_menu_kb(),
    )