# wipe_db.py
import asyncio
from db.models import Base
from bot.db import engine

async def wipe():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(wipe())
    print("✅ DATABASE DROPPED AND RECREATED")
