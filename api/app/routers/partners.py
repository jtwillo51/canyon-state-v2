"""Partners are shared: every signed-in user sees every partner, and team-wide referral counts on them.
Money is scoped (v1's rule): a rep's bound premium counts only referrals they're credited on."""

import uuid
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import ColumnElement, Float, Select, and_, case, cast, func, or_, select, true
from sqlalchemy.orm import joinedload, selectinload

from app.auth import DB, Viewer
from app.clock import agency_today
from app.models import Partner, Referral, User
from app.schemas import PartnerOut, PartnerPage, PartnerQuery, PartnerRow, PartnerStats
from app.scoping import referral_scope
from app.search import contains

router = APIRouter(prefix="/partners", tags=["partners"])


def _partners() -> Select[tuple[Partner]]:
    # Async can't lazy-load, so every relationship the schema reads is loaded here, up front.
    return select(Partner).options(joinedload(Partner.primary_rep), selectinload(Partner.production))


def _period_start(period: str, today: date) -> date | None:
    return {"r12": today - timedelta(days=365), "ytd": date(today.year, 1, 1)}.get(period)


def _stats_subquery(since: date | None, viewer: User):
    """One row per partner with referrals: counts for the period, and premium scoped to the viewer."""
    in_period = Referral.referred_date >= since if since else true()
    bound = and_(in_period, Referral.status == "bound")
    return (
        select(
            Referral.partner_id.label("partner_id"),
            func.count().filter(in_period).label("referrals"),
            func.count().filter(bound).label("bound"),
            func.sum(Referral.premium).filter(and_(bound, *referral_scope(viewer))).label("bound_premium"),
            func.max(Referral.referred_date).label("last_referred"),
        )
        .where(Referral.deleted_at.is_(None))  # explicit: this is an aggregate, not an entity load
        .group_by(Referral.partner_id)
        .subquery("stats")
    )


@router.get("")
async def list_partners(viewer: Viewer, db: DB, f: Annotated[PartnerQuery, Query()]) -> PartnerPage:
    """Partners with their referral numbers for the period: filtered, sorted and paged."""
    stats = _stats_subquery(_period_start(f.period, agency_today()), viewer)
    referrals = func.coalesce(stats.c.referrals, 0)
    bound = func.coalesce(stats.c.bound, 0)
    close_rate = case((referrals > 0, cast(bound, Float) / referrals), else_=None)
    premium = func.coalesce(stats.c.bound_premium, 0)

    where: list[ColumnElement[bool]] = []
    if f.type:
        where.append(Partner.type.in_(f.type))
    if f.primary_rep_id:
        where.append(Partner.primary_rep_id == f.primary_rep_id)
    if f.unassigned is not None:
        where.append(Partner.primary_rep_id.is_(None) if f.unassigned else Partner.primary_rep_id.is_not(None))
    if f.do_not_contact is not None:
        where.append(Partner.do_not_contact.is_(f.do_not_contact))
    if f.no_referrals is not None:
        where.append(referrals == 0 if f.no_referrals else referrals > 0)
    if f.q:
        where.append(or_(contains(Partner.name, f.q), contains(Partner.business_name, f.q)))

    sort_columns: dict[str, ColumnElement[Any]] = {
        "name": func.lower(Partner.name),
        "referrals": referrals,
        "bound": bound,
        "close_rate": close_rate,
        "bound_premium": premium,
        "last_referred": stats.c.last_referred,
    }
    column = sort_columns[f.sort.removeprefix("-")]
    order = (column.desc() if f.sort.startswith("-") else column.asc()).nulls_last()

    joined = _partners().add_columns(referrals, bound, close_rate, premium, stats.c.last_referred)
    page = (
        joined.outerjoin(stats, stats.c.partner_id == Partner.id)
        .where(*where)
        .order_by(order, func.lower(Partner.name), Partner.id)
        .limit(f.limit)
        .offset(f.offset)
    )
    count = select(func.count()).select_from(Partner).outerjoin(stats, stats.c.partner_id == Partner.id).where(*where)

    rows = (await db.execute(page)).unique().all()
    total = (await db.execute(count)).scalar_one()
    items = [
        PartnerRow(
            **PartnerOut.model_validate(p).model_dump(),
            stats=PartnerStats(referrals=n, bound=b, close_rate=rate, bound_premium=money, last_referred=last),
        )
        for p, n, b, rate, money, last in rows
    ]
    return PartnerPage(items=items, total=total, limit=f.limit, offset=f.offset)


@router.get("/{partner_id}")
async def get_partner(partner_id: uuid.UUID, viewer: Viewer, db: DB) -> PartnerOut:
    partner = (await db.execute(_partners().where(Partner.id == partner_id))).scalar_one_or_none()
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Partner not found")
    return PartnerOut.model_validate(partner)
