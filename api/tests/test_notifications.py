"""GET /notifications: each person sees only their own, and a stale nudge shows only while it still applies
to them (they can still see the referral, and it's still stale in the same spell)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from app.jobs.digest import build_digest, store_digest
from app.jobs.stale import notify_stale
from app.models import Activity
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

TODAY = agency_today()  # the API reads the real clock; the world's referrals (2026-09-01) are stale by now


async def inbox(api: httpx.AsyncClient, who: Any) -> dict[str, Any]:
    r = await api.get("/notifications", headers=as_user(who))
    assert r.status_code == 200
    return r.json()


def stale_clients(body: dict[str, Any]) -> list[str]:
    return [n["stale"]["client_name"] for n in body["items"] if n["kind"] == "stale_referral"]


async def test_each_rep_sees_only_their_own_nudges(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await notify_stale(db, TODAY)
    tessa, jordan, dana = await inbox(api, world.tessa), await inbox(api, world.jordan), await inbox(api, world.dana)
    assert (stale_clients(tessa), stale_clients(jordan), stale_clients(dana)) == (["Client Tessa"], ["Client Jordan"], [])
    nudge = tessa["items"][0]["stale"]
    assert nudge["days_since_touch"] == (TODAY - date(2026, 9, 1)).days
    assert tessa["unread"] == 1


async def test_a_nudge_disappears_when_someone_acts(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await notify_stale(db, TODAY)
    db.add(Activity(referral_id=world.tessas_referral.id, rep_id=world.tessa.id, logged_by_id=world.tessa.id,
                    date=TODAY, method="Phone"))  # fmt: skip
    world.jordans_referral.status, world.jordans_referral.lost_date = "lost", TODAY
    await db.flush()
    assert stale_clients(await inbox(api, world.tessa)) == []  # touched today
    assert stale_clients(await inbox(api, world.jordan)) == []  # closed


async def test_a_nudge_never_outlives_access(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await notify_stale(db, TODAY)
    world.tessas_credit.deleted_at = datetime.now(UTC)  # Tessa is no longer credited on the referral
    await db.flush()
    body = await inbox(api, world.tessa)
    assert body["items"] == [] and "Client Tessa" not in str(body)  # not even the client's name


async def test_digests_are_listed_and_private(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await store_digest(db, world.tessa.id, await build_digest(db, world.tessa, TODAY))
    tessa = await inbox(api, world.tessa)
    assert [n["kind"] for n in tessa["items"]] == ["weekly_digest"]
    assert tessa["items"][0]["digest"]["company"] is None  # a rep's digest: her own numbers only
    assert (await inbox(api, world.jordan))["items"] == [] and (await inbox(api, world.dana))["items"] == []


async def test_nudges_come_before_digests(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await store_digest(db, world.tessa.id, await build_digest(db, world.tessa, TODAY - timedelta(days=7)))
    await notify_stale(db, TODAY)
    assert [n["kind"] for n in (await inbox(api, world.tessa))["items"]] == ["stale_referral", "weekly_digest"]


async def test_marking_read(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await notify_stale(db, TODAY)
    await store_digest(db, world.tessa.id, await build_digest(db, world.tessa, TODAY))
    tessa, jordan = as_user(world.tessa), as_user(world.jordan)
    first = (await inbox(api, world.tessa))["items"][0]["id"]
    assert (await api.post(f"/notifications/{first}/read", headers=jordan)).status_code == 404  # not his
    assert (await api.post(f"/notifications/{first}/read", headers=tessa)).status_code == 204
    assert (await inbox(api, world.tessa))["unread"] == 1
    assert (await api.post("/notifications/read-all", headers=jordan)).status_code == 204  # touches only his
    assert (await inbox(api, world.tessa))["unread"] == 1
    assert (await api.post("/notifications/read-all", headers=tessa)).status_code == 204
    assert (await inbox(api, world.tessa))["unread"] == 0


async def test_most_overdue_nudge_comes_first(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    from app.models import Referral, ReferralStepCredit

    older = Referral(partner_id=world.partner.id, client_name="Client Older", line_of_business="Auto",
                     carrier_id=world.tessas_referral.carrier_id, referred_date=date(2026, 8, 1))  # fmt: skip
    db.add(older)
    await db.flush()
    db.add(ReferralStepCredit(referral_id=older.id, step="introduction", rep_id=world.tessa.id, date=date(2026, 8, 1)))
    await db.flush()
    await notify_stale(db, TODAY)
    assert stale_clients(await inbox(api, world.tessa)) == ["Client Older", "Client Tessa"]
