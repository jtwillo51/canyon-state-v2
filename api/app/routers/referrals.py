"""Referrals are scoped: admins see all; a rep sees the referrals they have a step credit on."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload, selectinload

from app.auth import DB, Viewer, is_admin
from app.models import Referral, ReferralStepCredit, User
from app.policy import mask
from app.schemas import ReferralOut

router = APIRouter(prefix="/referrals", tags=["referrals"])


def visible_referrals(viewer: User) -> Select[tuple[Referral]]:
    """The referrals this viewer may see. Every referral query starts here."""
    stmt = select(Referral).options(
        joinedload(Referral.partner),
        joinedload(Referral.carrier),
        selectinload(Referral.steps).joinedload(ReferralStepCredit.rep),
    )
    if is_admin(viewer):
        return stmt
    # A soft-deleted step credit no longer makes the rep an owner (the soft-delete filter covers subqueries).
    owned = select(ReferralStepCredit.referral_id).where(ReferralStepCredit.rep_id == viewer.id)
    return stmt.where(Referral.id.in_(owned))


def to_out(referral: Referral, viewer: User) -> ReferralOut:
    owners = {s.rep_id for s in referral.steps}
    return mask(ReferralOut.model_validate(referral), "referral", viewer, owners)


@router.get("")
async def list_referrals(viewer: Viewer, db: DB, partner_id: uuid.UUID | None = None) -> list[ReferralOut]:
    stmt = visible_referrals(viewer).order_by(Referral.referred_date.desc())
    if partner_id is not None:
        stmt = stmt.where(Referral.partner_id == partner_id)
    referrals = (await db.execute(stmt)).scalars().all()
    return [to_out(r, viewer) for r in referrals]


@router.get("/{referral_id}")
async def get_referral(referral_id: uuid.UUID, viewer: Viewer, db: DB) -> ReferralOut:
    stmt = visible_referrals(viewer).where(Referral.id == referral_id)
    referral = (await db.execute(stmt)).scalar_one_or_none()
    if referral is None:
        # 404, not 403, for someone else's referral: don't confirm that it exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")
    return to_out(referral, viewer)
