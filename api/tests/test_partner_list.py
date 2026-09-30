"""The Partners list: referral numbers per partner, and who may see which numbers."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import agency_today
from app.models import Partner, Referral, ReferralStepCredit, User
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio

TODAY = agency_today()


async def referral(db: AsyncSession, world: World, partner: Partner, rep: User, **fields: Any) -> None:
    r = Referral(
        partner_id=partner.id,
        client_name="Client",
        line_of_business="Home",
        carrier_id=world.tessas_referral.carrier_id,
        referred_date=fields.pop("referred_date", TODAY - timedelta(days=10)),
        **fields,
    )
    db.add(r)
    await db.flush()
    db.add(ReferralStepCredit(referral_id=r.id, step="introduction", rep_id=rep.id, date=r.referred_date))
    await db.flush()


async def rows(api: httpx.AsyncClient, who: User, **params: Any) -> dict[str, dict[str, Any]]:
    r = await api.get("/partners", params=params, headers=as_user(who))
    assert r.status_code == 200, r.text
    return {p["name"]: p["stats"] for p in r.json()["items"]}


@pytest.fixture
async def busy(db: AsyncSession, world: World) -> Partner:
    """A second partner: 4 referrals in the last year (2 bound: $1,000 Tessa's, $3,000 Jordan's), 1 older."""
    p = Partner(name="Busy Partner", type="Loan officer")
    db.add(p)
    await db.flush()
    await referral(db, world, p, world.tessa, status="bound", premium=Decimal(1000), bound_date=TODAY)
    await referral(db, world, p, world.jordan, status="bound", premium=Decimal(3000), bound_date=TODAY)
    await referral(db, world, p, world.jordan)
    await referral(db, world, p, world.tessa, status="quoted", premium=Decimal(500))
    await referral(db, world, p, world.tessa, referred_date=TODAY - timedelta(days=500))
    return p


async def test_admin_sees_counts_rate_and_all_premium(api: httpx.AsyncClient, world: World, busy: Partner) -> None:
    s = (await rows(api, world.dana))["Busy Partner"]
    assert (s["referrals"], s["bound"], s["close_rate"], s["bound_premium"]) == (4, 2, 0.5, 4000)
    assert s["last_referred"] == (TODAY - timedelta(days=10)).isoformat()


async def test_rep_sees_team_counts_but_only_their_own_premium(
    api: httpx.AsyncClient, world: World, busy: Partner
) -> None:
    s = (await rows(api, world.tessa))["Busy Partner"]
    assert (s["referrals"], s["bound"]) == (4, 2)  # team-wide, as in v1
    assert s["bound_premium"] == 1000  # only the bound referral Tessa is credited on


async def test_period_changes_the_window(api: httpx.AsyncClient, world: World, busy: Partner) -> None:
    assert (await rows(api, world.dana, period="all"))["Busy Partner"]["referrals"] == 5


async def test_partner_without_referrals_still_listed(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    db.add(Partner(name="Quiet Partner", type="Realtor"))
    await db.flush()
    s = (await rows(api, world.dana))["Quiet Partner"]
    assert (s["referrals"], s["bound"], s["close_rate"], s["bound_premium"]) == (0, 0, None, 0)
    assert list(await rows(api, world.dana, no_referrals=True)) == ["Quiet Partner"]


async def test_sort_by_close_rate_puts_no_referrals_last(
    api: httpx.AsyncClient, db: AsyncSession, world: World, busy: Partner
) -> None:
    db.add(Partner(name="Quiet Partner", type="Realtor"))
    await db.flush()
    # Pat Partner: 2 referrals, none bound (0.0). Busy: 0.5. Quiet: none (null) -> last both ways.
    assert list(await rows(api, world.dana, sort="-close_rate")) == ["Busy Partner", "Pat Partner", "Quiet Partner"]
    assert list(await rows(api, world.dana, sort="close_rate")) == ["Pat Partner", "Busy Partner", "Quiet Partner"]


async def test_filters(api: httpx.AsyncClient, world: World, busy: Partner) -> None:
    assert list(await rows(api, world.dana, type=["Loan officer"])) == ["Busy Partner"]
    assert list(await rows(api, world.dana, unassigned=True)) == ["Busy Partner"]
    assert list(await rows(api, world.dana, primary_rep_id=str(world.tessa.id))) == ["Pat Partner"]
    assert list(await rows(api, world.dana, q="busy")) == ["Busy Partner"]
    page = (await api.get("/partners", params={"limit": 1}, headers=as_user(world.dana))).json()
    assert (page["total"], len(page["items"])) == (2, 1)
