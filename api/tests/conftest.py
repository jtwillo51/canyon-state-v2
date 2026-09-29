"""Test setup: a migrated canyon_test database, one rolled-back transaction per test.

Run from api/:  uv run pytest
"""

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import date

# Point the app at canyon_test BEFORE anything imports app settings. Same server and credentials
# as DATABASE_URL (from the environment, or api/.env), different database.
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

_base = os.environ.get("DATABASE_URL") or dotenv_values(".env")["DATABASE_URL"]
TEST_URL = make_url(_base).set(database="canyon_test")
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)
os.environ["DEV_AUTH"] = "true"

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Carrier, Partner, Referral, ReferralStepCredit, User  # noqa: E402

assert TEST_URL.database == "canyon_test", "tests must never run against another database"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    """Bring canyon_test to the latest migration once per run (this also tests the migrations)."""
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is always rolled back: nothing a test writes survives."""
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        # Commits inside the app become savepoints, so the outer rollback still undoes them.
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest.fixture
async def api(db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client for the app, with every request using the test's session."""

    async def _test_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = _test_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def as_user(user: User) -> dict[str, str]:
    return {"X-Dev-User": str(user.id)}


@dataclass
class World:
    """A tiny agency: one admin, two reps, one partner, one referral credited to each rep."""

    dana: User  # admin
    tessa: User  # rep
    jordan: User  # rep
    partner: Partner
    tessas_referral: Referral
    tessas_credit: ReferralStepCredit
    jordans_referral: Referral


@pytest.fixture
async def world(db: AsyncSession) -> World:
    dana = User(name="Dana Admin", email="dana@example.test", role="admin")
    tessa = User(name="Tessa Rep", email="tessa@example.test", role="rep")
    jordan = User(name="Jordan Rep", email="jordan@example.test", role="rep")
    carrier = Carrier(name="Test Mutual")
    db.add_all([dana, tessa, jordan, carrier])
    await db.flush()  # assigns the UUIDs

    partner = Partner(
        name="Pat Partner", type="Realtor", primary_rep_id=tessa.id, sensitive_items="Avoid talking about the move."
    )
    db.add(partner)
    await db.flush()

    def referral(client: str) -> Referral:
        return Referral(
            partner_id=partner.id,
            client_name=client,
            client_address="100 Test St, Mesa, AZ",
            client_birthday=date(1980, 5, 1),
            line_of_business="Home",
            carrier_id=carrier.id,
            referred_date=date(2026, 9, 1),
        )

    tessas, jordans = referral("Client Tessa"), referral("Client Jordan")
    db.add_all([tessas, jordans])
    await db.flush()

    tessas_credit = ReferralStepCredit(referral_id=tessas.id, step="introduction", rep_id=tessa.id, date=date(2026, 9, 1))  # fmt: skip
    db.add_all([
        tessas_credit,
        ReferralStepCredit(referral_id=jordans.id, step="introduction", rep_id=jordan.id, date=date(2026, 9, 1)),
    ])  # fmt: skip
    await db.flush()
    return World(dana, tessa, jordan, partner, tessas, tessas_credit, jordans)
