from fastapi import APIRouter
from sqlalchemy import select

from app.auth import DB, Viewer
from app.models import Carrier
from app.schemas import CarrierRef

router = APIRouter(prefix="/carriers", tags=["carriers"])


@router.get("")
async def list_carriers(viewer: Viewer, db: DB) -> list[CarrierRef]:
    carriers = (await db.execute(select(Carrier).order_by(Carrier.name))).scalars()
    return [CarrierRef.model_validate(c) for c in carriers]
