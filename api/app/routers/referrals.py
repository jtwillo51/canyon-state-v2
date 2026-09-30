"""Referrals are scoped: admins see all; a rep sees the referrals they have a step credit on."""

import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.auth import DB, Viewer, is_admin
from app.clock import agency_today
from app.errors import FIELD_ERROR_RESPONSE, FieldError
from app.models import Activity, Referral, ReferralStepCredit, User
from app.pipeline import OPEN, PipelineError, apply_move, check_move
from app.policy import mask
from app.scoping import credited_to, referral_scope
from app.search import contains
from app.schemas import ActivityIn, ActivityOut, ReferralOut, ReferralPage, ReferralQuery, StatusChange

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
    return stmt.where(*referral_scope(viewer))


def to_out(referral: Referral, viewer: User) -> ReferralOut:
    owners = {s.rep_id for s in referral.steps}
    return mask(ReferralOut.model_validate(referral), "referral", viewer, owners)


# Pipeline order, so sorting by status reads referred -> lost rather than alphabetically.
_STATUS_ORDER = case({"referred": 0, "contacted": 1, "quoted": 2, "bound": 3, "lost": 4}, value=Referral.status)
_SORT_COLUMNS: dict[str, ColumnElement[Any]] = {
    "referred_date": Referral.referred_date,
    "last_touch": Referral.last_touch,
    "client_name": func.lower(Referral.client_name),
    "premium": Referral.premium,
    "status": _STATUS_ORDER,
}


def _filters(f: ReferralQuery) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if f.status:
        conditions.append(Referral.status.in_(f.status))
    if f.line:
        conditions.append(Referral.line_of_business.in_(f.line))
    if f.partner_id:
        conditions.append(Referral.partner_id == f.partner_id)
    if f.rep_id:
        conditions.append(credited_to(f.rep_id))
    if f.stale_days:
        # v1's "stale": still open, and nothing has happened for this many days.
        conditions += [Referral.status.in_(OPEN), Referral.last_touch <= agency_today() - timedelta(days=f.stale_days)]
    if f.bound_from:
        conditions.append(Referral.bound_date >= f.bound_from)
    if f.bound_to:
        conditions.append(Referral.bound_date <= f.bound_to)
    if f.has_premium is not None:
        conditions.append(Referral.premium.is_not(None) if f.has_premium else Referral.premium.is_(None))
    if f.q:
        conditions.append(contains(Referral.client_name, f.q))
    return conditions


@router.get("")
async def list_referrals(viewer: Viewer, db: DB, f: Annotated[ReferralQuery, Query()]) -> ReferralPage:
    """A filtered, sorted page of the referrals this viewer may see."""
    where = [*referral_scope(viewer), *_filters(f)]  # scope applies to the count too, not just the page
    key = f.sort.removeprefix("-")
    column = _SORT_COLUMNS[key]
    order = (column.desc() if f.sort.startswith("-") else column.asc()).nulls_last()

    page_stmt = visible_referrals(viewer).where(*where).order_by(order, Referral.id).limit(f.limit).offset(f.offset)
    count_stmt = select(func.count()).select_from(Referral).where(*where)
    referrals = (await db.execute(page_stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return ReferralPage(items=[to_out(r, viewer) for r in referrals], total=total, limit=f.limit, offset=f.offset)


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


@router.post("/{referral_id}/status", responses=FIELD_ERROR_RESPONSE)
async def change_status(referral_id: uuid.UUID, change: StatusChange, viewer: Viewer, db: DB) -> ReferralOut:
    """Move a referral on the pipeline (see app/pipeline.py for the rules)."""
    # FOR UPDATE locks the row until commit, so two people moving the same card at once can't both win.
    stmt = visible_referrals(viewer).where(Referral.id == referral_id).with_for_update(of=Referral)
    referral = (await db.execute(stmt)).scalar_one_or_none()
    if referral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")

    # A PipelineError from any of these becomes a 422 {message, field} (app/errors.py).
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
    db.add_all(new_credits)
    await db.commit()
    # Re-read with fresh steps (new credits in, un-credited ones filtered out). Still visible: admins see
    # everything, and a rep can only move forward or to lost, which never removes their own credit.
    stmt = visible_referrals(viewer).where(Referral.id == referral_id).execution_options(populate_existing=True)
    return to_out((await db.execute(stmt)).scalar_one(), viewer)


async def _visible_referral(referral_id: uuid.UUID, viewer: User, db: DB) -> Referral:
    referral = (await db.execute(visible_referrals(viewer).where(Referral.id == referral_id))).scalar_one_or_none()
    if referral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")
    return referral


def _activities() -> Select[tuple[Activity]]:
    return select(Activity).options(joinedload(Activity.rep), joinedload(Activity.logged_by))


@router.get("/{referral_id}/activities")
async def list_activities(referral_id: uuid.UUID, viewer: Viewer, db: DB) -> list[ActivityOut]:
    """Logged touches on a referral, newest first. Whoever can see the referral sees these."""
    await _visible_referral(referral_id, viewer, db)
    stmt = _activities().where(Activity.referral_id == referral_id).order_by(
        Activity.date.desc(), Activity.created_at.desc()
    )
    return [ActivityOut.model_validate(a) for a in (await db.execute(stmt)).scalars()]


@router.post("/{referral_id}/activities", status_code=status.HTTP_201_CREATED, responses=FIELD_ERROR_RESPONSE)
async def log_activity(referral_id: uuid.UUID, entry: ActivityIn, viewer: Viewer, db: DB) -> ActivityOut:
    """Log a call, email or meeting with the client. Doesn't change steps or credit."""
    referral = await _visible_referral(referral_id, viewer, db)
    if not referral.referred_date <= entry.date <= agency_today():
        raise FieldError("The date must be between the referral date and today.", field="date")
    # Anyone on the team may have made the contact (people log on a colleague's behalf).
    rep = (await db.execute(select(User).where(User.id == entry.rep_id, User.active))).scalar_one_or_none()
    if rep is None:
        raise FieldError("Choose an active team member.", field="rep_id")

    activity = Activity(
        referral_id=referral.id,
        rep_id=rep.id,
        logged_by_id=viewer.id,
        method=entry.method,
        notes=entry.notes.strip(),
        date=entry.date,
    )
    db.add(activity)
    await db.commit()
    created = (await db.execute(_activities().where(Activity.id == activity.id))).scalar_one()
    return ActivityOut.model_validate(created)


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
