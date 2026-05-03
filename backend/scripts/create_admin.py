"""Script to create an initial admin user."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import AsyncSessionLocal, engine, Base
from app.services.admin import create_admin_user


async def main():
    username = input("Admin username: ").strip()
    password = input("Admin password: ").strip()

    if not username or not password:
        print("Username and password are required.")
        return

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        admin = await create_admin_user(session, username, password)
        await session.commit()
        print(f"Admin user '{admin.username}' created successfully (id: {admin.id})")


if __name__ == "__main__":
    asyncio.run(main())
