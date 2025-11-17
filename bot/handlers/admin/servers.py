from __future__ import annotations

import re
from typing import Sequence

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from bot.db import (
    Admin,
    LogEntry,
    Payment,
    PaymentWebhookEvent,
    Product,
    Purchase,
    ReferralReward,
    Server,
    async_session,
)
from bot.keyboards.admin_keyboards import (
    admin_main_menu_kb,
    admin_server_picker_kb,
    admin_servers_menu_kb,
)
from bot.states.server_states import ServerManageState
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE

router = Router(name="admin_servers")

SERVER_MENU_BUTTON = "🖥️ Сервера"
SERVER_CREATE_BUTTON = "➕ Создать сервер"
SERVER_DELETE_BUTTON = "🗑 Удалить сервер"
SERVER_SET_LINK_BUTTON = "🔗 Назначить ссылку"
SERVER_CLEAR_LINK_BUTTON = "🚫 Удалить ссылку"
SERVER_BACK_BUTTON = "↩️ В админ-панель"


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


def _format_servers_list(servers: Sequence[Server]) -> str:
    lines = ["Доступные серверы:"]
    for server in sorted(servers, key=lambda item: item.position or 0):
        url = server.url or "нет"
        display_name = f"Сервер {server.position}"
        lines.append(
            f"{display_name} — ID <b>{server.id}</b> — {server.name} — ссылка: {url}"
        )
    return "\n".join(lines)


@router.message(F.text == SERVER_MENU_BUTTON)
async def server_menu(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "⚙️ Управление серверами:", reply_markup=admin_servers_menu_kb()
    )


@router.message(F.text == SERVER_BACK_BUTTON)
async def server_back_to_main(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await state.clear()
    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb(),
    )


