"""Who is asking. Every endpoint that returns data takes a `Viewer`.

For now the viewer comes from a development-only X-Dev-User header holding a user id. Real
sign-in (Stage 3) replaces get_viewer() and nothing else: endpoints only ever see a User.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Actor, set_actor
from app.config import settings
from app.db import get_db
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_viewer(
    db: DB,
    x_dev_user: Annotated[uuid.UUID | None, Header()] = None,
) -> User:
    if not settings.header_auth or x_dev_user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    user = (await db.execute(select(User).where(User.id == x_dev_user, User.active))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    set_actor(db, Actor.user(user.id))  # the audit trail records this person for what the request writes
    return user


Viewer = Annotated[User, Depends(get_viewer)]


def is_admin(user: User) -> bool:
    return user.role == "admin"
