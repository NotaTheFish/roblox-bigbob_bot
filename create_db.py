import asyncio

from bot.db import init_db


async def _create() -> None:
    print("⏳ Creating tables in PostgreSQL...")
    await init_db()
    print("✅ Tables created successfully!")


if __name__ == "__main__":
    asyncio.run(_create())