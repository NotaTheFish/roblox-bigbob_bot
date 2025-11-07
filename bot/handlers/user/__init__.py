"""User handlers routers aggregation."""

from .achievements import router as achievements_router
from .balance import router as balance_router
from .menu import router as menu_router
from .promo import router as promo_router
from .shop import router as shop_router
from .support import router as support_router
from .start import router as start_router
from .verify import router as verify_router


routers = [
    start_router,
    menu_router,
    verify_router,
    support_router,
    promo_router,
    shop_router,
    balance_router,
    achievements_router,
]

__all__ = ["routers"]