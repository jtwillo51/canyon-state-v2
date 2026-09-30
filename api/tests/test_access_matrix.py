"""Who may call what: every endpoint, asked by four people, with the answer each should get.

Most tests prove a feature works. This file proves each endpoint works *only* for the people it should:
nobody signed in, the rep who owns the record, another rep, and an admin. The guard at the bottom reads the
app's route list and fails when an endpoint has no row here, so a new endpoint can't ship until someone has
decided who may use it.

Statuses only. What's *in* a response that everyone may call (a rep's progress hides colleagues' dollars, a
rep's lists count only their referrals) is pinned in test_access.py, test_lists.py and test_progress.py.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app as app_package
from app.clock import agency_today
from app.main import app
from app.models import Notification, SavedView, User
from app.security import hash_password
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

# The askers. "owner" is Tessa: credited on her referral and the partner's primary rep.
ACTORS = ("nobody", "owner", "other_rep", "admin")

Body = Callable[[World, str], dict[str, Any]]


@dataclass(frozen=True)
class Case:
    method: str
    path: str  # the route's own template, e.g. "/referrals/{referral_id}"
    expect: dict[str, int]  # actor -> status
    why: str
    body: Body | None = None
    params: dict[str, str] = field(default_factory=dict)


def everyone(ok: int = 200) -> dict[str, int]:
    """Any signed-in person; nobody else."""
    return {"nobody": 401, "owner": ok, "other_rep": ok, "admin": ok}


def admins_only(ok: int = 200) -> dict[str, int]:
    """Reps are refused with the API's field error (422), which the UI shows next to the field."""
    return {"nobody": 401, "owner": 422, "other_rep": 422, "admin": ok}


def admins_only_hidden(ok: int = 200) -> dict[str, int]:
    """An admin feature that doesn't exist for anyone else: a 404, not a refusal."""
    return {"nobody": 401, "owner": 404, "other_rep": 404, "admin": ok}


def owner_and_admins(ok: int = 200) -> dict[str, int]:
    """Someone else's referral is a 404, not a 403, so its existence isn't confirmed."""
    return {"nobody": 401, "owner": ok, "other_rep": 404, "admin": ok}


def just(body: dict[str, Any]) -> Body:
    return lambda world, actor: body


def status_move(world: World, actor: str) -> dict[str, Any]:
    # An admin moving a referral forward names the rep who did the work; a rep is credited themselves.
    return {"status": "contacted", "credit_rep_id": str(world.tessa.id)} if actor == "admin" else {"status": "contacted"}


def activity(world: World, actor: str) -> dict[str, Any]:
    return {"rep_id": str(world.tessa.id), "date": agency_today().isoformat(), "method": "Phone", "notes": "Called."}


