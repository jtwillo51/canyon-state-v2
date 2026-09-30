"""Inline edits: who may change which partner and referral fields."""

from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from app.models import Carrier, User
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio


async def edit_partner(api: httpx.AsyncClient, world: World, who: User, **body: Any) -> httpx.Response:
    return await api.patch(f"/partners/{world.partner.id}", json=body, headers=as_user(who))


async def edit_referral(api: httpx.AsyncClient, world: World, who: User, **body: Any) -> httpx.Response:
    return await api.patch(f"/referrals/{world.tessas_referral.id}", json=body, headers=as_user(who))


# --- Partners ------------------------------------------------------------------------------------------------


async def test_any_rep_edits_shared_partner_facts(api: httpx.AsyncClient, world: World) -> None:
    r = await edit_partner(api, world, world.jordan, do_not_contact=True, territory=" West Valley ", sensitive_items="")
    assert r.status_code == 200
    assert (r.json()["do_not_contact"], r.json()["territory"], r.json()["sensitive_items"]) == (True, "West Valley", "")


async def test_fields_left_out_are_untouched(api: httpx.AsyncClient, world: World) -> None:
    r = await edit_partner(api, world, world.dana, territory="Scottsdale")
    assert r.json()["primary_rep"]["name"] == "Tessa Rep"  # not sent, so not unassigned
    assert r.json()["sensitive_items"] == "Avoid talking about the move."


async def test_only_admins_reassign_the_primary_rep(api: httpx.AsyncClient, world: World) -> None:
    r = await edit_partner(api, world, world.tessa, primary_rep_id=str(world.jordan.id))
    assert (r.status_code, r.json()["field"]) == (422, "primary_rep_id")
    r = await edit_partner(api, world, world.dana, primary_rep_id=str(world.jordan.id))
    assert r.json()["primary_rep"]["name"] == "Jordan Rep"
    r = await edit_partner(api, world, world.dana, primary_rep_id=None)  # explicit null unassigns
    assert r.json()["primary_rep"] is None


async def test_primary_rep_must_be_an_active_rep(api: httpx.AsyncClient, world: World) -> None:
    r = await edit_partner(api, world, world.dana, primary_rep_id=str(world.dana.id))  # an admin
    assert (r.status_code, r.json()["field"]) == (422, "primary_rep_id")


async def test_unknown_fields_are_refused(api: httpx.AsyncClient, world: World) -> None:
    assert (await edit_partner(api, world, world.dana, name="Renamed")).status_code == 422


# --- Referrals -----------------------------------------------------------------------------------------------


async def test_owner_fixes_line_and_carrier_before_bind(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    other = Carrier(name="Other Mutual")
    db.add(other)
    await db.flush()
    r = await edit_referral(api, world, world.tessa, line_of_business="Auto", carrier_id=str(other.id))
    assert (r.status_code, r.json()["line_of_business"], r.json()["carrier"]["name"]) == (200, "Auto", "Other Mutual")


async def test_premium_only_once_quoted(api: httpx.AsyncClient, world: World) -> None:
    r = await edit_referral(api, world, world.tessa, premium=900)  # still "referred"
    assert (r.status_code, r.json()["field"]) == (422, "premium")


async def test_quoted_premium_editable_by_owner(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    world.tessas_referral.status, world.tessas_referral.premium = "quoted", Decimal(900)
    await db.flush()
    r = await edit_referral(api, world, world.tessa, premium=950)
    assert r.json()["premium"] == 950


async def test_bound_referral_is_admin_only(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    ref = world.tessas_referral
    ref.status, ref.premium, ref.bound_date = "bound", Decimal(900), agency_today()
    await db.flush()
    r = await edit_referral(api, world, world.tessa, premium=5000)
    assert (r.status_code, r.json()["field"]) == (422, "premium")
    r = await edit_referral(api, world, world.dana, premium=950)
    assert r.json()["premium"] == 950


async def test_unknown_carrier_and_other_reps_referral(api: httpx.AsyncClient, world: World) -> None:
    r = await edit_referral(api, world, world.tessa, carrier_id="00000000-0000-4000-8000-000000000000")
    assert (r.status_code, r.json()["field"]) == (422, "carrier_id")
    assert (await edit_referral(api, world, world.jordan, line_of_business="Auto")).status_code == 404


async def test_schema_errors_use_the_same_shape(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    """FastAPI's own validation (premium must be > 0) answers with {message, field} like our rules do."""
    world.tessas_referral.status, world.tessas_referral.premium = "quoted", Decimal(900)
    await db.flush()
    r = await edit_referral(api, world, world.tessa, premium=0)
    body = r.json()
    assert (r.status_code, body["field"]) == (422, "premium")
    assert "greater than 0" in body["message"]
    assert body["detail"]  # FastAPI's standard list is still there


async def test_carriers_listed(api: httpx.AsyncClient, world: World) -> None:
    names = [c["name"] for c in (await api.get("/carriers", headers=as_user(world.tessa))).json()]
    assert names == ["Test Mutual"]
