"""The audit trail: who changed what, and when, recorded automatically for every table.

How it works
- **Capture** is a SQLAlchemy `after_flush` hook: every insert, update and soft delete of an audited row made
  through the ORM becomes an AuditEvent in the same transaction, so a change and its record commit or roll
  back together. Endpoints don't call anything, so none can forget.
- **Bulk statements** (`session.execute(update(...))`, `insert(...)`) don't pass through that hook, so they're
  refused on audited tables (`_refuse_bypass`) unless they come through `audited_insert`, which records what
  it wrote. Raw SQL writes aren't used in app/ at all (a test checks).
- **Who**: the Actor stored on the session: the signed-in person (set in auth.get_viewer), a job, a script,
  or "system" when nothing more specific applies.
- **Sensitive values are never copied** into the log: for fields in REDACTED the event records that the field
  changed, not what it held (the log shouldn't become a second store of personal data).
- **Append-only**: a database trigger refuses UPDATE and DELETE on audit_events, and TRUNCATE unless the seed
  script opts in (migration "audit_events").
"""

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Column, event, inspect, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ORMExecuteState, Session

from app.models import AuditEvent, Base


@dataclass(frozen=True)
class Actor:
    kind: str  # models.ActorKind
    user_id: uuid.UUID | None = None
    label: str | None = None

    @classmethod
    def user(cls, user_id: uuid.UUID) -> "Actor":
        return cls("user", user_id=user_id)

    @classmethod
    def job(cls, name: str) -> "Actor":
        return cls("job", label=name)

    @classmethod
    def script(cls, name: str) -> "Actor":
        return cls("script", label=name)


SYSTEM = Actor("system")
_ACTOR = "audit_actor"
_OFF = "audit_off"


def set_actor(session: AsyncSession | Session, actor: Actor) -> None:
    session.info[_ACTOR] = actor


def disable(session: AsyncSession | Session, reason: str) -> None:
    """Stop recording for this session. Only the seed script does this (it rebuilds everything from scratch)."""
    session.info[_OFF] = reason


# --- What's audited, and how ------------------------------------------------------------------------------

# Tables not audited, each with its reason. Everything else is, including tables added later.
EXCLUDED = {
    AuditEvent.__tablename__: "the log itself",
    "login_attempts": "a security log of its own: every row is already a record of an attempt",
}
AUDITED = frozenset(t for t in Base.metadata.tables if t not in EXCLUDED)

# Values never copied into the log: personal data and free text that may hold it.
REDACTED: dict[str, frozenset[str]] = {
    "referrals": frozenset({"client_name", "client_address", "client_birthday", "sensitive_items"}),
    "partners": frozenset({"phone", "email", "sensitive_items"}),
    "users": frozenset({"email", "password_hash"}),
    "sessions": frozenset({"token_hash"}),
    "account_links": frozenset({"token_hash"}),
    "activities": frozenset({"notes"}),
    "notifications": frozenset({"data"}),  # an admin's digest holds every rep's numbers
}

# Timestamps are the event's own occurred_at; ids are the event's entity_id.
_SKIP = frozenset({"id", "created_at", "updated_at"})

# Bookkeeping that changes constantly and means nothing on its own: a change to only these isn't an event.
IGNORED: dict[str, frozenset[str]] = {"sessions": frozenset({"last_seen_at"})}

Getter = Callable[[str], Any]

# Whose history an event belongs to: (referral_id, partner_id). A partner's history is its own changes only,
# never its referrals' (partners are shared; their referrals aren't).
SUBJECTS: dict[str, Callable[[Getter], tuple[Any, Any]]] = {
    "referrals": lambda get: (get("id"), None),
    "referral_steps": lambda get: (get("referral_id"), None),
    "activities": lambda get: (get("referral_id"), get("partner_id")),
    "partners": lambda get: (None, get("id")),
    "partner_production": lambda get: (None, get("partner_id")),
}


