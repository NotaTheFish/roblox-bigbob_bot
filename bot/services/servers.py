"""Services for retrieving Roblox server metadata for user interactions."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from bot.db import Server, async_session


@dataclass(frozen=True)
class ServerInfo:
    """A lightweight representation of a Roblox server."""

    id: int
    name: str
    url: str | None
    closed_message: str | None


async def get_ordered_servers() -> list[ServerInfo]:
    """Return all servers ordered by their identifier."""

    async with async_session() as session:
        servers = (
            await session.scalars(select(Server).order_by(Server.id))
        ).all()

    return [
        ServerInfo(
            id=server.id,
            name=server.name,
            url=server.url or None,
            closed_message=server.closed_message or None,
        )
        for server in sorted(servers, key=lambda item: item.id or 0)
    ]


async def get_server_by_id(server_id: int) -> ServerInfo | None:
    """Return server information for the provided identifier, if present."""

    async with async_session() as session:
        server = await session.get(Server, server_id)

    if not server:
        return None

    return ServerInfo(
        id=server.id,
        name=server.name,
        url=server.url or None,
        closed_message=server.closed_message or None,
    )


__all__ = ["ServerInfo", "get_ordered_servers", "get_server_by_id"]