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
from app.models import SavedView, User
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
]

# Endpoints that deliberately need no sign-in, and why.
PUBLIC = {
    ("GET", "/health"): "liveness check for the host; returns no data",
    ("GET", "/dev/users"): "the dev 'View as' list; 404 unless DEV_AUTH is on (test_access)",
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


async def test_public_endpoints_answer_without_sign_in(api: httpx.AsyncClient) -> None:
    for method, path in PUBLIC:
        assert (await api.request(method, path)).status_code == 200, path


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


def test_no_endpoint_hides_from_the_schema() -> None:
    """The guard reads the schema, so an endpoint left out of it (include_in_schema=False) would escape."""
    hidden = [p.name for p in Path(app_package.__file__).parent.rglob("*.py") if "include_in_schema" in p.read_text("utf-8")]
    assert hidden == [], "an endpoint hidden from the schema can't be checked by the access matrix"