def _json(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    return value


def _change(table: str, field: str, old: Any, new: Any) -> dict[str, Any]:
    return {"redacted": True} if field in REDACTED.get(table, ()) else {"from": _json(old), "to": _json(new)}


def _event(actor: Actor, action: str, table: str, get: Getter, changes: dict[str, Any]) -> dict[str, Any]:
    referral_id, partner_id = SUBJECTS.get(table, lambda _: (None, None))(get)
    return {
        "actor_kind": actor.kind,
        "actor_id": actor.user_id,
        "actor_label": actor.label,
        "action": action,
        "entity": table,
        "entity_id": get("id"),
        "referral_id": referral_id,
        "partner_id": partner_id,
        "changes": changes,
    }


def _column_changes(obj: Any, table: str, inserting: bool) -> dict[str, Any]:
    """Field by field: for an insert, every value the app set; for an update, only what changed."""
    state = inspect(obj)
    out: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        if attr.key in _SKIP or attr.key in IGNORED.get(table, ()) or not isinstance(attr.columns[0], Column):
            continue  # (the Column check skips computed attributes such as last_touch)
        history = state.attrs[attr.key].history
        if not history.added and not (not inserting and history.deleted):
            continue
        old = None if inserting or not history.deleted else history.deleted[0]
        new = history.added[0] if history.added else None
        if inserting and new is None:
            continue
        out[attr.key] = _change(table, attr.key, old, new)
    return out


@event.listens_for(Session, "after_flush")
def _record(session: Session, _flush_context: Any) -> None:
    """Runs inside every flush. The session still shows what's being flushed (new, dirty, deleted) with each
    attribute's before/after history, and the rows now have their ids."""
    if session.info.get(_OFF):
        return
    actor: Actor = session.info.get(_ACTOR, SYSTEM)
    events: list[dict[str, Any]] = []

    for obj in session.new:
        table = obj.__table__.name
        if table in AUDITED:
            events.append(_event(actor, "insert", table, lambda k, o=obj: getattr(o, k), _column_changes(obj, table, True)))

    for obj in session.dirty:
        table = obj.__table__.name
        if table not in AUDITED or not session.is_modified(obj, include_collections=False):
            continue
        changes = _column_changes(obj, table, False)
        if not changes:
            continue
        action = "update"
        if "deleted_at" in changes:  # soft delete is how things are removed here, so name it
            action = "delete" if changes["deleted_at"]["to"] else "restore"
        events.append(_event(actor, action, table, lambda k, o=obj: getattr(o, k), changes))

    for obj in session.deleted:  # hard deletes shouldn't happen (soft delete everywhere), but never unrecorded
        table = obj.__table__.name
        if table in AUDITED:
            events.append(_event(actor, "delete", table, lambda k, o=obj: getattr(o, k), {}))

    if events:
        session.connection().execute(insert(AuditEvent.__table__), events)


@event.listens_for(Session, "do_orm_execute")
def _refuse_bypass(state: ORMExecuteState) -> None:
    """Bulk INSERT/UPDATE/DELETE statements skip the flush hook, so they may not touch audited tables unless
    they come through audited_insert (which records what it wrote)."""
    if not (state.is_insert or state.is_update or state.is_delete) or state.execution_options.get("audited"):
        return
    table = getattr(state.statement, "table", None)
    if table is not None and table.name in AUDITED:
        raise RuntimeError(
            f"Bulk {state.statement.__visit_name__} on audited table {table.name!r} would skip the audit trail. "
            "Change ORM objects instead, or use audit.audited_insert."
        )


async def audited_insert(
    session: AsyncSession,
    model: type[Base],
    values: Sequence[Mapping[str, Any]],
    *,
    skip_duplicates_on: Sequence[str],
    where: Any = None,
) -> list[Mapping[str, Any]]:
    """INSERT ... ON CONFLICT DO NOTHING for many rows at once, recording an event for each row written.
    Returns the rows actually inserted (duplicates are skipped by the database, and not recorded)."""
    if not values:
        return []
    table = model.__table__
    stmt = (
        pg_insert(model)
        .values(list(values))
        .on_conflict_do_nothing(index_elements=list(skip_duplicates_on), index_where=where)
        .returning(*table.c)
    )
    rows = (await session.execute(stmt, execution_options={"audited": True})).mappings().all()
    if rows and not session.info.get(_OFF):
        actor: Actor = session.info.get(_ACTOR, SYSTEM)
        events = [
            _event(actor, "insert", table.name, row.get,
                   {k: _change(table.name, k, None, v) for k, v in row.items() if k not in _SKIP and v is not None})
            for row in rows
        ]  # fmt: skip
        await session.execute(insert(AuditEvent.__table__), events)
    return list(rows)
