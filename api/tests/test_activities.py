"""Logging activity on a referral: who can, what's checked, and what it never changes."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from app.models import Activity
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

TODAY = agency_today()


def entry(world: World, **overrides: Any) -> dict[str, Any]:
    body = {"rep_id": str(world.tessa.id), "date": TODAY.isoformat(), "method": "Phone", "notes": "Left a voicemail."}
    return {**body, **overrides}


async def log(api: httpx.AsyncClient, world: World, who: Any, body: dict[str, Any]) -> httpx.Response:
    return await api.post(f"/referrals/{world.tessas_referral.id}/activities", json=body, headers=as_user(who))


async def test_owner_logs_and_sees_activity(api: httpx.AsyncClient, world: World) -> None:
    r = await log(api, world, world.tessa, entry(world, notes="  Left a voicemail.  "))
    assert r.status_code == 201
    assert (r.json()["method"], r.json()["notes"]) == ("Phone", "Left a voicemail.")  # trimmed
    listed = (await api.get(f"/referrals/{world.tessas_referral.id}/activities", headers=as_user(world.tessa))).json()
    assert [a["notes"] for a in listed] == ["Left a voicemail."]


async def test_logging_for_a_colleague_records_both_people(api: httpx.AsyncClient, world: World) -> None:
    r = await log(api, world, world.dana, entry(world, rep_id=str(world.tessa.id)))
    assert (r.json()["rep"]["name"], r.json()["logged_by"]["name"]) == ("Tessa Rep", "Dana Admin")


async def test_someone_elses_referral_is_404_both_ways(api: httpx.AsyncClient, world: World) -> None:
    assert (await log(api, world, world.jordan, entry(world))).status_code == 404
    r = await api.get(f"/referrals/{world.tessas_referral.id}/activities", headers=as_user(world.jordan))
    assert r.status_code == 404


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"date": (TODAY + timedelta(days=1)).isoformat()}, "date"),  # future
        ({"date": "2020-01-01"}, "date"),  # before the referral
        ({"rep_id": "00000000-0000-4000-8000-000000000000"}, "rep_id"),  # nobody
    ],
)
async def test_rules_are_checked(api: httpx.AsyncClient, world: World, change: dict[str, str], field: str) -> None:
    r = await log(api, world, world.tessa, entry(world, **change))
    assert (r.status_code, r.json()["field"]) == (422, field)


@pytest.mark.parametrize("change", [{"method": "Carrier pigeon"}, {"notes": "x" * 2001}])
async def test_shape_is_checked(api: httpx.AsyncClient, world: World, change: dict[str, str]) -> None:
    assert (await log(api, world, world.tessa, entry(world, **change))).status_code == 422


async def test_activity_never_changes_steps_or_status(api: httpx.AsyncClient, world: World) -> None:
    await log(api, world, world.tessa, entry(world, method="In person"))
    r = (await api.get(f"/referrals/{world.tessas_referral.id}", headers=as_user(world.tessa))).json()
    assert r["status"] == "referred"
    assert [s["step"] for s in r["steps"]] == ["introduction"]


async def test_database_requires_exactly_one_parent(db: AsyncSession, world: World) -> None:
    """The CHECK constraint, not just the API, stops an activity pointing at nothing (or at two things)."""
    for parents in ({}, {"referral_id": world.tessas_referral.id, "partner_id": world.partner.id}):
        savepoint = await db.begin_nested()  # so the failure doesn't end the test's transaction
        db.add(Activity(rep_id=world.tessa.id, logged_by_id=world.tessa.id, method="Phone", date=TODAY, **parents))
        with pytest.raises(IntegrityError, match="ck_activities_one_parent"):
            await db.flush()
        await savepoint.rollback()
    assert (await db.execute(text("select count(*) from activities"))).scalar() == 0
