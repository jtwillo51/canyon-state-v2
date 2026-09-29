"""Development-only helpers. The web app's "View as" switcher lists people from here.

Returns 404 unless DEV_AUTH is on, so a deployed API doesn't reveal its user list.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth import DB
from app.config import settings
from app.models import User
from app.schemas import DevUserOut

router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/users")
async def list_dev_users(db: DB) -> list[DevUserOut]:
    if not settings.dev_auth:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    users = (await db.execute(select(User).where(User.active).order_by(User.role, User.name))).scalars().all()
    return [DevUserOut.model_validate(u) for u in users]
