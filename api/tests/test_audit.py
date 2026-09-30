"""The audit trail: every change recorded with who made it, sensitive values never copied, nothing able to
skip it, the log itself append-only, and each history readable only by those who can see the record."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

import app as app_package
from app import audit
from app.jobs.stale import notify_stale
from app.models import AuditEvent, Base, Notification, Referral, SavedView
from tests.conftest import World, as_user

pytestmark = pytest.mark.anyio


async def events(db: AsyncSession, entity: str, **where: Any) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.entity == entity, *(getattr(AuditEvent, k) == v for k, v in where.items()))
    return list((await db.execute(stmt.order_by(AuditEvent.occurred_at, AuditEvent.id))).scalars())


# --- Coverage ----------------------------------------------------------------------------------------------


def test_every_table_is_audited() -> None:
    """A new table is audited automatically; this fails only if the rule itself is changed."""
    assert audit.AUDITED == set(Base.metadata.tables) - {"audit_events"}


def test_redaction_and_subject_rules_name_real_columns() -> None:
    for table, fields in audit.REDACTED.items():
        assert fields <= set(Base.metadata.tables[table].c.keys()), table  # a typo would silently log the value
    assert set(audit.SUBJECTS) <= audit.AUDITED


def test_app_code_never_writes_with_raw_sql() -> None:
    """Raw SQL writes would skip the trail; app/ uses the ORM (or audited_insert) for every write."""
    raw_write = re.compile(r"text\(\s*[\"'](?:\s*)(INSERT|UPDATE|DELETE|TRUNCATE)\b", re.IGNORECASE)
    root = Path(app_package.__file__).parent
    offenders = [p.name for p in root.rglob("*.py") if raw_write.search(p.read_text("utf-8"))]
    assert offenders == []


# --- What gets recorded -----------------------------------------------------------------------------------


async def test_an_edit_records_who_and_what(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    r = await api.patch(f"/referrals/{world.tessas_referral.id}", json={"line_of_business": "Auto"}, headers=as_user(world.tessa))
    assert r.status_code == 200
    [e] = await events(db, "referrals", action="update")
    assert (e.actor_kind, e.actor_id, e.referral_id) == ("user", world.tessa.id, world.tessas_referral.id)
    assert e.changes == {"line_of_business": {"from": "Home", "to": "Auto"}}


async def test_sensitive_values_are_never_copied(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    secret = "Going through a divorce, avoid the topic"
    r = await api.patch(f"/partners/{world.partner.id}", json={"sensitive_items": secret}, headers=as_user(world.dana))
    assert r.status_code == 200
    [e] = await events(db, "partners", action="update")
    assert e.changes == {"sensitive_items": {"redacted": True}}
    # Nor anywhere else in the log: the client's details written by the fixture are redacted too.
    everything = json.dumps([x.changes for x in (await db.execute(select(AuditEvent))).scalars()])
    for value in (secret, "Avoid talking about the move.", "100 Test St, Mesa, AZ", "Client Tessa", "1980-05-01"):
        assert value not in everything


async def test_a_pipeline_move_records_the_status_and_the_credit(
    api: httpx.AsyncClient, db: AsyncSession, world: World
) -> None:
    r = await api.post(f"/referrals/{world.tessas_referral.id}/status", json={"status": "contacted"}, headers=as_user(world.tessa))
    assert r.status_code == 200
    [move] = await events(db, "referrals", action="update")
    assert move.changes["status"] == {"from": "referred", "to": "contacted"}
    credits = await events(db, "referral_steps", action="insert", actor_id=world.tessa.id)
    assert [c.changes["step"]["to"] for c in credits] == ["contact"]
    assert all(c.referral_id == world.tessas_referral.id for c in credits)  # part of the referral's history


async def test_a_refused_change_leaves_no_record(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    r = await api.post(f"/referrals/{world.tessas_referral.id}/status", json={"status": "quoted"}, headers=as_user(world.tessa))
    assert r.status_code == 422  # quoting needs a premium
    assert await events(db, "referrals", action="update") == []


async def test_soft_delete_is_recorded_as_a_delete(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    body = {"list": "referrals", "name": "Mine", "query": "status=quoted"}
    view_id = (await api.post("/views", json=body, headers=as_user(world.tessa))).json()["id"]
    assert (await api.delete(f"/views/{view_id}", headers=as_user(world.tessa))).status_code == 204
    actions = [e.action for e in await events(db, "saved_views", actor_id=world.tessa.id)]
    assert actions == ["insert", "delete"]


async def test_jobs_are_recorded_under_their_name(db: AsyncSession, world: World) -> None:
    audit.set_actor(db, audit.Actor.job("stale-referrals"))
    await notify_stale(db, date(2026, 10, 5))
    written = await events(db, "notifications", action="insert")
    assert len(written) == 2 and {(e.actor_kind, e.actor_label) for e in written} == {("job", "stale-referrals")}
    assert written[0].changes["data"] == {"redacted": True}  # digests hold everyone's numbers; never copied


async def test_marking_read_is_recorded(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await notify_stale(db, date(2026, 10, 5))
    assert (await api.post("/notifications/read-all", headers=as_user(world.tessa))).status_code == 204
    [e] = await events(db, "notifications", action="update")
    assert e.actor_id == world.tessa.id and set(e.changes) == {"read_at"}


async def test_the_seed_can_turn_recording_off(db: AsyncSession, world: World) -> None:
    audit.disable(db, "seed")
    db.add(SavedView(user_id=world.tessa.id, list="referrals", name="Seeded", query=""))
    await db.flush()
    assert await events(db, "saved_views") == []


# --- Nothing can skip it, and nothing can change it ------------------------------------------------------------


async def test_bulk_statements_on_audited_tables_are_refused(db: AsyncSession, world: World) -> None:
    with pytest.raises(RuntimeError, match="skip the audit trail"):
        await db.execute(update(Referral).values(status="lost"))
    with pytest.raises(RuntimeError, match="skip the audit trail"):
        await db.execute(update(Notification).values(read_at=None))


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_events SET action = 'insert'", "DELETE FROM audit_events", "TRUNCATE audit_events"],
)
async def test_the_log_is_append_only(db: AsyncSession, world: World, statement: str) -> None:
    assert await events(db, "referrals")  # the fixture's inserts were recorded
    with pytest.raises(DBAPIError, match="append-only"):
        async with db.begin_nested():  # a savepoint, so the test's transaction survives the refusal
            await db.execute(text(statement))


async def test_only_the_seed_setting_allows_a_reset(db: AsyncSession, world: World) -> None:
    async with db.begin_nested():
        await db.execute(text("SET LOCAL canyon.allow_audit_reset = 'on'"))
        await db.execute(text("TRUNCATE audit_events"))
    assert (await db.execute(select(AuditEvent))).first() is None


# --- Reading history ----------------------------------------------------------------------------------------


async def test_a_referral_history_names_people_and_carriers(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await api.patch(f"/referrals/{world.tessas_referral.id}", json={"line_of_business": "Auto"}, headers=as_user(world.tessa))
    r = await api.get(f"/referrals/{world.tessas_referral.id}/history", headers=as_user(world.tessa))
    assert r.status_code == 200
    newest, *older = r.json()
    assert (newest["actor"]["name"], newest["action"], newest["changes"]) == (
        "Tessa Rep", "update",
        [{"field": "line_of_business", "redacted": False, "before": "Home", "after": "Auto",
          "before_label": None, "after_label": None}],
    )  # fmt: skip
    created = next(e for e in older if e["entity"] == "referrals" and e["action"] == "insert")
    assert created["actor"] is None  # the fixture wrote it: "system"
    carrier = next(c for c in created["changes"] if c["field"] == "carrier_id")
    assert carrier["after_label"] == "Test Mutual"
    assert next(c for c in created["changes"] if c["field"] == "client_name")["redacted"] is True
    credit = next(e for e in older if e["entity"] == "referral_steps")
    assert next(c for c in credit["changes"] if c["field"] == "rep_id")["after_label"] == "Tessa Rep"


async def test_a_partner_history_never_shows_its_referrals(api: httpx.AsyncClient, db: AsyncSession, world: World) -> None:
    await api.patch(f"/partners/{world.partner.id}", json={"territory": "East Valley"}, headers=as_user(world.jordan))
    await api.patch(f"/referrals/{world.tessas_referral.id}", json={"line_of_business": "Auto"}, headers=as_user(world.tessa))
    history = (await api.get(f"/partners/{world.partner.id}/history", headers=as_user(world.jordan))).json()
    assert {e["entity"] for e in history} == {"partners"}  # not Tessa's referral, not its credits
    assert history[0]["actor"]["name"] == "Jordan Rep"
