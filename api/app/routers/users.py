from fastapi import APIRouter
from sqlalchemy import select

from app.auth import DB, Viewer
from app.models import User
from app.schemas import Me, UserRef

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(viewer: Viewer) -> Me:
    """Who the API thinks is asking."""
    return Me.model_validate(viewer)


@router.get("/reps")
async def list_reps(viewer: Viewer, db: DB) -> list[UserRef]:
    """Active reps, e.g. for an admin choosing who gets credit for a pipeline move."""
    reps = (await db.execute(select(User).where(User.role == "rep", User.active).order_by(User.name))).scalars()
    return [UserRef.model_validate(u) for u in reps]
