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
    admin_server_navigation_kb,
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
SERVER_STEP_BACK_BUTTON = "↩️ Назад"

SERVERS_CREATE_CALLBACK = "servers_create"
SERVERS_DELETE_CALLBACK = "servers_delete"
SERVERS_SET_LINK_CALLBACK = "servers_set_link"
SERVERS_CLEAR_LINK_CALLBACK = "servers_clear_link"


async def is_admin(uid: int) -> bool:
    async with async_session() as session:
        return bool(await session.scalar(select(Admin).where(Admin.telegram_id == uid)))


async def _is_valid_admin_message(message: types.Message) -> bool:
    return bool(message.from_user) and await is_admin(message.from_user.id)


async def _ensure_admin_callback(call: types.CallbackQuery) -> bool:
    if not call.from_user:
        return False

    if not await is_admin(call.from_user.id):
        await call.answer("⛔ У вас нет доступа", show_alert=True)
        return False

    return True


def _format_servers_list(servers: Sequence[Server]) -> str:
    lines = ["Доступные серверы:"]
    for server in sorted(servers, key=lambda item: item.position or 0):
        url = server.url or "нет"
        lines.append(f"Сервер {server.position} — ссылка:\n{url}")
    return "\n".join(lines)


async def show_servers_menu(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "⚙️ Управление серверами:", reply_markup=admin_servers_menu_kb()
    )


