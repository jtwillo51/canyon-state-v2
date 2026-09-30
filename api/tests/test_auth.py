"""Signing in: passwords, sessions, rate limits, one-time links and the Team page's safeguards."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import IDLE_TIMEOUT
from app.models import AccountLink, LoginAttempt, UserSession
from app.routers.auth import ACCOUNT_LIMIT, GLOBAL_LIMIT, WRONG
from app.security import email_key, hash_password, password_problem, token_hash, verify_password
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

GOOD = "purple tractor lemonade rain"
GOOD2 = "copper kettle midnight harbor"


async def with_password(db: AsyncSession, world: World, who: str = "tessa", password: str = GOOD) -> None:
    getattr(world, who).password_hash = hash_password(password)
    await db.flush()


async def sign_in(api: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await api.post("/auth/sign-in", json={"email": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Password rules (NIST SP 800-63B) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("password", "why"),
    [
        ("short one", "at least 15"),
        ("aaaaaaaaaaaaaaaaaaaa", "too few"),
        ("tessa loves long walks", "name or email"),
        ("Password1234567890!", "predictable"),
        ("WelcomeCanyonState2026", "predictable"),
        ("x" * 129, "at most"),
    ],
)
def test_weak_passwords_are_refused_with_a_reason(password: str, why: str) -> None:
    problem = password_problem(password, name="Tessa Rep", email="tessa@example.test")
    assert problem is not None and why in problem


def test_a_passphrase_is_fine() -> None:
    assert password_problem(GOOD, name="Tessa Rep", email="tessa@example.test") is None


def test_hashes_verify_and_nothing_verifies_without_one() -> None:
    h = hash_password(GOOD)
    assert h.startswith("$argon2id$") and verify_password(h, GOOD) and not verify_password(h, GOOD2)
    assert not verify_password(None, GOOD)


# --- Signing in ------------------------------------------------------------------------------------------------


async def test_signing_in_gives_a_session_that_works(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await with_password(db, world)
    r = await sign_in(api, "  TESSA@example.test ", GOOD)  # email is case- and space-insensitive
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["name"] == "Tessa Rep" and "password_hash" not in str(body)
    me = await api.get("/users/me", headers=bearer(body["token"]))
    assert me.json()["name"] == "Tessa Rep"


@pytest.mark.parametrize("case", ["wrong password", "unknown email", "no password yet", "deactivated"])
async def test_every_failure_looks_the_same(api: httpx.AsyncClient, db: AsyncSession, world: World, case: str) -> None:
    await with_password(db, world)
    email, password = "tessa@example.test", GOOD
    if case == "wrong password":
        password = GOOD2
    elif case == "unknown email":
        email = "nobody@example.test"
    elif case == "no password yet":
        email = "jordan@example.test"
    else:
        world.tessa.active = False
        await db.flush()
    r = await sign_in(api, email, password)
    assert (r.status_code, r.json()["detail"]) == (401, WRONG)


async def test_only_the_tokens_hash_is_stored(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await with_password(db, world)
    token = (await sign_in(api, "tessa@example.test", GOOD)).json()["token"]
    stored = (await db.execute(select(UserSession.token_hash))).scalars().all()
    assert stored == [token_hash(token)]
    dump = (await db.execute(text("SELECT string_agg(t::text, '') FROM (SELECT * FROM sessions) t"))).scalar_one()
    audit = (await db.execute(text("SELECT string_agg(changes::text, '') FROM audit_events"))).scalar_one()
    assert token not in dump and token not in audit and "argon2" not in audit


async def test_a_bad_session_never_falls_back_to_the_dev_header(api: httpx.AsyncClient, world: World) -> None:
    r = await api.get("/users/me", headers={**bearer("not-a-real-token-" * 3), **as_user(world.dana)})
    assert r.status_code == 401


# --- Rate limits -----------------------------------------------------------------------------------------------


async def test_an_account_pauses_after_repeated_failures(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await with_password(db, world)
    for _ in range(ACCOUNT_LIMIT):
        assert (await sign_in(api, "tessa@example.test", GOOD2)).status_code == 401
    paused = await sign_in(api, "tessa@example.test", GOOD)  # even the right password waits
    assert paused.status_code == 429 and int(paused.headers["Retry-After"]) > 0
    assert (await sign_in(api, "jordan@example.test", GOOD)).status_code == 401  # other accounts unaffected


async def test_made_up_emails_pause_the_same_way(api: httpx.AsyncClient) -> None:
    """So a pause never reveals which emails have accounts."""
    for _ in range(ACCOUNT_LIMIT):
        assert (await sign_in(api, "nobody@example.test", GOOD)).status_code == 401
    assert (await sign_in(api, "nobody@example.test", GOOD)).status_code == 429


async def test_a_success_resets_the_count(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await with_password(db, world)
    for _ in range(ACCOUNT_LIMIT - 1):
        await sign_in(api, "tessa@example.test", GOOD2)
    assert (await sign_in(api, "tessa@example.test", GOOD)).status_code == 200
    assert (await sign_in(api, "tessa@example.test", GOOD2)).status_code == 401  # counting from zero again


async def test_spraying_many_accounts_pauses_everyone(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    db.add_all([LoginAttempt(email_key=email_key(f"victim{i}@example.test"), succeeded=False) for i in range(GLOBAL_LIMIT)])
    await db.flush()
    assert (await sign_in(api, "someone-new@example.test", GOOD)).status_code == 429


async def test_attempts_store_no_email_addresses(api: httpx.AsyncClient, db: AsyncSession) -> None:
    await sign_in(api, "tessa@example.test", GOOD2)
    keys = (await db.execute(select(LoginAttempt.email_key))).scalars().all()
    assert keys == [email_key("tessa@example.test")] and "@" not in keys[0]


# --- Session lifetime ------------------------------------------------------------------------------------------


async def signed_in(api: httpx.AsyncClient, db: AsyncSession, world: World) -> str:
    await with_password(db, world)
    return (await sign_in(api, "tessa@example.test", GOOD)).json()["token"]


async def test_signing_out_ends_the_session(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    token = await signed_in(api, db, world)
    assert (await api.post("/auth/sign-out", headers=bearer(token))).status_code == 204
    assert (await api.get("/users/me", headers=bearer(token))).status_code == 401


@pytest.mark.parametrize("how", ["expired", "idle"])
async def test_old_sessions_stop_working(api: httpx.AsyncClient, db: AsyncSession, world: World, how: str) -> None:
    token = await signed_in(api, db, world)
    session = (await db.execute(select(UserSession))).scalar_one()
    now = datetime.now(UTC)
    if how == "expired":
        session.expires_at = now - timedelta(seconds=1)
    else:
        session.last_seen_at = now - IDLE_TIMEOUT - timedelta(seconds=1)
    await db.flush()
    assert (await api.get("/users/me", headers=bearer(token))).status_code == 401


async def test_sign_out_everywhere(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    first = await signed_in(api, db, world)
    second = (await sign_in(api, "tessa@example.test", GOOD)).json()["token"]
    assert (await api.post("/auth/sign-out-everywhere", headers=bearer(second))).status_code == 204
    for token in (first, second):
        assert (await api.get("/users/me", headers=bearer(token))).status_code == 401


async def test_deactivation_ends_sessions_at_once(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    token = await signed_in(api, db, world)
    r = await api.patch(f"/team/{world.tessa.id}", json={"active": False}, headers=as_user(world.dana))
    assert r.status_code == 200
    assert (await api.get("/users/me", headers=bearer(token))).status_code == 401


# --- Changing a password ---------------------------------------------------------------------------------------


async def test_changing_a_password(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    other = await signed_in(api, db, world)
    token = (await sign_in(api, "tessa@example.test", GOOD)).json()["token"]
    wrong = await api.post("/auth/password", json={"current_password": GOOD2, "new_password": GOOD2}, headers=bearer(token))
    assert (wrong.status_code, wrong.json()["field"]) == (422, "current_password")
    weak = await api.post("/auth/password", json={"current_password": GOOD, "new_password": "short"}, headers=bearer(token))
    assert (weak.status_code, weak.json()["field"]) == (422, "new_password")
    ok = await api.post("/auth/password", json={"current_password": GOOD, "new_password": GOOD2}, headers=bearer(token))
    assert ok.status_code == 204
    assert (await api.get("/users/me", headers=bearer(token))).status_code == 200  # this session stays
    assert (await api.get("/users/me", headers=bearer(other))).status_code == 401  # every other one ends
    assert (await sign_in(api, "tessa@example.test", GOOD2)).status_code == 200


# --- One-time links and the Team page ----------------------------------------------------------------------------


async def add_person(api: httpx.AsyncClient, world: World, email: str = "new.rep@example.com") -> dict[str, Any]:
    r = await api.post("/team", json={"name": "New Rep", "email": email, "role": "rep"}, headers=as_user(world.dana))
    assert r.status_code == 201
    return r.json()


async def test_a_new_person_sets_their_own_password(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    created = await add_person(api, world)
    token = created["link"]["token"]
    assert created["link"]["purpose"] == "setup" and created["person"]["has_password"] is False
    assert (await api.post("/auth/links/check", json={"token": token})).json() == {"purpose": "setup", "name": "New Rep"}
    weak = await api.post("/auth/links/redeem", json={"token": token, "password": "new rep password!"})
    assert (weak.status_code, weak.json()["field"]) == (422, "password")  # contains their name
    done = await api.post("/auth/links/redeem", json={"token": token, "password": GOOD})
    assert done.status_code == 200 and done.json()["user"]["name"] == "New Rep"
    again = await api.post("/auth/links/redeem", json={"token": token, "password": GOOD2})
    assert again.status_code == 404  # one time only
    assert (await sign_in(api, "new.rep@example.com", GOOD)).status_code == 200
    stored = (await db.execute(select(AccountLink.token_hash))).scalars().all()
    assert token not in stored and token_hash(token) in stored


async def test_a_new_link_voids_the_old_one(api: httpx.AsyncClient, world: World) -> None:
    first = (await add_person(api, world))["link"]["token"]
    person = (await api.get("/team", headers=as_user(world.dana))).json()
    new_id = next(p["id"] for p in person if p["name"] == "New Rep")
    second = (await api.post(f"/team/{new_id}/link", headers=as_user(world.dana))).json()["token"]
    assert (await api.post("/auth/links/check", json={"token": first})).status_code == 404
    assert (await api.post("/auth/links/check", json={"token": second})).status_code == 200


async def test_expired_links_stop_working(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    token = (await add_person(api, world))["link"]["token"]
    link = (await db.execute(select(AccountLink))).scalar_one()
    link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.flush()
    assert (await api.post("/auth/links/check", json={"token": token})).status_code == 404


async def test_a_reset_link_ends_old_sessions(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    old = await signed_in(api, db, world)
    link = (await api.post(f"/team/{world.tessa.id}/link", headers=as_user(world.dana))).json()
    assert link["purpose"] == "reset"
    assert (await sign_in(api, "tessa@example.test", GOOD)).status_code == 200  # works until the link is used
    assert (await api.post("/auth/links/redeem", json={"token": link["token"], "password": GOOD2})).status_code == 200
    assert (await api.get("/users/me", headers=bearer(old))).status_code == 401
    assert (await sign_in(api, "tessa@example.test", GOOD)).status_code == 401


async def test_team_is_invisible_to_reps_whatever_they_send(api: httpx.AsyncClient, world: World) -> None:
    """A 404 before the body is even read: a validation error would confirm the endpoint exists."""
    r = await api.post("/team", json={"email": "not an email"}, headers=as_user(world.tessa))
    assert r.status_code == 404


async def test_admins_cannot_lock_themselves_out(api: httpx.AsyncClient, world: World) -> None:
    for change in ({"active": False}, {"role": "rep"}):
        r = await api.patch(f"/team/{world.dana.id}", json=change, headers=as_user(world.dana))
        assert r.status_code == 422


async def test_emails_are_unique_on_the_team(api: httpx.AsyncClient, world: World) -> None:
    await add_person(api, world, "dup@example.com")
    r = await api.post("/team", json={"name": "Dup", "email": "DUP@example.com", "role": "rep"}, headers=as_user(world.dana))
    assert (r.status_code, r.json()["field"]) == (422, "email")


async def test_the_team_list_never_includes_secrets(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await with_password(db, world)
    people = (await api.get("/team", headers=as_user(world.dana))).json()
    assert "argon2" not in str(people) and "password_hash" not in str(people)
    assert next(p for p in people if p["name"] == "Tessa Rep")["has_password"] is True
    assert (await db.execute(select(func.count()).select_from(UserSession))).scalar_one() == 0