@router.message(F.text == SERVER_CREATE_BUTTON)
async def server_create(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    async with async_session() as session:
        servers = (
            await session.scalars(select(Server).order_by(Server.position))
        ).all()
        next_position = len(servers) + 1

        new_server = Server(
            name=f"Сервер {next_position}",
            slug=f"server-{next_position}",
            position=next_position,
            telegram_chat_id=None,
            url=None,
            closed_message=SERVER_DEFAULT_CLOSED_MESSAGE,
            status="active",
        )

        session.add(new_server)
        await session.flush()

        session.add(
            LogEntry(
                server_id=new_server.id,
                event_type="server_created",
                message=f"Сервер {new_server.name} создан через админку",
                data={
                    "slug": new_server.slug,
                    "url": new_server.url,
                    "closed_message": new_server.closed_message,
                },
            )
        )

        await session.commit()

        server_id = new_server.id
        server_name = new_server.name
        server_slug = new_server.slug

    await state.clear()
    await message.answer(
        (
            "✅ Сервер <b>{name}</b> создан.\n"
            "ID: <code>{server_id}</code>\n"
            "Slug: <code>{slug}</code>"
        ).format(name=server_name, server_id=server_id, slug=server_slug),
        parse_mode="HTML",
        reply_markup=admin_servers_menu_kb(),
    )


async def _request_server_choice(
    message: types.Message,
    state: FSMContext,
    *,
    operation: str,
    prompt: str,
) -> None:
    async with async_session() as session:
        servers = (
            await session.scalars(select(Server).order_by(Server.position))
        ).all()

    if not servers:
        await message.answer(
            "ℹ️ Нет доступных серверов.", reply_markup=admin_servers_menu_kb()
        )
        await state.clear()
        return

    await state.set_state(ServerManageState.waiting_for_server)
    await state.update_data(
        operation=operation,
        position_map={str(server.position): server.id for server in servers},
    )

    keyboard = admin_server_picker_kb(
        [f"Сервер {server.position}" for server in servers],
        footer_button=SERVER_BACK_BUTTON,
    )

    await message.answer(
        f"{prompt}\n\n{_format_servers_list(servers)}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.message(F.text == SERVER_DELETE_BUTTON)
async def server_delete_start(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await _request_server_choice(
        message,
        state,
        operation="delete",
        prompt="Выберите сервер, который нужно удалить:",
    )


@router.message(F.text == SERVER_SET_LINK_BUTTON)
async def server_set_link_start(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await _request_server_choice(
        message,
        state,
        operation="set_link",
        prompt="Выберите сервер, для которого нужно установить ссылку:",
    )


@router.message(F.text == SERVER_CLEAR_LINK_BUTTON)
async def server_clear_link_start(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    await _request_server_choice(
        message,
        state,
        operation="clear_link",
        prompt="Выберите сервер, для которого нужно удалить ссылку:",
    )


def _parse_server_position(raw: str | None) -> int | None:
    if not raw:
        return None

    try:
        digits = re.sub(r"\D+", "", raw)
        if not digits:
            return None
        return int(digits)
    except ValueError:
        return None


async def _cleanup_server_related_data(session, server_id: int) -> None:
    purchase_ids = (
        await session.scalars(select(Purchase.id).where(Purchase.server_id == server_id))
    ).all()

    if purchase_ids:
        purchase_id_tuple = tuple(purchase_ids)
        payment_ids = (
            await session.scalars(
                select(Payment.id).where(Payment.purchase_id.in_(purchase_id_tuple))
            )
        ).all()

        if payment_ids:
            payment_id_tuple = tuple(payment_ids)
            await session.execute(
                delete(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.payment_id.in_(payment_id_tuple)
                )
            )
            await session.execute(
                delete(ReferralReward).where(
                    ReferralReward.payment_id.in_(payment_id_tuple)
                )
            )
            await session.execute(
                delete(Payment).where(Payment.id.in_(payment_id_tuple))
            )

        await session.execute(
            delete(ReferralReward).where(ReferralReward.purchase_id.in_(purchase_id_tuple))
        )
        await session.execute(delete(Purchase).where(Purchase.id.in_(purchase_id_tuple)))

    await session.execute(delete(Product).where(Product.server_id == server_id))


@router.message(StateFilter(ServerManageState.waiting_for_server))
async def server_select_handler(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    server_position = _parse_server_position(message.text or "")
    data = await state.get_data()
    position_map: dict[str, int] = data.get("position_map") or {}

    if server_position is None:
        await message.answer("Введите номер сервера из списка:")
        return

    server_id = position_map.get(str(server_position))

    if server_id is None:
        await message.answer("Сервер с такой позицией не найден. Выберите корректный сервер:")
        return

    operation = data.get("operation")

    if operation == "delete":
        await _delete_server(
            message,
            state,
            server_id,
            server_position=server_position,
        )
    elif operation == "set_link":
        await state.update_data(server_id=server_id)
        await state.set_state(ServerManageState.waiting_for_link)
        await message.answer("Отправьте новую ссылку для сервера:")
    elif operation == "clear_link":
        await state.update_data(server_id=server_id)
        await state.set_state(ServerManageState.waiting_for_closed_message)
        await message.answer("Введите новое сообщение для закрытого сервера:")
    else:
        await state.clear()
        await message.answer("Неизвестная операция.", reply_markup=admin_servers_menu_kb())


async def _delete_server(
    message: types.Message,
    state: FSMContext,
    server_id: int,
    *,
    server_position: int,
) -> None:
    async with async_session() as session:
        target = await session.get(Server, server_id)

        if not target:
            await message.answer(
                "Сервер не найден.", reply_markup=admin_servers_menu_kb()
            )
            await state.clear()
            return

        try:
            await _cleanup_server_related_data(session, target.id)

            session.add(
                LogEntry(
                    server_id=None,
                    event_type="server_deleted",
                    message=f"Сервер {target.name} удалён через админку",
                    data={
                        "server_id": target.id,
                        "server_name": target.name,
                    },
                )
            )

            deleted_position = target.position or server_position
            await session.delete(target)
            await session.execute(
                update(Server)
                    .where(Server.position > deleted_position)
                    .values(position=Server.position - 1)
            )

            await session.commit()
        except IntegrityError:
            await session.rollback()
            await state.clear()
            await message.answer(
                (
                    "⚠️ Не удалось удалить сервер. Сначала удалите связанные покупки,"
                    " товары и начисления, затем повторите попытку."
                ),
                reply_markup=admin_servers_menu_kb(),
            )
            return

    await state.clear()
    await message.answer(
        "✅ Сервер успешно удалён",
        reply_markup=admin_servers_menu_kb(),
    )


@router.message(StateFilter(ServerManageState.waiting_for_link))
async def server_set_link_finish(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    link = (message.text or "").strip()

    if not link:
        await message.answer("Ссылка не может быть пустой. Повторите ввод:")
        return

    data = await state.get_data()
    server_id = data.get("server_id")

    async with async_session() as session:
        target = await session.get(Server, server_id)

        if not target:
            await state.clear()
            await message.answer(
                "Сервер не найден.", reply_markup=admin_servers_menu_kb()
            )
            return

        target.url = link
        target.closed_message = SERVER_DEFAULT_CLOSED_MESSAGE

        session.add(
            LogEntry(
                server_id=target.id,
                event_type="server_link_updated",
                message=f"Сервер {target.name} получил новую ссылку",
                data={"url": link},
            )
        )

        await session.commit()

    await state.clear()
    await message.answer(
        "🔗 Ссылка обновлена.", reply_markup=admin_servers_menu_kb()
    )


@router.message(StateFilter(ServerManageState.waiting_for_closed_message))
async def server_clear_link_finish(message: types.Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    if not await is_admin(message.from_user.id):
        return

    closed_message = (message.text or "").strip()

    if not closed_message:
        await message.answer(
            "Сообщение не может быть пустым. Введите новое сообщение для закрытого сервера:")
        return

    data = await state.get_data()
    server_id = data.get("server_id")

    async with async_session() as session:
        target = await session.get(Server, server_id)

        if not target:
            await state.clear()
            await message.answer(
                "Сервер не найден.", reply_markup=admin_servers_menu_kb()
            )
            return

        target.url = None
        target.closed_message = closed_message

        session.add(
            LogEntry(
                server_id=target.id,
                event_type="server_link_removed",
                message=f"С сервера {target.name} удалена ссылка",
                data={"closed_message": closed_message},
            )
        )

        await session.commit()

    await state.clear()
    await message.answer(
        "🚫 Ссылка удалена, сообщение обновлено.",
        reply_markup=admin_servers_menu_kb(),
    )