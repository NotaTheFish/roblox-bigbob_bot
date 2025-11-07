"""Admin handlers routers aggregation."""

from .achievements import router as achievements_router
from .login import router as login_router
from .menu import router as menu_router
from .payments import router as payments_router
from .promo import router as promo_router
from .servers import router as servers_router
from .shop import router as shop_router
from .support import router as support_router
from .users import router as users_router


routers = [
    menu_router,
    login_router,
    users_router,
    promo_router,
    shop_router,
    payments_router,
    achievements_router,
    servers_router,
    support_router,
]

__all__ = ["routers"]