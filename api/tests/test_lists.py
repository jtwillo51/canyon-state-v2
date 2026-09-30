"""The referral list's filters, sort and paging, and saved views."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from app.models import Activity, Referral, ReferralStepCredit
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

TODAY = agency_today()


async def add_referral(db: AsyncSession, world: World, client: str, **fields: Any) -> Referral:
    """A referral for Tessa (credited on introduction) with any fields overridden."""
    values: dict[str, Any] = {
        "partner_id": world.partner.id,
        "client_name": client,
        "line_of_business": "Auto",
        "carrier_id": world.tessas_referral.carrier_id,
        "referred_date": TODAY - timedelta(days=5),
        **fields,
    }
    r = Referral(**values)
    db.add(r)
    await db.flush()
    db.add(ReferralStepCredit(referral_id=r.id, step="introduction", rep_id=world.tessa.id, date=r.referred_date))
    await db.flush()
    return r


async def names(api: httpx.AsyncClient, who: Any, **params: Any) -> list[str]:
    r = await api.get("/referrals", params=params, headers=as_user(who))
    assert r.status_code == 200, r.text
    return [x["client_name"] for x in r.json()["items"]]


# --- Filters -------------------------------------------------------------------------------------------


async def test_status_and_line_filters(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await add_referral(db, world, "Quoted Home", status="quoted", premium=Decimal(900), line_of_business="Home")
    await add_referral(db, world, "Quoted Auto", status="quoted", premium=Decimal(700))
    assert await names(api, world.dana, status=["quoted"], line=["Home"]) == ["Quoted Home"]
    assert sorted(await names(api, world.dana, status=["quoted", "referred"])) == [
        "Client Jordan", "Client Tessa", "Quoted Auto", "Quoted Home",
    ]  # fmt: skip


async def test_stale_uses_the_last_touch(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    old = TODAY - timedelta(days=60)
    await add_referral(db, world, "Quiet", referred_date=old)
    touched = await add_referral(db, world, "Called last week", referred_date=old)
    db.add(Activity(referral_id=touched.id, rep_id=world.tessa.id, logged_by_id=world.tessa.id, method="Phone", date=TODAY - timedelta(days=7)))  # fmt: skip
    await add_referral(db, world, "Lost long ago", referred_date=old, status="lost", lost_date=old)
    await db.flush()
    # The fixture referrals are from 2026-09-01: stale too if that's 30+ days back.
    stale = await names(api, world.dana, stale_days=30)
    assert "Quiet" in stale
    assert "Called last week" not in stale  # the activity counts as a touch
    assert "Lost long ago" not in stale  # stale only applies to open referrals


async def test_last_touch_is_returned(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    r = await add_referral(db, world, "Touched", referred_date=TODAY - timedelta(days=20))
    db.add(Activity(referral_id=r.id, rep_id=world.tessa.id, logged_by_id=world.tessa.id, method="Email", date=TODAY - timedelta(days=3)))  # fmt: skip
    await db.flush()
    body = (await api.get(f"/referrals/{r.id}", headers=as_user(world.tessa))).json()
    assert body["last_touch"] == (TODAY - timedelta(days=3)).isoformat()


async def test_bound_range_and_premium_filters(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await add_referral(db, world, "Bound now", status="bound", premium=Decimal(1000), bound_date=TODAY)
    await add_referral(db, world, "Lost at quote", status="lost", premium=Decimal(500), lost_date=TODAY)
    await add_referral(db, world, "Lost early", status="lost", lost_date=TODAY)
    assert await names(api, world.dana, bound_from=TODAY.replace(day=1).isoformat(), bound_to=TODAY.isoformat()) == ["Bound now"]  # fmt: skip
    assert await names(api, world.dana, status=["lost"], has_premium=True) == ["Lost at quote"]


async def test_search_is_literal(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await add_referral(db, world, "Ana 50% Off")
    await add_referral(db, world, "Ana 500")
    assert await names(api, world.dana, q="50%") == ["Ana 50% Off"]  # % is a character, not a wildcard
    assert await names(api, world.dana, q="client tes") == ["Client Tessa"]  # case-insensitive


async def test_filters_never_widen_scoping(api: httpx.AsyncClient, world: World) -> None:
    # Tessa asking for Jordan's referrals gets nothing, not Jordan's.
    assert await names(api, world.tessa, rep_id=str(world.jordan.id)) == []
    assert await names(api, world.dana, rep_id=str(world.jordan.id)) == ["Client Jordan"]


async def test_total_is_scoped_too(api: httpx.AsyncClient, world: World) -> None:
    """A rep mustn't learn how many referrals exist agency-wide from the page total."""
    assert (await api.get("/referrals", headers=as_user(world.tessa))).json()["total"] == 1
    assert (await api.get("/referrals", headers=as_user(world.dana))).json()["total"] == 2


