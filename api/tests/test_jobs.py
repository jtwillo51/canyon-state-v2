"""The scheduled jobs (app/jobs/): who gets nudged and what digests hold, that re-runs are harmless, and that
the endpoint Inngest calls is locked down."""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.jobs import endpoint, functions
from app.jobs.digest import build_digest, last_week, store_digest
from app.jobs.stale import STALE_DAYS, notify_stale
from app.models import Activity, Notification, User
from tests.conftest import World

pytestmark = pytest.mark.anyio

TODAY = date(2026, 10, 5)  # a Monday; the world's referrals date from 2026-09-01, so both are stale


async def nudged(db: AsyncSession) -> list[tuple[str, str]]:
    rows = await db.execute(
        select(User.name, Notification.dedupe_key).join(User, User.id == Notification.user_id)
        .where(Notification.kind == "stale_referral").order_by(User.name)
    )  # fmt: skip
    return [(name, key) for name, key in rows]


# --- Stale referrals -----------------------------------------------------------------------------------


async def test_credited_reps_are_nudged_once_per_stale_spell(db: AsyncSession, world: World) -> None:
    assert await notify_stale(db, TODAY) == 2
    assert [name for name, _ in await nudged(db)] == ["Jordan Rep", "Tessa Rep"]  # each about their own
    assert await notify_stale(db, TODAY) == 0  # a retry or a second run writes nothing new
    assert await notify_stale(db, TODAY + timedelta(days=1)) == 0  # still the same spell tomorrow


async def test_fresh_and_closed_referrals_are_left_alone(db: AsyncSession, world: World) -> None:
    fresh_day = date(2026, 9, 1) + timedelta(days=STALE_DAYS - 1)  # one day short of stale
    assert await notify_stale(db, fresh_day) == 0
    world.jordans_referral.status, world.jordans_referral.bound_date = "bound", date(2026, 9, 10)
    await db.flush()
    assert await notify_stale(db, TODAY) == 1  # Tessa's only


async def test_touching_a_referral_starts_a_new_spell(db: AsyncSession, world: World) -> None:
    await notify_stale(db, TODAY)
    db.add(Activity(referral_id=world.tessas_referral.id, rep_id=world.tessa.id, logged_by_id=world.tessa.id,
                    date=date(2026, 9, 10), method="Phone"))  # fmt: skip
    await db.flush()
    assert await notify_stale(db, TODAY) == 1  # stale again since the 10th: a new nudge for Tessa
    assert ("Tessa Rep", f"stale:{world.tessas_referral.id}:2026-09-10") in await nudged(db)


async def test_inactive_reps_are_not_nudged(db: AsyncSession, world: World) -> None:
    world.jordan.active = False
    await db.flush()
    assert await notify_stale(db, TODAY) == 1


# --- Weekly digest -------------------------------------------------------------------------------------


def test_last_week_is_the_monday_to_sunday_before() -> None:
    assert last_week(date(2026, 10, 5)) == (date(2026, 9, 28), date(2026, 10, 4))  # run on a Monday
    assert last_week(date(2026, 10, 7)) == (date(2026, 9, 28), date(2026, 10, 4))  # a retry on Wednesday


async def bind_in_last_week(db: AsyncSession, world: World) -> None:
    """Tessa binds her referral on Wednesday of last week for $1,200."""
    from app.models import ReferralStepCredit

    r = world.tessas_referral
    r.status, r.premium, r.bound_date = "bound", 1200, date(2026, 9, 30)
    db.add(ReferralStepCredit(referral_id=r.id, step="bind", rep_id=world.tessa.id, date=date(2026, 9, 30)))
    await db.flush()


async def test_a_reps_digest_holds_only_their_own_numbers(db: AsyncSession, world: World) -> None:
    await bind_in_last_week(db, world)
    digest = await build_digest(db, world.tessa, TODAY)
    assert (digest.company, digest.reps) == (None, [])  # never the company's or a colleague's numbers
    assert digest.mine is not None
    assert (digest.mine.clients, float(digest.mine.sales), digest.mine.close_rate) == (1, 1200.0, 1.0)
    assert digest.stale == 0  # her only referral is bound
    jordans = await build_digest(db, world.jordan, TODAY)
    assert jordans.mine is not None and (jordans.mine.clients, jordans.stale) == (0, 1)


