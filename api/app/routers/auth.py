"""Signing in and out, changing a password, and using a one-time setup or reset link.

Guessing is slowed two ways, both counted in login_attempts before any password is checked:
- per account: after ACCOUNT_LIMIT failures within ACCOUNT_WINDOW (since the last success), that email is paused
  until the oldest failure ages out. Made-up emails are counted exactly like real ones, so the pause itself
  reveals nothing about who has an account;
- across all accounts: after GLOBAL_LIMIT failures within GLOBAL_WINDOW, failed sign-ins pause for everyone.
  That's what stops "password spraying" (one common password tried against many accounts). The cost is that
  during an attack a real person may have to wait a few minutes.
Every refusal is the same message and takes about as long, whether the email exists or not.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func, select

from app.auth import DB, Viewer, current_session, end_sessions, start_session
from app.errors import FIELD_ERROR_RESPONSE, FieldError
from app.models import AccountLink, LoginAttempt, User, UserSession
from app.schemas import LinkInfo, LinkRedeem, LinkToken, Me, PasswordChange, SessionOut, SignIn
from app.security import email_key, hash_password, needs_rehash, password_problem, token_hash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

ACCOUNT_LIMIT, ACCOUNT_WINDOW = 5, timedelta(minutes=15)
GLOBAL_LIMIT, GLOBAL_WINDOW = 100, timedelta(minutes=5)

WRONG = "That email and password don't match. Check both and try again."
LINK_GONE = "This link has expired or has already been used. Ask an admin for a new one."

Session = Annotated[UserSession | None, Depends(current_session)]


def _paused(seconds: float) -> HTTPException:
    minutes = max(1, round(seconds / 60))
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"Too many attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
        headers={"Retry-After": str(int(seconds) + 1)},
    )


async def _check_limits(db: DB, key: str) -> None:
    now = datetime.now(UTC)
    recent = (
        await db.execute(
            select(LoginAttempt.attempted_at, LoginAttempt.succeeded)
            .where(LoginAttempt.email_key == key, LoginAttempt.attempted_at > now - ACCOUNT_WINDOW)
            .order_by(LoginAttempt.attempted_at.desc())
        )
    ).all()
    failures = []
    for at, ok in recent:  # failures since the last success in the window
        if ok:
            break
        failures.append(at)
    if len(failures) >= ACCOUNT_LIMIT:
        raise _paused((failures[ACCOUNT_LIMIT - 1] + ACCOUNT_WINDOW - now).total_seconds())

    everyone = await db.execute(
        select(func.count()).where(LoginAttempt.attempted_at > now - GLOBAL_WINDOW, LoginAttempt.succeeded.is_(False))
    )
    if everyone.scalar_one() >= GLOBAL_LIMIT:
        raise _paused(GLOBAL_WINDOW.total_seconds())


async def _record_attempt(db: DB, key: str, succeeded: bool) -> None:
    db.add(LoginAttempt(email_key=key, succeeded=succeeded))
    await db.commit()


@router.post("/sign-in", responses={401: {}, 429: {}})
async def sign_in(body: SignIn, db: DB, user_agent: Annotated[str | None, Header()] = None) -> SessionOut:
    key = email_key(body.email)
    await _check_limits(db, key)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower(), User.active))
    ).scalar_one_or_none()
    # Always verify, against a dummy hash if there's no such person (or no password yet), so timing is the same.
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        await _record_attempt(db, key, False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)

    if user.password_hash and needs_rehash(user.password_hash):  # stronger settings since it was set
        user.password_hash = hash_password(body.password)
    token, session = await start_session(db, user, user_agent)
    await _record_attempt(db, key, True)  # commits the session too
    return SessionOut(token=token, expires_at=session.expires_at, user=Me.model_validate(user))


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(viewer: Viewer, session: Session, db: DB) -> Response:
    if session is not None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sign-out-everywhere", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_everywhere(viewer: Viewer, db: DB) -> Response:
    await end_sessions(db, viewer.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, responses={**FIELD_ERROR_RESPONSE, 429: {}})
async def change_password(body: PasswordChange, viewer: Viewer, session: Session, db: DB) -> Response:
    """Change your own password. Needs a real session and the current password (which counts as a sign-in
    attempt, so this can't be used to guess it). Every other session of yours ends."""
    if session is None:
        raise FieldError("Sign in with your password to change it.", field="current_password")
    key = email_key(viewer.email)
    await _check_limits(db, key)
    if not verify_password(viewer.password_hash, body.current_password):
        await _record_attempt(db, key, False)
        raise FieldError("That isn't your current password.", field="current_password")
    if problem := password_problem(body.new_password, name=viewer.name, email=viewer.email):
        raise FieldError(problem, field="new_password")
    viewer.password_hash = hash_password(body.new_password)
    viewer.password_changed_at = datetime.now(UTC)
    await end_sessions(db, viewer.id, keep=session.id)
    await _record_attempt(db, key, True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _live_link(db: DB, token: str) -> AccountLink:
    link = (
        await db.execute(
            select(AccountLink)
            .join(User, User.id == AccountLink.user_id)
            .where(
                AccountLink.token_hash == token_hash(token),
                AccountLink.used_at.is_(None),
                AccountLink.voided_at.is_(None),
                AccountLink.expires_at > datetime.now(UTC),
                User.active,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, LINK_GONE)
    return link


@router.post("/links/check")
async def check_link(body: LinkToken, db: DB) -> LinkInfo:
    """Whether a setup or reset link still works, and whose it is (to greet them). The token travels in the
    body, never the URL, so it stays out of server logs."""
    link = await _live_link(db, body.token)
    user = await db.get(User, link.user_id)
    assert user is not None
    return LinkInfo(purpose=link.purpose, name=user.name)


@router.post("/links/redeem", responses=FIELD_ERROR_RESPONSE)
async def redeem_link(body: LinkRedeem, db: DB, user_agent: Annotated[str | None, Header()] = None) -> SessionOut:
    """Set a password through a one-time link, and sign in. Ends any other session the person had."""
    link = await _live_link(db, body.token)
    user = await db.get(User, link.user_id)
    assert user is not None
    if problem := password_problem(body.password, name=user.name, email=user.email):
        raise FieldError(problem, field="password")
    now = datetime.now(UTC)
    user.password_hash = hash_password(body.password)
    user.password_changed_at = now
    link.used_at = now
    await end_sessions(db, user.id)
    token, session = await start_session(db, user, user_agent)
    await db.commit()
    return SessionOut(token=token, expires_at=session.expires_at, user=Me.model_validate(user))