async def test_unknown_parameters_are_refused(api: httpx.AsyncClient, world: World) -> None:
    r = await api.get("/referrals", params={"sort": "password"}, headers=as_user(world.dana))
    assert r.status_code == 422
    r = await api.get("/referrals", params={"statuss": "quoted"}, headers=as_user(world.dana))
    assert r.status_code == 422


# --- Sort and paging --------------------------------------------------------------------------------------


async def test_sort_by_premium_puts_unquoted_last(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await add_referral(db, world, "Small", status="quoted", premium=Decimal(100))
    await add_referral(db, world, "Big", status="quoted", premium=Decimal(900))
    ordered = await names(api, world.dana, sort="-premium")
    assert ordered[:2] == ["Big", "Small"]
    ordered = await names(api, world.dana, sort="premium")
    assert ordered[:2] == ["Small", "Big"]  # nulls last both ways


async def test_paging_reports_the_total(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    for i in range(5):
        await add_referral(db, world, f"Extra {i}")
    r = (await api.get("/referrals", params={"limit": 3, "offset": 3, "sort": "client_name"}, headers=as_user(world.dana))).json()  # fmt: skip
    assert (r["total"], r["limit"], r["offset"], len(r["items"])) == (7, 3, 3, 3)


async def test_total_ignores_soft_deleted(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    world.jordans_referral.deleted_at = datetime.now(UTC)
    await db.flush()
    r = (await api.get("/referrals", headers=as_user(world.dana))).json()
    assert (r["total"], [x["client_name"] for x in r["items"]]) == (1, ["Client Tessa"])


# --- Saved views --------------------------------------------------------------------------------------------


async def save(api: httpx.AsyncClient, who: Any, name: str, query: str = "status=quoted") -> httpx.Response:
    return await api.post("/views", json={"list": "referrals", "name": name, "query": query}, headers=as_user(who))


async def test_views_are_private(api: httpx.AsyncClient, world: World) -> None:
    assert (await save(api, world.tessa, "My quotes")).status_code == 201
    mine = (await api.get("/views", params={"list": "referrals"}, headers=as_user(world.tessa))).json()
    theirs = (await api.get("/views", params={"list": "referrals"}, headers=as_user(world.jordan))).json()
    assert ([v["name"] for v in mine], theirs) == (["My quotes"], [])
    assert (await api.delete(f"/views/{mine[0]['id']}", headers=as_user(world.jordan))).status_code == 404


async def test_view_names_are_unique_per_person_until_deleted(api: httpx.AsyncClient, world: World) -> None:
    # Headers up front: the refused duplicate rolls the (shared, test-only) session back, which expires
    # the fixture objects, and async SQLAlchemy won't silently reload an expired attribute.
    tessa, jordan = as_user(world.tessa), as_user(world.jordan)
    body = {"list": "referrals", "name": "Quotes", "query": "status=quoted"}

    first = (await api.post("/views", json=body, headers=tessa)).json()
    dup = await api.post("/views", json=body, headers=tessa)
    assert (dup.status_code, dup.json()["field"]) == (422, "name")
    assert (await api.post("/views", json=body, headers=jordan)).status_code == 201  # someone else may use it
    assert (await api.delete(f"/views/{first['id']}", headers=tessa)).status_code == 204
    assert (await api.post("/views", json=body, headers=tessa)).status_code == 201  # free again after delete


@pytest.mark.parametrize("query", ["javascript:alert(1)", "a=<script>", "x" * 1001])
async def test_view_query_must_be_a_plain_query_string(api: httpx.AsyncClient, world: World, query: str) -> None:
    assert (await save(api, world.tessa, "Bad", query)).status_code == 422