CASES = [
    # --- Reference lists and the viewer -------------------------------------------------------------
    Case("GET", "/users/me", everyone(), "who the API thinks is asking"),
    Case("GET", "/users", everyone(), "the team, for 'who made contact'"),
    Case("GET", "/users/reps", everyone(), "the rep picker"),
    Case("GET", "/carriers", everyone(), "the carrier picker"),
    # --- Partners: shared by the whole team -----------------------------------------------------------
    Case("GET", "/partners", everyone(), "partners are shared; money inside is scoped (test_partner_list)"),
    Case("GET", "/partners/{partner_id}", everyone(), "partners are shared"),
    Case("GET", "/partners/{partner_id}/history", everyone(), "shared, and holds only the partner's own changes (test_audit)"),
    Case("PATCH", "/partners/{partner_id}", everyone(), "shared facts anyone may fix", body=just({"territory": "East Valley"})),
    Case(
        "PATCH", "/partners/{partner_id}", admins_only(), "only admins reassign the primary rep",
        body=lambda world, actor: {"primary_rep_id": str(world.jordan.id)},
    ),  # fmt: skip
    # --- Referrals: scoped to the reps credited on them ----------------------------------------------
    Case("GET", "/referrals", everyone(), "the list is scoped, not refused (test_access)"),
    Case("GET", "/referrals/pipeline", everyone(), "the board is scoped, not refused (test_access)"),
    Case("GET", "/referrals/{referral_id}", owner_and_admins(), "a referral belongs to its credited reps"),
    Case("PATCH", "/referrals/{referral_id}", owner_and_admins(), "edits before bind", body=just({"line_of_business": "Auto"})),
    Case("POST", "/referrals/{referral_id}/status", owner_and_admins(), "moving it on the board", body=status_move),
    Case("GET", "/referrals/{referral_id}/activities", owner_and_admins(), "its timeline"),
    Case("GET", "/referrals/{referral_id}/history", owner_and_admins(), "its change history, like the referral itself"),
    Case("POST", "/referrals/{referral_id}/activities", owner_and_admins(201), "logging a touch", body=activity),
    # --- Progress and goals -------------------------------------------------------------------------
    Case("GET", "/progress", everyone(), "scoped inside: a rep sees only their own numbers (test_progress)"),
    Case("PUT", "/goals/reps/{user_id}", admins_only(), "only admins set goals", body=just({"clients": 5, "sales": 9000})),
    Case("PUT", "/goals/company", admins_only(), "only admins set the close-rate target", body=just({"close_rate": "0.6"})),
    # --- Saved views: private to their owner, admins included ------------------------------------------
    Case("GET", "/views", everyone(), "each person lists only their own (test_lists)", params={"list": "referrals"}),
    Case("POST", "/views", everyone(201), "anyone saves their own", body=lambda world, actor: {"list": "referrals", "name": f"Mine {actor}", "query": "status=quoted"}),  # fmt: skip
    Case(
        "DELETE", "/views/{view_id}", {"nobody": 401, "owner": 204, "other_rep": 404, "admin": 404},
        "a view is private, even from admins",
    ),  # fmt: skip
    # --- Notifications: private to their recipient, admins included ---------------------------------------
    Case("GET", "/notifications", everyone(), "each person lists only their own (test_notifications)"),
    Case("POST", "/notifications/read-all", everyone(204), "marks only the caller's own"),
    Case(
        "POST", "/notifications/{notification_id}/read", {"nobody": 401, "owner": 204, "other_rep": 404, "admin": 404},
        "a notification is private, even from admins",
    ),  # fmt: skip

    # --- Signing in and out (see test_auth.py for the rules themselves) --------------------------------------
    Case("POST", "/auth/sign-out", everyone(204), "ends the caller's own session"),
    Case("POST", "/auth/sign-out-everywhere", everyone(204), "ends the caller's own sessions"),
    Case(
        "POST", "/auth/password", {"nobody": 401, "owner": 422, "other_rep": 422, "admin": 422},
        "needs a real password session (these askers use the dev header)",
        body=just({"current_password": "anything", "new_password": "anything"}),
    ),  # fmt: skip
    # --- Team: admins only, invisible to everyone else ------------------------------------------------------
    Case("GET", "/team", admins_only_hidden(), "the Team page"),
    Case(
        "POST", "/team", admins_only_hidden(201), "adding a person",
        body=lambda world, actor: {"name": "New Person", "email": f"new-{actor}@example.com", "role": "rep"},
    ),  # fmt: skip
    Case("POST", "/team/{user_id}/link", admins_only_hidden(201), "a setup or reset link"),
    Case("PATCH", "/team/{user_id}", admins_only_hidden(), "role and deactivation", body=just({"role": "rep"})),
]

# Endpoints that deliberately need no sign-in, and why.
PUBLIC = {
    ("GET", "/health"): "liveness check for the host; returns no data",
    ("GET", "/dev/users"): "the dev 'View as' list; 404 unless DEV_AUTH is on (test_access)",
    ("POST", "/auth/sign-in"): "signing in; rate-limited and uniform on failure (test_auth)",
    ("POST", "/auth/links/check"): "a one-time link's own 256-bit token is the credential (test_auth)",
    ("POST", "/auth/links/redeem"): "a one-time link's own 256-bit token is the credential (test_auth)",
}

TEST_PASSWORD = "purple tractor lemonade rain"

