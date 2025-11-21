"""ASGI entrypoint for the backend service."""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI

from .config import get_settings
from .database import init_models
from .logging import get_logger
from .routers.game import router as game_router
from .routers.payments import router as payments_router
from .services.achievements import run_periodic_recalculation

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Starting backend service", extra={"database": settings.database_url})

    app = FastAPI(title="Roblox BigBob Backend", version="1.0.0")
    app.include_router(game_router)
    app.include_router(payments_router)

    stop_event = asyncio.Event()

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - lifecycle hook
        await init_models()
        app.state.achievements_task = asyncio.create_task(
            run_periodic_recalculation(stop_event)
        )
        logger.info("Backend startup complete")

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # pragma: no cover - lifecycle hook
        stop_event.set()
        task = getattr(app.state, "achievements_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()