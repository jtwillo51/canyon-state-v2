"""Run the scheduled jobs once, now, without Inngest: stale-referral nudges and this week's digests.

The same logic the Inngest functions run (app/jobs/), for seeding: the e2e stack and the demo's nightly
reseed call it right after scripts.seed so there are notifications to show. Idempotent like the jobs
themselves, so running it twice changes nothing.

Run from api/:  uv run python -m scripts.run_jobs
"""

import asyncio

from sqlalchemy import select

from app.audit import Actor, set_actor
from app.clock import agency_today
from app.db import SessionLocal, engine
from app.jobs.digest import build_digest, store_digest
from app.jobs.stale import notify_stale
from app.models import User


async def main() -> None:
    today = agency_today()
    async with SessionLocal() as db:
        set_actor(db, Actor.script("run_jobs"))
        nudges = await notify_stale(db, today)
        users = (await db.execute(select(User).where(User.active).order_by(User.name))).scalars().all()
        digests = sum([await store_digest(db, u.id, await build_digest(db, u, today)) for u in users])
    await engine.dispose()
    print(f"stale nudges: {nudges} new; digests: {digests} new of {len(users)} people")


if __name__ == "__main__":
    asyncio.run(main())
