"""Monthly progress: attribution, comparisons, goals, and what a rep may see."""

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from app.models import Referral, ReferralStepCredit, User
from app.progress import month_windows, others_average
from tests.conftest import World, as_user

TODAY = agency_today()
(START, END), (PREV_START, PREV_END) = month_windows(TODAY)


# --- Pure helpers --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "this_month", "last_month"),
    [
        (date(2026, 9, 12), (date(2026, 9, 1), date(2026, 9, 12)), (date(2026, 8, 1), date(2026, 8, 12))),
        (date(2026, 3, 31), (date(2026, 3, 1), date(2026, 3, 31)), (date(2026, 2, 1), date(2026, 2, 28))),
        (date(2028, 3, 31), (date(2028, 3, 1), date(2028, 3, 31)), (date(2028, 2, 1), date(2028, 2, 29))),  # leap
        (date(2026, 1, 15), (date(2026, 1, 1), date(2026, 1, 15)), (date(2025, 12, 1), date(2025, 12, 15))),
    ],
)
def test_month_windows_compare_the_same_span(today: date, this_month: tuple, last_month: tuple) -> None:
    assert month_windows(today) == (this_month, last_month)


def test_others_average_excludes_the_rep_and_missing_values() -> None:
    a, b, c = "a", "b", "c"
    assert others_average({a: 10, b: 4, c: None}, a) == 4  # c has no value yet; a is excluded
    assert others_average({a: 10}, a) is None


# --- The endpoint --------------------------------------------------------------------------------------------

async def bound(db: AsyncSession, world: World, *, intro: User, binder: User, premium: int, on: date) -> None:
    """A referral introduced by one rep and bound by another on `on`."""
    r = Referral(partner_id=world.partner.id, client_name="C", line_of_business="Home",
                 carrier_id=world.tessas_referral.carrier_id, referred_date=PREV_START,
                 status="bound", premium=Decimal(premium), bound_date=on)  # fmt: skip
    db.add(r)
    await db.flush()
    db.add_all([
        ReferralStepCredit(referral_id=r.id, step="introduction", rep_id=intro.id, date=PREV_START),
        ReferralStepCredit(referral_id=r.id, step="bind", rep_id=binder.id, date=on),
    ])  # fmt: skip
    await db.flush()


async def lost(db: AsyncSession, world: World, *, intro: User, on: date) -> None:
    r = Referral(partner_id=world.partner.id, client_name="L", line_of_business="Home",
                 carrier_id=world.tessas_referral.carrier_id, referred_date=PREV_START, status="lost", lost_date=on)  # fmt: skip
    db.add(r)
    await db.flush()
    db.add(ReferralStepCredit(referral_id=r.id, step="introduction", rep_id=intro.id, date=PREV_START))
    await db.flush()


async def get(api: httpx.AsyncClient, who: User) -> dict[str, Any]:
    r = await api.get("/progress", headers=as_user(who))
    assert r.status_code == 200, r.text
    return r.json()


def row(body: dict[str, Any], name: str) -> dict[str, Any]:
    return next(x for x in body["reps"] if x["rep"]["name"] == name)


@pytest.fixture
async def month(db: AsyncSession, world: World) -> None:
    """This month: Jordan binds 2 ($1,000 + $3,000), one introduced by Tessa. Tessa introduced one that
    was lost. Last month (same span): Jordan bound 1 ($500)."""
    await bound(db, world, intro=world.tessa, binder=world.jordan, premium=1000, on=START)
    await bound(db, world, intro=world.jordan, binder=world.jordan, premium=3000, on=END)
    await lost(db, world, intro=world.tessa, on=START)
    await bound(db, world, intro=world.jordan, binder=world.jordan, premium=500, on=PREV_START)


@pytest.mark.anyio
async def test_attribution_bind_for_sales_intro_for_close_rate(api: httpx.AsyncClient, world: World, month: None) -> None:
    body = await get(api, world.dana)
    jordan, tessa = row(body, "Jordan Rep"), row(body, "Tessa Rep")
    assert (jordan["clients"]["value"], jordan["sales"]["value"]) == (2, 4000)  # he bound both
    assert (tessa["clients"]["value"], tessa["sales"]["value"]) == (0, 0)
    # Tessa introduced 2 decided referrals: 1 bound, 1 lost. Jordan introduced 1, bound.
    assert (tessa["close_rate"]["value"], jordan["close_rate"]["value"]) == (0.5, 1.0)


@pytest.mark.anyio
async def test_company_totals_and_last_month(api: httpx.AsyncClient, world: World, month: None) -> None:
    c = (await get(api, world.dana))["company"]
    assert (c["clients"]["value"], c["sales"]["value"]) == (2, 4000)
    assert (c["clients"]["vs_last_month"], c["sales"]["vs_last_month"]) == (1, 3500)
    assert c["close_rate"]["value"] == pytest.approx(2 / 3)


@pytest.mark.anyio
async def test_vs_team_compares_with_the_other_reps(api: httpx.AsyncClient, world: World, month: None) -> None:
    jordan = row(await get(api, world.dana), "Jordan Rep")
    # Only one other rep (Tessa, $0 and 0 clients): Jordan is 2 clients and $4,000 above her.
    assert (jordan["clients"]["vs_team"], jordan["sales"]["vs_team"]) == (2, 4000)
    assert jordan["close_rate"]["vs_team"] == pytest.approx(0.5)
    assert jordan["clients"]["vs_last_month"] == 1


@pytest.mark.anyio
async def test_rep_sees_only_themselves_and_company_as_share(
    api: httpx.AsyncClient, db: AsyncSession, world: World, month: None
) -> None:
    await api.put(f"/goals/reps/{world.jordan.id}", json={"clients": 4, "sales": 8000}, headers=as_user(world.dana))
    await api.put(f"/goals/reps/{world.tessa.id}", json={"clients": 4, "sales": 2000}, headers=as_user(world.dana))
    body = await get(api, world.tessa)
    assert body["company"] is None
    assert [r["rep"]["name"] for r in body["reps"]] == ["Tessa Rep"]
    share = body["company_share"]
    assert (share["clients_pct_of_goal"], share["sales_pct_of_goal"]) == (0.25, 0.4)  # 2/8, $4,000/$10,000
    mine = body["reps"][0]
    assert mine["sales"]["vs_team"] is None  # would reveal colleagues' dollars
    assert mine["sales"]["vs_team_pct"] == -1.0  # $0 vs Jordan's $4,000: 100% below


@pytest.mark.anyio
async def test_goals_are_admin_only_and_update_in_place(api: httpx.AsyncClient, world: World) -> None:
    r = await api.put(f"/goals/reps/{world.tessa.id}", json={"clients": 5, "sales": 9000}, headers=as_user(world.tessa))
    assert (r.status_code, r.json()["message"]) == (422, "Only an admin can change goals.")
    for clients in (5, 7):  # second call updates, doesn't duplicate (the unique index would refuse)
        r = await api.put(f"/goals/reps/{world.tessa.id}", json={"clients": clients, "sales": 9000}, headers=as_user(world.dana))
        assert r.status_code == 200
    assert row(await get(api, world.dana), "Tessa Rep")["clients"]["goal"] == 7
    for rate in ("0.6", "0.65"):
        assert (await api.put("/goals/company", json={"close_rate": rate}, headers=as_user(world.dana))).status_code == 200
    assert (await get(api, world.dana))["company"]["close_rate"]["goal"] == 0.65
    assert (await api.put("/goals/company", json={"close_rate": "1.5"}, headers=as_user(world.dana))).status_code == 422
