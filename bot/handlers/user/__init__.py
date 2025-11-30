"""User handlers routers aggregation."""

from __future__ import annotations

import logging
from typing import Iterable

from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.constants.admin_menu import ADMIN_MENU_BUTTONS

from .achievements import router as achievements_router
from .balance import router as balance_router
from .banned import router as banned_router
from .menu import router as menu_router
from .messages import router as messages_router
from .promo import router as promo_router
from .promocode_use import router as promocode_use_router
from .shop import router as shop_router
from .support import router as support_router
from .start import router as start_router
from .verify import router as verify_router


logger = logging.getLogger(__name__)


async def _skip_admin_routing(
    event: types.TelegramObject, state: FSMContext | None = None, **_: object
) -> bool:
    """Prevent user routers from handling admin messages or admin FSM events."""

    text = getattr(event, "text", None) or getattr(event, "data", None)

    current_state = None
    if state:
        current_state = await state.get_state()
        logger.info("FSM STATE = %s", current_state)

    if current_state and current_state.startswith("Admin"):
        logger.info("PASSED TO ADMIN: %s", text)
        return False

    if text in ADMIN_MENU_BUTTONS:
        logger.info("PASSED TO ADMIN: %s", text)
        return False

    return True


def _apply_user_router_filters(target_routers: Iterable) -> list:
    routers_list = list(target_routers)
    for router in routers_list:
        router.message.filter(_skip_admin_routing)
        router.callback_query.filter(_skip_admin_routing)
    return routers_list


routers = _apply_user_router_filters(
    [
        start_router,
        menu_router,
        verify_router,
        support_router,
        banned_router,
        promo_router,
        promocode_use_router,
        shop_router,
        balance_router,
        achievements_router,
        messages_router,
    ]
)

__all__ = ["routers"]