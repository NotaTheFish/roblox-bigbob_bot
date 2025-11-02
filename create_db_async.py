import asyncio

from bot.db import init_db


async def create() -> None:
    await init_db()
    print("✅ Tables created")


if __name__ == "__main__":
    asyncio.run(create())