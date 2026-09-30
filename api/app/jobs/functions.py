"""The scheduled jobs, as Inngest functions.

Each job is a thin wrapper: the logic lives in stale.py and digest.py (plain async functions pytest calls
directly). What Inngest adds is the schedule, retries, and durable steps: every `ctx.step.run(...)` is
checkpointed, so a retry re-runs only the step that failed, and a step's saved result is replayed, never
recomputed. That's why "today" is its own first step: a retry that lands after midnight still works on the
day the run started.

Step results must be JSON (Inngest stores them), so steps pass ids and ISO dates, not ORM objects.
"""

import logging
import uuid
from contextlib import AbstractAsyncContextManager
from datetime import date
from typing import Callable

import inngest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Actor, set_actor
from app.clock import AGENCY_TZ, agency_today
from app.config import settings
from app.db import SessionLocal
from app.jobs.digest import build_digest, store_digest
from app.jobs.stale import notify_stale
from app.models import User

client = inngest.Inngest(
    app_id="canyon-state",
    # Production unless the local Dev Server is explicitly on (config refuses that outside local development).
    is_production=not settings.inngest_dev,
    signing_key=settings.inngest_signing_key.get_secret_value() if settings.inngest_signing_key else None,
    logger=logging.getLogger("app.jobs"),
)

# Where steps get a database session. Tests swap it for their rolled-back test session.
session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = SessionLocal

# Crons run on the agency's clock, not the server's (UTC).
TZ = f"TZ={AGENCY_TZ.key}"


async def _today() -> str:
    return agency_today().isoformat()


# --- Stale referrals: every morning --------------------------------------------------------------------


async def _notify_stale(today: str) -> int:
    async with session_factory() as db:
        set_actor(db, Actor.job("stale-referrals"))
        return await notify_stale(db, date.fromisoformat(today))


async def stale_referrals(ctx: inngest.Context) -> dict[str, int]:
    today = await ctx.step.run("agency-today", _today)
    written = await ctx.step.run("notify-reps", _notify_stale, today)
    return {"new_nudges": written}


# --- Weekly digest: Monday morning, one step per person ------------------------------------------------


async def _recipients() -> list[str]:
    async with session_factory() as db:
        ids = (await db.execute(select(User.id).where(User.active).order_by(User.name))).scalars()
        return [str(i) for i in ids]


async def _digest_for(user_id: str, today: str) -> bool:
    async with session_factory() as db:
        user = await db.get(User, uuid.UUID(user_id))
        if user is None or not user.active:  # deactivated since the recipients step ran
            return False
        set_actor(db, Actor.job("weekly-digest"))
        digest = await build_digest(db, user, date.fromisoformat(today))
        return await store_digest(db, user.id, digest)


async def weekly_digest(ctx: inngest.Context) -> dict[str, int]:
    today = await ctx.step.run("agency-today", _today)
    recipients = await ctx.step.run("recipients", _recipients)
    written = 0
    for user_id in recipients:
        # One step per person: if one digest fails, only that one is retried.
        if await ctx.step.run(f"digest-{user_id}", _digest_for, user_id, today):
            written += 1
    return {"recipients": len(recipients), "new_digests": written}


FUNCTIONS = [
    client.create_function(
        fn_id="stale-referrals",
        name="Nudge reps about stale referrals",
        trigger=inngest.TriggerCron(cron=f"{TZ} 0 6 * * *"),  # 6:00 am daily
        retries=3,
    )(stale_referrals),
    client.create_function(
        fn_id="weekly-digest",
        name="Weekly digest",
        trigger=inngest.TriggerCron(cron=f"{TZ} 0 7 * * 1"),  # 7:00 am Mondays
        retries=3,
    )(weekly_digest),
]
