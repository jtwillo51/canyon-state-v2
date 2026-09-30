"""Create the local canyon_dev, canyon_test (pytest) and canyon_e2e (Playwright) databases if they don't exist.

Uses the credentials in DATABASE_URL (api/.env), so no password prompt is needed.
Run from api/:  uv run python -m scripts.create_databases
"""

import asyncio

import asyncpg
from sqlalchemy.engine import make_url

from app.config import settings

DATABASES = ("canyon_dev", "canyon_test", "canyon_e2e")


async def main() -> None:
    url = make_url(settings.database_url)
    # Connect to the built-in "postgres" database: you can't create a database from inside itself.
    conn = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database="postgres",
    )
    try:
        existing = {row["datname"] for row in await conn.fetch("SELECT datname FROM pg_database")}
        for name in DATABASES:
            if name in existing:
                print(f"{name}: already exists")
            else:
                await conn.execute(f'CREATE DATABASE "{name}"')
                print(f"{name}: created")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
