"""Saved list views. Private: each person sees and manages only their own."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import DB, Viewer
from app.errors import FIELD_ERROR_RESPONSE, FieldError
from app.models import ListName, SavedView
from app.schemas import SavedViewIn, SavedViewOut

router = APIRouter(prefix="/views", tags=["views"])


@router.get("")
async def list_views(list: ListName, viewer: Viewer, db: DB) -> list[SavedViewOut]:
    stmt = select(SavedView).where(SavedView.user_id == viewer.id, SavedView.list == list).order_by(SavedView.name)
    return [SavedViewOut.model_validate(v) for v in (await db.execute(stmt)).scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, responses=FIELD_ERROR_RESPONSE)
async def save_view(view: SavedViewIn, viewer: Viewer, db: DB) -> SavedViewOut:
    saved = SavedView(user_id=viewer.id, list=view.list, name=view.name.strip(), query=view.query)
    db.add(saved)
    try:
        await db.commit()
    except IntegrityError:
        # The live-row unique index on (user, list, name). Roll back so the session is usable again.
        await db.rollback()
        raise FieldError("You already have a view with that name.", field="name") from None
    return SavedViewOut.model_validate(saved)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(view_id: uuid.UUID, viewer: Viewer, db: DB) -> None:
    view = (
        await db.execute(select(SavedView).where(SavedView.id == view_id, SavedView.user_id == viewer.id))
    ).scalar_one_or_none()
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "View not found")  # also for someone else's
    view.deleted_at = datetime.now(UTC)
    await db.commit()
