"""Referrals are scoped: admins see all; a rep sees the referrals they have a step credit on."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.auth import DB, Viewer, is_admin
from app.clock import agency_today
from app.models import Referral, ReferralStepCredit, User
from app.pipeline import OPEN, PipelineError, apply_move, check_move
from app.policy import mask
from app.schemas import PipelineErrorOut, ReferralOut, StatusChange

router = APIRouter(prefix="/referrals", tags=["referrals"])

# How long bound and lost referrals stay on the pipeline board.
BOARD_RECENT_DAYS = 30


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


# Declared before /{referral_id}, or "pipeline" would be parsed as an id.
@router.get("/pipeline")
async def pipeline_board(viewer: Viewer, db: DB) -> list[ReferralOut]:
    """Open referrals, plus those bound or lost in the last 30 days."""
    since = agency_today() - timedelta(days=BOARD_RECENT_DAYS)
    stmt = (
        visible_referrals(viewer)
        .where(
            or_(
                Referral.status.in_(OPEN),
                and_(Referral.status == "bound", Referral.bound_date >= since),
                and_(Referral.status == "lost", Referral.lost_date >= since),
            )
        )
        .order_by(Referral.referred_date.desc())
    )
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


@router.post("/{referral_id}/status", responses={422: {"model": PipelineErrorOut}})
async def change_status(referral_id: uuid.UUID, change: StatusChange, viewer: Viewer, db: DB) -> ReferralOut:
    """Move a referral on the pipeline (see app/pipeline.py for the rules)."""
    # FOR UPDATE locks the row until commit, so two people moving the same card at once can't both win.
    stmt = visible_referrals(viewer).where(Referral.id == referral_id).with_for_update(of=Referral)
    referral = (await db.execute(stmt)).scalar_one_or_none()
    if referral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")

    try:
        check_move(referral, change.status, viewer)
        credit_rep = await _credit_rep(change, viewer, db)
        new_credits = apply_move(
            referral,
            change.status,
            credit_rep=credit_rep,
            premium=change.premium,
            bound_date=change.bound_date,
            today=agency_today(),
        )
    except PipelineError as e:
        return JSONResponse(  # type: ignore[return-value]
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=PipelineErrorOut(message=str(e), field=e.field).model_dump(),
        )

    db.add_all(new_credits)
    await db.commit()
    # Re-read with fresh steps (new credits in, un-credited ones filtered out). Still visible: admins see
    # everything, and a rep can only move forward or to lost, which never removes their own credit.
    stmt = visible_referrals(viewer).where(Referral.id == referral_id).execution_options(populate_existing=True)
    return to_out((await db.execute(stmt)).scalar_one(), viewer)


async def _credit_rep(change: StatusChange, viewer: User, db: DB) -> User | None:
    """Who gets credit for steps this move passes: a rep themselves, or the rep an admin names."""
    if not is_admin(viewer):
        if change.credit_rep_id not in (None, viewer.id):
            raise PipelineError("Reps can only credit themselves.", field="credit_rep_id")
        return viewer
    if change.credit_rep_id is None:
        return None  # fine unless the move passes a step; apply_move checks
    rep = (
        await db.execute(select(User).where(User.id == change.credit_rep_id, User.role == "rep", User.active))
    ).scalar_one_or_none()
    if rep is None:
        raise PipelineError("Choose an active rep.", field="credit_rep_id")
    return rep
