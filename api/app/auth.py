"""Who is asking. Every endpoint that returns data takes a `Viewer`; endpoints only ever see a User.

Two ways in:
- **A session** (`Authorization: Bearer <token>`), from signing in (routers/auth.py). The API stores only the
  token's SHA-256. A session ends at whichever comes first: its absolute lifetime, IDLE_TIMEOUT without a
  request, or revocation (sign out, password change or reset, deactivation).
- **The development "View as" header** (`X-Dev-User: <user id>`), accepted only when DEV_AUTH (local) or
  DEMO_MODE (the public demo, synthetic data) is on. A request that sends a Bearer token is judged by that
  token alone: a bad session never falls back to the header.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import Actor, set_actor
from app.config import settings
from app.db import get_db
from app.models import User, UserSession
from app.security import new_token, token_hash

DB = Annotated[AsyncSession, Depends(get_db)]

SESSION_LIFETIME = timedelta(hours=12)  # a workday: sign in each morning
IDLE_TIMEOUT = timedelta(hours=2)
TOUCH_EVERY = timedelta(minutes=5)  # how stale last_seen_at may get before a request refreshes it

_UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Not signed in", headers={"WWW-Authenticate": "Bearer"}
)


def _bearer(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _UNAUTHORIZED
    return token.strip()


async def start_session(db: AsyncSession, user: User, user_agent: str | None) -> tuple[str, UserSession]:
    """Create a session and return its token (the only time the token exists outside the person's cookie)."""
    now = datetime.now(UTC)
    token = new_token()
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash(token),
        expires_at=now + SESSION_LIFETIME,
        last_seen_at=now,
        user_agent=(user_agent or "")[:200],
    )
    db.add(session)
    return token, session


async def end_sessions(db: AsyncSession, user_id: uuid.UUID, *, keep: uuid.UUID | None = None) -> None:
    """Revoke every open session of this person (except `keep`, the one making the change)."""
    now = datetime.now(UTC)
    for s in (await db.execute(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None)))).scalars():
        if s.id != keep:
            s.revoked_at = now


async def current_session(db: DB, authorization: Annotated[str | None, Header()] = None) -> UserSession | None:
    """The live session behind this request's Bearer token, or None if it sent none."""
    token = _bearer(authorization)
    if token is None:
        return None
    now = datetime.now(UTC)
    session = (
        await db.execute(
            select(UserSession)
            .join(User, User.id == UserSession.user_id)
            .where(
                UserSession.token_hash == token_hash(token),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.last_seen_at > now - IDLE_TIMEOUT,
                User.active,
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise _UNAUTHORIZED
    if now - session.last_seen_at > TOUCH_EVERY:
        session.last_seen_at = now  # not an audit event (audit.IGNORED); saved with the request's commit, if any
        await db.commit()
    return session


async def get_viewer(
    db: DB,
    session: Annotated[UserSession | None, Depends(current_session)],
    x_dev_user: Annotated[uuid.UUID | None, Header()] = None,
) -> User:
    if session is not None:
        user = await db.get(User, session.user_id)
    elif settings.header_auth and x_dev_user is not None:
        user = (await db.execute(select(User).where(User.id == x_dev_user, User.active))).scalar_one_or_none()
    else:
        user = None
    if user is None:
        raise _UNAUTHORIZED
    set_actor(db, Actor.user(user.id))  # the audit trail records this person for what the request writes
    return user


Viewer = Annotated[User, Depends(get_viewer)]


def is_admin(user: User) -> bool:
    return user.role == "admin"
