"""The signed-in person's notifications: stale-referral nudges and weekly digests (written by app/jobs/).

Private to their recipient, admins included. A stale nudge is resolved at read time through the reader's own
scoping (visible_referrals): it shows only while the reader can still see the referral and it's still stale
in the same spell, so a nudge never outlives the reader's access and never lingers once someone acts.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select, update

from app.auth import DB, Viewer
from app.clock import agency_today
from app.jobs.stale import is_stale
from app.models import Notification, Referral
from app.routers.referrals import visible_referrals
from app.schemas import DigestData, NotificationOut, NotificationPage, PartnerRef, StaleReferralRef

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Enough history for a quarter of weekly digests; nudges are few because resolved ones drop out.
LIMIT = 100


@router.get("")
async def list_notifications(viewer: Viewer, db: DB) -> NotificationPage:
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == viewer.id)
            .order_by(Notification.created_at.desc(), Notification.id)
            .limit(LIMIT)
        )
    ).scalars().all()  # fmt: skip

    referral_ids = {n.referral_id for n in rows if n.referral_id}
    visible: dict[uuid.UUID, Referral] = {}
    if referral_ids:
        found = await db.execute(visible_referrals(viewer).where(Referral.id.in_(referral_ids)))
        visible = {r.id: r for r in found.scalars()}

    today = agency_today()
    stale: list[NotificationOut] = []
    digests: list[NotificationOut] = []
    for n in rows:
        base = {"id": n.id, "kind": n.kind, "created_at": n.created_at, "read_at": n.read_at}
        if n.kind == "weekly_digest":
            digests.append(NotificationOut(**base, digest=DigestData.model_validate(n.data)))
            continue
        r = visible.get(n.referral_id) if n.referral_id else None
        # Same spell only: once touched, last_touch moves on and this nudge is resolved.
        if r is None or not is_stale(r, today) or n.data.get("last_touch") != r.last_touch.isoformat():
            continue
        ref = StaleReferralRef(
            id=r.id,
            client_name=r.client_name,
            partner=PartnerRef.model_validate(r.partner),
            status=r.status,
            last_touch=r.last_touch,
            days_since_touch=(today - r.last_touch).days,
        )
        stale.append(NotificationOut(**base, stale=ref))

    stale.sort(key=lambda n: -n.stale.days_since_touch if n.stale else 0)  # most overdue first
    items = stale + digests
    return NotificationPage(items=items, unread=sum(1 for i in items if i.read_at is None))


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: uuid.UUID, viewer: Viewer, db: DB) -> Response:
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == viewer.id, Notification.deleted_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )  # fmt: skip
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")  # also for someone else's
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(viewer: Viewer, db: DB) -> Response:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == viewer.id, Notification.read_at.is_(None), Notification.deleted_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )  # fmt: skip
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
