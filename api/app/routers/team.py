"""The Team page: admins add people, hand out one-time setup and reset links, and deactivate accounts.

Admins only. For anyone else the whole feature is a 404: it doesn't exist for them, the same way someone
else's referral doesn't. Admins never see or choose a password: a new person (or one who forgot theirs) gets a
one-time link and sets it themselves. An admin can't deactivate or demote themselves, so the agency can't lock
itself out by accident.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import DB, Viewer, end_sessions, is_admin
from app.errors import FIELD_ERROR_RESPONSE, FieldError
from app.models import AccountLink, User, UserSession
from app.schemas import LinkOut, PersonCreated, PersonIn, PersonOut, PersonPatch
from app.security import new_token, token_hash

LINK_LIFETIME = timedelta(hours=48)


async def _admins_only(viewer: Viewer) -> None:
    """A router-level dependency, so it runs before the request body is validated: anyone else gets a plain 404
    whatever they send, never a validation error that would confirm the endpoint exists."""
    if not is_admin(viewer):
        raise HTTPException(status.HTTP_404_NOT_FOUND)


router = APIRouter(prefix="/team", tags=["team"], dependencies=[Depends(_admins_only)])


async def _person(db: DB, user: User) -> PersonOut:
    last = (
        await db.execute(select(func.max(UserSession.created_at)).where(UserSession.user_id == user.id))
    ).scalar_one()
    return PersonOut(
        id=user.id, name=user.name, email=user.email, role=user.role, active=user.active,
        has_password=user.password_hash is not None, last_sign_in_at=last,
    )  # fmt: skip


async def _new_link(db: DB, user: User, admin: User) -> LinkOut:
    """A fresh one-time link for this person; any earlier unused link of theirs stops working."""
    now = datetime.now(UTC)
    for old in (
        await db.execute(select(AccountLink).where(AccountLink.user_id == user.id, AccountLink.used_at.is_(None), AccountLink.voided_at.is_(None)))
    ).scalars():
        old.voided_at = now
    token = new_token()
    purpose = "reset" if user.password_hash else "setup"
    db.add(AccountLink(user_id=user.id, purpose=purpose, token_hash=token_hash(token),
                       expires_at=now + LINK_LIFETIME, created_by_id=admin.id))  # fmt: skip
    return LinkOut(token=token, purpose=purpose, expires_at=now + LINK_LIFETIME)


async def _get(db: DB, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user


@router.get("")
async def list_people(viewer: Viewer, db: DB) -> list[PersonOut]:
    users = (await db.execute(select(User).order_by(User.active.desc(), User.name))).scalars().all()
    return [await _person(db, u) for u in users]


@router.post("", status_code=status.HTTP_201_CREATED, responses=FIELD_ERROR_RESPONSE)
async def add_person(body: PersonIn, viewer: Viewer, db: DB) -> PersonCreated:
    user = User(name=body.name.strip(), email=body.email.strip().lower(), role=body.role)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise FieldError("Someone on the team already uses that email.", field="email") from None
    link = await _new_link(db, user, viewer)
    await db.commit()
    return PersonCreated(person=await _person(db, user), link=link)


@router.post("/{user_id}/link", status_code=status.HTTP_201_CREATED, responses=FIELD_ERROR_RESPONSE)
async def new_link(user_id: uuid.UUID, viewer: Viewer, db: DB) -> LinkOut:
    """A setup link (no password yet) or a reset link (forgotten password). The old password keeps working
    until the link is used; using it ends every session the person had."""
    user = await _get(db, user_id)
    if not user.active:
        raise FieldError("Reactivate this person first.", field="active")
    link = await _new_link(db, user, viewer)
    await db.commit()
    return link


@router.patch("/{user_id}", responses=FIELD_ERROR_RESPONSE)
async def update_person(user_id: uuid.UUID, body: PersonPatch, viewer: Viewer, db: DB) -> PersonOut:
    user = await _get(db, user_id)
    if user.id == viewer.id and ({"active", "role"} & body.model_fields_set):
        raise FieldError("You can't deactivate or demote yourself. Ask another admin.", field="active" if "active" in body.model_fields_set else "role")
    if "role" in body.model_fields_set and body.role is not None:
        user.role = body.role
    if "active" in body.model_fields_set and body.active is not None and body.active != user.active:
        user.active = body.active
        if not body.active:  # out now: every session ends and unused links stop working
            await end_sessions(db, user.id)
            now = datetime.now(UTC)
            for link in (await db.execute(select(AccountLink).where(AccountLink.user_id == user.id, AccountLink.used_at.is_(None), AccountLink.voided_at.is_(None)))).scalars():
                link.voided_at = now
    await db.commit()
    return await _person(db, user)