async def test_an_admins_digest_holds_the_company_and_every_rep(db: AsyncSession, world: World) -> None:
    await bind_in_last_week(db, world)
    digest = await build_digest(db, world.dana, TODAY)
    assert digest.mine is None and digest.company is not None
    assert (digest.company.clients, float(digest.company.sales), digest.stale) == (1, 1200.0, 1)
    assert [(r.rep.name, r.clients) for r in digest.reps] == [("Jordan Rep", 0), ("Tessa Rep", 1)]


async def test_a_digest_is_stored_once_per_week(db: AsyncSession, world: World) -> None:
    digest = await build_digest(db, world.tessa, TODAY)
    assert await store_digest(db, world.tessa.id, digest) is True
    assert await store_digest(db, world.tessa.id, digest) is False


# --- The Inngest functions, run with a stand-in for Inngest's step runner --------------------------------


class FakeStep:
    """Runs each step immediately, and insists its result is JSON, as Inngest's storage does."""

    def __init__(self) -> None:
        self.ids: list[str] = []

    async def run(self, step_id: str, handler: Callable[..., Awaitable[Any]], *args: Any) -> Any:
        assert step_id not in self.ids, "step ids must be unique within a run"
        self.ids.append(step_id)
        result = await handler(*args)
        json.dumps(result)
        return result


class FakeContext:
    def __init__(self) -> None:
        self.step = FakeStep()


@pytest.fixture
def job_session(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Steps open their own sessions; point them at the test's rolled-back one (left open for the test)."""

    @asynccontextmanager
    async def same_session() -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(functions, "session_factory", same_session)
    monkeypatch.setattr(functions, "agency_today", lambda: TODAY)


async def test_weekly_digest_job_writes_one_per_active_person(db: AsyncSession, world: World, job_session: None) -> None:
    ctx = FakeContext()
    result = await functions.weekly_digest(ctx)  # type: ignore[arg-type]
    assert result == {"recipients": 3, "new_digests": 3}  # Dana, Jordan, Tessa
    assert ctx.step.ids[:2] == ["agency-today", "recipients"]
    assert await functions.weekly_digest(FakeContext()) == {"recipients": 3, "new_digests": 0}  # type: ignore[arg-type]


async def test_stale_job_nudges_through_its_steps(db: AsyncSession, world: World, job_session: None) -> None:
    ctx = FakeContext()
    assert await functions.stale_referrals(ctx) == {"new_nudges": 2}  # type: ignore[arg-type]
    assert ctx.step.ids == ["agency-today", "notify-reps"]


def test_schedules_run_on_the_agencys_clock() -> None:
    crons = {f.id: f.get_config("http://test").main.triggers[0].cron for f in functions.FUNCTIONS}
    assert crons == {
        "canyon-state-stale-referrals": "TZ=America/Phoenix 0 6 * * *",
        "canyon-state-weekly-digest": "TZ=America/Phoenix 0 7 * * 1",
    }


# --- The endpoint Inngest calls ----------------------------------------------------------------------------


def app_with_jobs() -> FastAPI:
    app = FastAPI()
    router = endpoint.jobs_router()
    if router:
        app.include_router(router)
    return app


async def call(app: FastAPI, method: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, "/api/inngest", content=b"{}")


@pytest.mark.parametrize("method", ["GET", "POST", "PUT"])
async def test_endpoint_does_not_exist_unless_configured(method: str) -> None:
    assert not settings.jobs_enabled  # the test environment configures no jobs
    assert (await call(app_with_jobs(), method)).status_code == 404


@pytest.mark.parametrize("method", ["GET", "POST", "PUT"])  # inspect, run a function, re-register the app
async def test_production_endpoint_refuses_unsigned_requests(method: str, monkeypatch: pytest.MonkeyPatch) -> None:
    key = "signkey-prod-" + "ab" * 32
    monkeypatch.setattr(settings, "inngest_signing_key", SecretStr(key))
    monkeypatch.setattr(functions.client, "_signing_key", key)  # the client read its key at import
    r = await call(app_with_jobs(), method)
    assert r.status_code == 401, r.text  # it exists (not 404) and refuses (not 500): nothing runs, nothing syncs


def test_dev_mode_is_refused_outside_local_development() -> None:
    with pytest.raises(ValidationError, match="INNGEST_DEV"):
        Settings(database_url="postgresql://u:p@localhost/x", inngest_dev=True, dev_auth=False)
    assert Settings(database_url="postgresql://u:p@localhost/x", inngest_dev=True, dev_auth=True).jobs_enabled


async def test_no_notifications_left_behind(db: AsyncSession) -> None:
    """Sanity: tests roll back, so nothing written above survives into the next test."""
    assert (await db.execute(select(func.count()).select_from(Notification))).scalar_one() == 0
