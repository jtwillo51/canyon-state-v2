"""Partners are shared: every signed-in user sees every partner."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload, selectinload

from app.auth import DB, Viewer
from app.models import Partner
from app.schemas import PartnerOut

router = APIRouter(prefix="/partners", tags=["partners"])


def _partners() -> Select[tuple[Partner]]:
    # Async can't lazy-load, so every relationship the schema reads is loaded here, up front.
    return select(Partner).options(joinedload(Partner.primary_rep), selectinload(Partner.production))


@router.get("")
async def list_partners(viewer: Viewer, db: DB) -> list[PartnerOut]:
    partners = (await db.execute(_partners().order_by(Partner.name))).scalars().all()
    return [PartnerOut.model_validate(p) for p in partners]


@router.get("/{partner_id}")
async def get_partner(partner_id: uuid.UUID, viewer: Viewer, db: DB) -> PartnerOut:
    partner = (await db.execute(_partners().where(Partner.id == partner_id))).scalar_one_or_none()
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Partner not found")
    return PartnerOut.model_validate(partner)
