"""The weekly digest: last week's numbers for each person, stored as a notification.

The numbers come from app/progress.py (the dashboard's definitions), and the visibility split is the
dashboard's too: a rep's digest holds only their own numbers; an admin's holds the company and every rep.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.stale import stale_cutoff
from app.models import Notification, Referral, ReferralStepCredit, User
from app.pipeline import OPEN
from app.progress import Tally, tallies
from app.schemas import DigestData, RepWeek, UserRef, WeekTally


def last_week(today: date) -> tuple[date, date]:
    """Monday to Sunday of the week before the one `today` is in."""
    start = today - timedelta(days=today.weekday() + 7)
    return start, start + timedelta(days=6)


def digest_key(week_start: date) -> str:
    return f"digest:{week_start.isoformat()}"


async def _new_referrals(db: AsyncSession, start: date, end: date) -> tuple[int, dict[uuid.UUID, int]]:
    """Referrals referred in the window: the company's count, and each rep's (by introduction credit)."""
    in_window = Referral.referred_date.between(start, end)
    total = (await db.execute(select(func.count()).select_from(Referral).where(in_window))).scalar_one()
    intro = and_(ReferralStepCredit.referral_id == Referral.id, ReferralStepCredit.step == "introduction")
    by_rep = await db.execute(
        select(ReferralStepCredit.rep_id, func.count()).join(Referral, intro).where(in_window).group_by(ReferralStepCredit.rep_id)
    )  # fmt: skip
    return total, {rep_id: n for rep_id, n in by_rep}


async def _stale(db: AsyncSession, today: date) -> tuple[int, dict[uuid.UUID, int]]:
    """Open referrals stale today: the company's count, and each credited rep's."""
    stale = and_(Referral.status.in_(OPEN), Referral.last_touch <= stale_cutoff(today))
    total = (await db.execute(select(func.count()).select_from(Referral).where(stale))).scalar_one()
    by_rep = await db.execute(
        select(ReferralStepCredit.rep_id, func.count(func.distinct(Referral.id)))
        .join(Referral, ReferralStepCredit.referral_id == Referral.id)
        .where(stale)
        .group_by(ReferralStepCredit.rep_id)
    )
    return total, {rep_id: n for rep_id, n in by_rep}


def _week(t: Tally, new: int) -> WeekTally:
    return WeekTally(new_referrals=new, clients=t.clients, sales=t.sales, close_rate=t.close_rate)


async def build_digest(db: AsyncSession, user: User, today: date) -> DigestData:
    start, end = last_week(today)
    company, reps = await tallies(db, start, end)
    new_total, new_by_rep = await _new_referrals(db, start, end)
    stale_total, stale_by_rep = await _stale(db, today)
    base = {"week_start": start, "week_end": end}

    if user.role != "admin":
        mine = _week(reps.get(user.id, Tally()), new_by_rep.get(user.id, 0))
        return DigestData(**base, mine=mine, stale=stale_by_rep.get(user.id, 0))

    team = (await db.execute(select(User).where(User.role == "rep", User.active).order_by(User.name))).scalars()
    rows = [
        RepWeek(rep=UserRef.model_validate(r), **_week(reps.get(r.id, Tally()), new_by_rep.get(r.id, 0)).model_dump())
        for r in team
    ]
    return DigestData(**base, company=_week(company, new_total), reps=rows, stale=stale_total)


async def store_digest(db: AsyncSession, user_id: uuid.UUID, digest: DigestData) -> bool:
    """Save one person's digest. Returns False if they already have this week's (a retry or a repeat run)."""
    stmt = (
        insert(Notification)
        .values(
            user_id=user_id,
            kind="weekly_digest",
            dedupe_key=digest_key(digest.week_start),
            data=digest.model_dump(mode="json"),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"], index_where=Notification.deleted_at.is_(None))
        .returning(Notification.id)
    )
    written = (await db.execute(stmt)).first() is not None
    await db.commit()
    return written
