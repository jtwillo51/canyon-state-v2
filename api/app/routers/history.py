"""Change history from the audit trail (app/audit.py), for anyone who can see the record.

- A referral's history (its own changes, its step credits, its logged activity): the referral's reps and
  admins, through visible_referrals, so someone else's is a 404 like the referral itself.
- A partner's history (the partner and its production figures only): everyone, since partners are shared.
  Never its referrals' events, which would reveal colleagues' clients.

Sensitive values were never stored, so there's nothing to mask here: those changes read "changed" only.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth import DB, Viewer
from app.models import AuditEvent, Carrier, Partner, Referral, User
from app.routers.referrals import visible_referrals
from app.schemas import FieldChange, HistoryEvent, UserRef

router = APIRouter(tags=["history"])

LIMIT = 200  # newest first; a record's whole working life fits comfortably

# Fields holding ids that read better as names.
USER_FIELDS = frozenset({"primary_rep_id", "rep_id", "logged_by_id", "user_id"})
CARRIER_FIELDS = frozenset({"carrier_id"})


async def _history(db: DB, *conditions: Any) -> list[HistoryEvent]:
    events = (
        await db.execute(
            select(AuditEvent).where(*conditions).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id).limit(LIMIT)
        )
    ).scalars().all()  # fmt: skip

    # Names for every person and carrier mentioned, in two queries. Deactivated or removed ones included:
    # history must still say who did something after they've left.
    user_ids, carrier_ids = set(), set()
    for e in events:
        if e.actor_id:
            user_ids.add(e.actor_id)
        for field, change in e.changes.items():
            ids = {change.get("from"), change.get("to")} - {None}
            if field in USER_FIELDS:
                user_ids |= {uuid.UUID(i) for i in ids}
            elif field in CARRIER_FIELDS:
                carrier_ids |= {uuid.UUID(i) for i in ids}
    opts = {"include_deleted": True}
    users = {u.id: u for u in (await db.execute(select(User).where(User.id.in_(user_ids)).execution_options(**opts))).scalars()}
    carriers = {
        c.id: c.name
        for c in (await db.execute(select(Carrier).where(Carrier.id.in_(carrier_ids)).execution_options(**opts))).scalars()
    }

    def label(field: str, value: Any) -> str | None:
        if value is None:
            return None
        if field in USER_FIELDS:
            u = users.get(uuid.UUID(value))
            return u.name if u else None
        if field in CARRIER_FIELDS:
            return carriers.get(uuid.UUID(value))
        return None

    out = []
    for e in events:
        changes = [
            FieldChange(field=f, redacted=True)
            if c.get("redacted")
            else FieldChange(field=f, before=c.get("from"), after=c.get("to"),
                             before_label=label(f, c.get("from")), after_label=label(f, c.get("to")))  # fmt: skip
            for f, c in e.changes.items()
            if f != "deleted_at"  # the action already says "delete" or "restore"
        ]
        actor = users.get(e.actor_id) if e.actor_id else None
        out.append(
            HistoryEvent(
                id=e.id,
                occurred_at=e.occurred_at,
                actor=UserRef.model_validate(actor) if actor else None,
                actor_label=e.actor_label,
                action=e.action,
                entity=e.entity,
                entity_id=e.entity_id,
                changes=changes,
            )
        )
    return out


@router.get("/referrals/{referral_id}/history")
async def referral_history(referral_id: uuid.UUID, viewer: Viewer, db: DB) -> list[HistoryEvent]:
    if (await db.execute(visible_referrals(viewer).where(Referral.id == referral_id))).scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")
    return await _history(db, AuditEvent.referral_id == referral_id)


@router.get("/partners/{partner_id}/history")
async def partner_history(partner_id: uuid.UUID, viewer: Viewer, db: DB) -> list[HistoryEvent]:
    if (await db.execute(select(Partner.id).where(Partner.id == partner_id))).scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Partner not found")
    return await _history(db, AuditEvent.partner_id == partner_id)
