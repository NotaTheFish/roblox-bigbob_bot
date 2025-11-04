"""ASGI entrypoint for the backend service."""
from __future__ import annotations

from fastapi import FastAPI

from .config import get_settings
from .database import init_models
from .logging import get_logger
from .routers.game import router as game_router
from .routers.payments import router as payments_router

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Starting backend service", extra={"database": settings.database_url})

    app = FastAPI(title="Roblox BigBob Backend", version="1.0.0")
    app.include_router(game_router)
    app.include_router(payments_router)

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - lifecycle hook
        await init_models()
        logger.info("Backend startup complete")

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()