# How each public endpoint is shown to answer without a session: (body, expected status). Not 401 is the point.
PUBLIC_PROBES: dict[tuple[str, str], tuple[dict[str, Any] | None, int]] = {
    ("GET", "/health"): (None, 200),
    ("GET", "/dev/users"): (None, 200),
    ("POST", "/auth/sign-in"): ({"email": "tessa@example.test", "password": TEST_PASSWORD}, 200),
    ("POST", "/auth/links/check"): ({"token": "x" * 43}, 404),  # no such link: "expired or used", not "sign in"
    ("POST", "/auth/links/redeem"): ({"token": "x" * 43, "password": TEST_PASSWORD}, 404),
}


def who(world: World, actor: str) -> User | None:
    return {"nobody": None, "owner": world.tessa, "other_rep": world.jordan, "admin": world.dana}[actor]


async def fill(path: str, world: World, db: AsyncSession) -> str:
    """Put real ids into the route template. Every record belongs to Tessa, the owner."""
    ids: dict[str, Any] = {
        "partner_id": world.partner.id,
        "referral_id": world.tessas_referral.id,
        "user_id": world.tessa.id,
    }
    if "{notification_id}" in path:
        note = Notification(user_id=world.tessa.id, kind="weekly_digest", dedupe_key="digest:2026-09-21")
        db.add(note)
        await db.flush()
        ids["notification_id"] = note.id
    if "{view_id}" in path:
        view = SavedView(user_id=world.tessa.id, list="referrals", name="Tessa's quotes", query="status=quoted")
        db.add(view)
        await db.flush()
        ids["view_id"] = view.id
    return path.format(**ids)


@pytest.mark.parametrize(
    ("case", "actor"),
    [(c, a) for c in CASES for a in ACTORS],
    ids=[f"{c.method} {c.path} [{c.why}] as {a}" for c in CASES for a in ACTORS],
)
async def test_access(api: httpx.AsyncClient, db: AsyncSession, world: World, case: Case, actor: str) -> None:
    url = await fill(case.path, world, db)
    person = who(world, actor)
    r = await api.request(
        case.method,
        url,
        params=case.params,
        json=case.body(world, actor) if case.body else None,
        headers=as_user(person) if person else {},
    )
    assert r.status_code == case.expect[actor], f"{actor} got {r.status_code}: {r.text[:200]}"


async def test_public_endpoints_answer_without_sign_in(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    world.tessa.password_hash = hash_password(TEST_PASSWORD)
    await db.flush()
    assert set(PUBLIC_PROBES) == set(PUBLIC)
    for (method, path), (body, expected) in PUBLIC_PROBES.items():
        assert (await api.request(method, path, json=body)).status_code == expected, path


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def endpoints() -> set[tuple[str, str]]:
    """Every endpoint, read from the OpenAPI schema: FastAPI's public list of what the API serves (and
    what the TypeScript client is generated from). app.routes won't do: since FastAPI 0.14x it holds
    included routers as unexpanded wrappers."""
    paths = app.openapi()["paths"]
    return {(m.upper(), p) for p, ops in paths.items() for m in ops if m in HTTP_METHODS}


def test_every_endpoint_has_a_row() -> None:
    """The guard: adding an endpoint fails this test until it has a row in CASES (or a reason in PUBLIC)."""
    routes = endpoints()
    assert ("GET", "/referrals/{referral_id}") in routes, "the route list came back empty or incomplete"
    covered = {(c.method, c.path) for c in CASES} | set(PUBLIC)
    assert routes - covered == set(), "decide who may call these, then add them to CASES"
    assert covered - routes == set(), "these rows point at endpoints that no longer exist"
    assert all(set(c.expect) == set(ACTORS) for c in CASES), "every row answers for all four people"


# Endpoints deliberately left out of the schema, each reviewed, with where its security is tested instead.
REVIEWED_HIDDEN = {
    "jobs/endpoint.py": "Inngest's /api/inngest: exists only when configured, signed requests only (test_jobs.py)",
}


def test_no_endpoint_hides_from_the_schema() -> None:
    """The guard reads the schema, so an endpoint left out of it (include_in_schema=False) would escape."""
    root = Path(app_package.__file__).parent
    hidden = {p.relative_to(root).as_posix() for p in root.rglob("*.py") if "include_in_schema" in p.read_text("utf-8")}
    assert hidden == set(REVIEWED_HIDDEN), "an endpoint hidden from the schema can't be checked by the access matrix"
