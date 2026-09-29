"""Who can see what. These are the rules a data leak would come from."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio


# --- Signing in ---------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/partners", "/referrals"])
async def test_no_viewer_is_401(api: httpx.AsyncClient, path: str) -> None:
    assert (await api.get(path)).status_code == 401


async def test_unknown_user_is_401(api: httpx.AsyncClient) -> None:
    r = await api.get("/partners", headers={"X-Dev-User": "00000000-0000-4000-8000-000000000000"})
    assert r.status_code == 401


async def test_inactive_user_is_401(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    world.tessa.active = False
    await db.flush()
    assert (await api.get("/partners", headers=as_user(world.tessa))).status_code == 401


async def test_dev_header_ignored_when_dev_auth_off(
    api: httpx.AsyncClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "dev_auth", False)
    assert (await api.get("/partners", headers=as_user(world.dana))).status_code == 401


async def test_dev_user_list_only_with_dev_auth(
    api: httpx.AsyncClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = [u["name"] for u in (await api.get("/dev/users")).json()]
    assert names == ["Dana Admin", "Jordan Rep", "Tessa Rep"]  # admins first, then by name
    monkeypatch.setattr(settings, "dev_auth", False)
    assert (await api.get("/dev/users")).status_code == 404


# --- Partners: shared -----------------------------------------------------------------------------


async def test_every_rep_sees_every_partner_with_do_not_discuss(api: httpx.AsyncClient, world: World) -> None:
    for rep in (world.tessa, world.jordan):
        partners = (await api.get("/partners", headers=as_user(rep))).json()
        assert [p["name"] for p in partners] == ["Pat Partner"]
        # Shared on purpose, so nobody raises the topic.
        assert partners[0]["sensitive_items"] == "Avoid talking about the move."


# --- Referrals: scoped ----------------------------------------------------------------------------


async def test_admin_sees_all_referrals(api: httpx.AsyncClient, world: World) -> None:
    referrals = (await api.get("/referrals", headers=as_user(world.dana))).json()
    assert {r["client_name"] for r in referrals} == {"Client Tessa", "Client Jordan"}


async def test_rep_sees_only_referrals_they_are_credited_on(api: httpx.AsyncClient, world: World) -> None:
    referrals = (await api.get("/referrals", headers=as_user(world.tessa))).json()
    assert [r["client_name"] for r in referrals] == ["Client Tessa"]


async def test_rep_gets_404_for_someone_elses_referral(api: httpx.AsyncClient, world: World) -> None:
    r = await api.get(f"/referrals/{world.jordans_referral.id}", headers=as_user(world.tessa))
    assert r.status_code == 404


async def test_partner_filter_keeps_scoping(api: httpx.AsyncClient, world: World) -> None:
    r = await api.get("/referrals", params={"partner_id": str(world.partner.id)}, headers=as_user(world.jordan))
    assert [x["client_name"] for x in r.json()] == ["Client Jordan"]


async def test_owner_sees_blocked_fields_unmasked(api: httpx.AsyncClient, world: World) -> None:
    r = (await api.get(f"/referrals/{world.tessas_referral.id}", headers=as_user(world.tessa))).json()
    assert r["client_address"] == "100 Test St, Mesa, AZ"
    assert r["client_birthday"] == "1980-05-01"


# --- Soft delete ----------------------------------------------------------------------------------


async def test_soft_deleted_credit_revokes_access(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    world.tessas_credit.deleted_at = datetime.now(UTC)
    await db.flush()
    assert (await api.get("/referrals", headers=as_user(world.tessa))).json() == []
    r = await api.get(f"/referrals/{world.tessas_referral.id}", headers=as_user(world.tessa))
    assert r.status_code == 404


async def test_soft_deleted_partner_disappears(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    world.partner.deleted_at = datetime.now(UTC)
    await db.flush()
    assert (await api.get("/partners", headers=as_user(world.dana))).json() == []
    assert (await api.get(f"/partners/{world.partner.id}", headers=as_user(world.dana))).status_code == 404