@router.message(F.text == SERVER_MENU_BUTTON)
async def server_menu(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    await show_servers_menu(message, state)


async def _handle_servers_back(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state == ServerManageState.waiting_for_server.state:
        await show_servers_menu(message, state)
        return

    if current_state in {
        ServerManageState.waiting_for_link.state,
        ServerManageState.waiting_for_closed_message.state,
    }:
        if await _back_to_server_picker(message, state):
            return

    await state.clear()
    await message.answer(
        "👑 <b>Админ-панель</b>\nВыберите раздел:",
        reply_markup=admin_main_menu_kb(),
    )


@router.message(F.text == SERVER_STEP_BACK_BUTTON)
async def server_step_back(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    await _handle_servers_back(message, state)


@router.callback_query(F.data == "servers_back")
async def servers_back_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await _handle_servers_back(call.message, state)

    await call.answer()


@router.callback_query(F.data == "servers_link_back")
async def servers_link_back_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    if not await _ensure_admin_callback(call):
        return

    if not call.message:
        return await call.answer()

    handled = await _back_to_server_picker(call.message, state)
    if not handled:
        await show_servers_menu(call.message, state)

    await call.answer()


@router.callback_query(F.data == "servers_add_back")
async def servers_add_back_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await show_servers_menu(call.message, state)

    await call.answer()


@router.callback_query(F.data == "servers_delete_back")
async def servers_delete_back_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await show_servers_menu(call.message, state)

    await call.answer()


async def _perform_server_create(message: types.Message, state: FSMContext) -> None:
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
        reply_markup=admin_server_navigation_kb("servers_add_back"),
    )


@router.message(F.text == SERVER_CREATE_BUTTON)
async def server_create(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    await _perform_server_create(message, state)


@router.callback_query(F.data == SERVERS_CREATE_CALLBACK)
async def server_create_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await _perform_server_create(call.message, state)

    await call.answer()


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
    position_map: dict[str, int] = {}
    button_items: list[tuple[int, str]] = []
    for idx, server in enumerate(servers, start=1):
        position = server.position or idx
        position_map[str(position)] = server.id
        button_items.append((position, f"Сервер {position}"))

    await state.update_data(
        operation=operation,
        prompt=prompt,
        position_map=position_map,
    )

    keyboard = admin_server_picker_kb(button_items)

    await message.answer(
        f"{prompt}\n\n{_format_servers_list(servers)}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def _back_to_server_picker(message: types.Message, state: FSMContext) -> bool:
    data = await state.get_data()
    operation = data.get("operation")
    prompt = data.get("prompt")

    if not operation or not prompt:
        return False

    await _request_server_choice(
        message,
        state,
        operation=operation,
        prompt=prompt,
    )
    return True

    
async def _handle_server_selection(
    server_position: int, message: types.Message, state: FSMContext
) -> None:
    data = await state.get_data()
    position_map: dict[str, int] = data.get("position_map") or {}
    server_id = position_map.get(str(server_position))

    if server_id is None:
        await message.answer(
            "Сервер с такой позицией не найден. Выберите корректный сервер:",
            reply_markup=admin_server_navigation_kb("servers_back"),
        )
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
        await message.answer(
            "Отправьте новую ссылку для сервера:",
            reply_markup=admin_server_navigation_kb("servers_link_back"),
        )
    elif operation == "clear_link":
        await state.update_data(server_id=server_id)
        await state.set_state(ServerManageState.waiting_for_closed_message)
        await message.answer(
            "Введите новое сообщение для закрытого сервера:",
            reply_markup=admin_server_navigation_kb("servers_link_back"),
        )
    else:
        await state.clear()
        await message.answer(
            "Неизвестная операция.", reply_markup=admin_servers_menu_kb()
        )


async def _start_delete_flow(message: types.Message, state: FSMContext) -> None:
    await _request_server_choice(
        message,
        state,
        operation="delete",
        prompt="Выберите сервер, который нужно удалить:",
    )


@router.message(F.text == SERVER_DELETE_BUTTON)
async def server_delete_start(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    await _start_delete_flow(message, state)


@router.callback_query(F.data == SERVERS_DELETE_CALLBACK)
async def server_delete_start_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await _start_delete_flow(call.message, state)

    await call.answer()


async def _start_set_link_flow(message: types.Message, state: FSMContext) -> None:
    await _request_server_choice(
        message,
        state,
        operation="set_link",
        prompt="Выберите сервер, для которого нужно установить ссылку:",
    )


@router.message(F.text == SERVER_SET_LINK_BUTTON)
async def server_set_link_start(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    await _start_set_link_flow(message, state)


@router.callback_query(F.data == SERVERS_SET_LINK_CALLBACK)
async def server_set_link_start_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await _start_set_link_flow(call.message, state)

    await call.answer()


async def _start_clear_link_flow(message: types.Message, state: FSMContext) -> None:
    await _request_server_choice(
        message,
        state,
        operation="clear_link",
        prompt="Выберите сервер, для которого нужно удалить ссылку:",
    )


@router.message(F.text == SERVER_CLEAR_LINK_BUTTON)
async def server_clear_link_start(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    await _start_clear_link_flow(message, state)


@router.callback_query(F.data == SERVERS_CLEAR_LINK_CALLBACK)
async def server_clear_link_start_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    if not await _ensure_admin_callback(call):
        return

    if call.message:
        await _start_clear_link_flow(call.message, state)

    await call.answer()


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
    if not await _is_valid_admin_message(message):
        return

    server_position = _parse_server_position(message.text or "")

    if server_position is None:
        await message.answer(
            "Введите номер сервера из списка:",
            reply_markup=admin_server_navigation_kb("servers_back"),
        )
        return

    await _handle_server_selection(server_position, message, state)

    
@router.callback_query(F.data.startswith("servers_pick:"))
async def server_pick_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_admin_callback(call):
        return

    if not call.message:
        return await call.answer()

    raw_data = call.data or ""
    try:
        _, position_raw = raw_data.split(":", 1)
        server_position = int(position_raw)
    except (ValueError, AttributeError):
        return await call.answer("Некорректный сервер", show_alert=True)

    await _handle_server_selection(server_position, call.message, state)
    await call.answer()


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
                reply_markup=admin_server_navigation_kb("servers_delete_back"),
            )
            return

    await state.clear()
    await message.answer(
        "✅ Сервер успешно удалён",
        reply_markup=admin_server_navigation_kb("servers_delete_back"),
    )


@router.message(StateFilter(ServerManageState.waiting_for_link))
async def server_set_link_finish(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    link = (message.text or "").strip()

    if not link:
        await message.answer(
            "Ссылка не может быть пустой. Повторите ввод:",
            reply_markup=admin_server_navigation_kb("servers_link_back"),
        )
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
        "🔗 Ссылка обновлена.",
        reply_markup=admin_server_navigation_kb("servers_link_back"),
    )


@router.message(StateFilter(ServerManageState.waiting_for_closed_message))
async def server_clear_link_finish(message: types.Message, state: FSMContext) -> None:
    if not await _is_valid_admin_message(message):
        return

    closed_message = (message.text or "").strip()

    if not closed_message:
        await message.answer(
            "Сообщение не может быть пустым. Введите новое сообщение для закрытого сервера:",
            reply_markup=admin_server_navigation_kb("servers_link_back"),
        )
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
        reply_markup=admin_server_navigation_kb("servers_link_back"),
    )