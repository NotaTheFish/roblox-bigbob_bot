import asyncio
from bot.db import Base, engine

async def create():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")

asyncio.run(create())
