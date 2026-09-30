"""Stale referrals: open, and nothing has happened for STALE_DAYS days.

"Nothing has happened" uses Referral.last_touch (the latest of the referral date, its step credits and its
logged activity), the same measure as the Referrals list's "Stale" view.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audited_insert
from app.models import Notification, Referral, ReferralStepCredit, User
from app.pipeline import OPEN

STALE_DAYS = 14  # decided 2026-09-30 (DECISIONS.md, "Background jobs")


def stale_cutoff(today: date) -> date:
    """A referral last touched on or before this day is stale."""
    return today - timedelta(days=STALE_DAYS)


def is_stale(referral: Referral, today: date) -> bool:
    return referral.status in OPEN and referral.last_touch <= stale_cutoff(today)


def stale_key(referral_id: object, last_touch: date) -> str:
    """One nudge per stale spell: a touch moves last_touch, so going stale again is a new key (a new nudge)."""
    return f"stale:{referral_id}:{last_touch.isoformat()}"


async def notify_stale(db: AsyncSession, today: date) -> int:
    """Nudge every active rep credited on a stale referral. Returns how many new nudges were written.

    Idempotent: rows already written for the same stale spell are skipped by the database (the live unique
    index on user_id + dedupe_key), so a retried or repeated run adds nothing.
    """
    rows = (
        await db.execute(
            select(Referral.id, Referral.last_touch, ReferralStepCredit.rep_id)
            .join(ReferralStepCredit, ReferralStepCredit.referral_id == Referral.id)
            .join(User, User.id == ReferralStepCredit.rep_id)
            .where(Referral.status.in_(OPEN), Referral.last_touch <= stale_cutoff(today), User.active)
            .distinct()
        )
    ).all()
    if not rows:
        return 0

    written = await audited_insert(
        db,
        Notification,
        [
            {
                "user_id": rep_id,
                "kind": "stale_referral",
                "referral_id": referral_id,
                "dedupe_key": stale_key(referral_id, last_touch),
                "data": {"last_touch": last_touch.isoformat()},
            }
            for referral_id, last_touch, rep_id in rows
        ],
        skip_duplicates_on=["user_id", "dedupe_key"],
        where=Notification.deleted_at.is_(None),
    )
    await db.commit()
    return len(written)
