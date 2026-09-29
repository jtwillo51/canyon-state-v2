"""Pipeline moves: who may move what where, and what each move records."""

from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

TODAY = agency_today()


async def move(api: httpx.AsyncClient, world: World, who: Any, status: str, **extra: Any) -> httpx.Response:
    body = {"status": status, **{k: str(v) for k, v in extra.items()}}
    return await api.post(f"/referrals/{world.tessas_referral.id}/status", json=body, headers=as_user(who))


def steps(referral: dict[str, Any]) -> dict[str, str]:
    return {s["step"]: s["rep"]["name"] for s in referral["steps"]}


# --- Forward moves by a rep ------------------------------------------------------------------------


async def test_rep_moves_forward_and_is_credited(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "contacted")
    assert r.status_code == 200
    assert r.json()["status"] == "contacted"
    assert steps(r.json()) == {"introduction": "Tessa Rep", "contact": "Tessa Rep"}


async def test_skipping_ahead_credits_every_step_passed(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "quoted", premium=1200)
    assert r.status_code == 200
    assert set(steps(r.json())) == {"introduction", "contact", "quote"}
    assert r.json()["premium"] == 1200


async def test_quoted_needs_a_premium(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "quoted")
    assert r.status_code == 422
    assert r.json()["field"] == "premium"


async def test_bound_needs_a_bind_date(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "bound", premium=900)
    assert (r.status_code, r.json()["field"]) == (422, "bound_date")


@pytest.mark.parametrize("offset", [timedelta(days=1), None])  # tomorrow, or before the referral
async def test_bind_date_must_be_real(api: httpx.AsyncClient, world: World, offset: timedelta | None) -> None:
    on = TODAY + offset if offset else world.tessas_referral.referred_date - timedelta(days=1)
    r = await move(api, world, world.tessa, "bound", premium=900, bound_date=on)
    assert (r.status_code, r.json()["field"]) == (422, "bound_date")


async def test_binding_records_date_premium_and_credit(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "bound", premium=900, bound_date=TODAY)
    body = r.json()
    assert (body["status"], body["premium"], body["bound_date"]) == ("bound", 900, TODAY.isoformat())
    assert {s["step"]: s["date"] for s in body["steps"]}["bind"] == TODAY.isoformat()


async def test_a_refused_move_changes_nothing(api: httpx.AsyncClient, world: World) -> None:
    await move(api, world, world.tessa, "bound", premium=900)  # no bind date: refused
    r = await api.get(f"/referrals/{world.tessas_referral.id}", headers=as_user(world.tessa))
    assert (r.json()["status"], r.json()["premium"]) == ("referred", None)


async def test_moving_to_the_same_status_is_refused(api: httpx.AsyncClient, world: World) -> None:
    assert (await move(api, world, world.tessa, "referred")).status_code == 422


# --- What reps may not do ------------------------------------------------------------------------------


async def test_rep_cannot_move_backward(api: httpx.AsyncClient, world: World) -> None:
    await move(api, world, world.tessa, "quoted", premium=1000)
    r = await move(api, world, world.tessa, "contacted")
    assert r.status_code == 422
    assert "admin" in r.json()["message"]


async def test_rep_can_mark_lost_but_not_reopen(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "lost")
    assert (r.json()["status"], r.json()["lost_date"]) == ("lost", TODAY.isoformat())
    assert (await move(api, world, world.tessa, "contacted")).status_code == 422


async def test_rep_cannot_credit_someone_else(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.tessa, "contacted", credit_rep_id=world.jordan.id)
    assert (r.status_code, r.json()["field"]) == (422, "credit_rep_id")


async def test_rep_cannot_move_someone_elses_referral(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.jordan, "contacted")
    assert r.status_code == 404


# --- Admins ------------------------------------------------------------------------------------------------


async def test_admin_must_name_the_rep_for_a_forward_move(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.dana, "contacted")
    assert (r.status_code, r.json()["field"]) == (422, "credit_rep_id")
    r = await move(api, world, world.dana, "contacted", credit_rep_id=world.jordan.id)
    assert steps(r.json())["contact"] == "Jordan Rep"


async def test_admin_cannot_credit_another_admin(api: httpx.AsyncClient, world: World) -> None:
    r = await move(api, world, world.dana, "contacted", credit_rep_id=world.dana.id)
    assert (r.status_code, r.json()["field"]) == (422, "credit_rep_id")


async def test_admin_moving_back_uncredits_later_steps(api: httpx.AsyncClient, world: World) -> None:
    await move(api, world, world.tessa, "bound", premium=900, bound_date=TODAY)
    r = await move(api, world, world.dana, "contacted")
    body = r.json()
    assert (body["status"], body["premium"], body["bound_date"]) == ("contacted", None, None)
    assert set(steps(body)) == {"introduction", "contact"}


async def test_admin_reopens_a_lost_referral_keeping_its_credits(api: httpx.AsyncClient, world: World) -> None:
    await move(api, world, world.tessa, "quoted", premium=1500)
    await move(api, world, world.tessa, "lost")
    r = await move(api, world, world.dana, "quoted")  # premium kept; no new steps, so no rep needed
    body = r.json()
    assert (body["status"], body["premium"], body["lost_date"]) == ("quoted", 1500, None)
    assert set(steps(body)) == {"introduction", "contact", "quote"}


# --- The board -----------------------------------------------------------------------------------------------


async def test_board_shows_open_and_recently_closed_only(
    api: httpx.AsyncClient, db: AsyncSession, world: World
) -> None:
    jordans = world.jordans_referral
    jordans.status, jordans.premium = "bound", 800
    jordans.referred_date, jordans.bound_date = TODAY - timedelta(days=90), TODAY - timedelta(days=60)
    await db.flush()
    names = [r["client_name"] for r in (await api.get("/referrals/pipeline", headers=as_user(world.dana))).json()]
    assert names == ["Client Tessa"]

    await move(api, world, world.tessa, "lost")  # lost today: still on the board
    names = [r["client_name"] for r in (await api.get("/referrals/pipeline", headers=as_user(world.dana))).json()]
    assert names == ["Client Tessa"]
