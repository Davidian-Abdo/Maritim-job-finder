import asyncio
from app.db import engine
from sqlalchemy import text

async def test():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ Database is reachable!")
    except Exception as e:
        print(f"❌ Database error: {e}")

asyncio.run(test())