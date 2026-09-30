"""Database tables (SQLAlchemy). API shapes live separately in app/schemas.py.

Fields mirror v1's src/types/index.ts. Fixed value lists are text columns guarded by CHECK
constraints; the lists themselves are the Literal types below, shared with the schemas.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, get_args

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column, relationship

Role = Literal["admin", "rep"]
PartnerType = Literal["Loan officer", "Realtor", "Financial advisor", "Other"]
ReferralStatus = Literal["referred", "contacted", "quoted", "bound", "lost"]
LineOfBusiness = Literal["Auto", "Home", "Umbrella", "Life", "Commercial"]
ReferralStep = Literal["introduction", "contact", "quote", "bind"]
# How a rep reached someone: the agency's own form uses these three.
ContactMethod = Literal["In person", "Phone", "Email"]
# Lists that can have saved views.
ListName = Literal["referrals", "partners"]
# What the scheduled jobs (app/jobs/) tell people about.
NotificationKind = Literal["stale_referral", "weekly_digest"]
# The audit trail (app/audit.py): what happened, and who (or what) did it.
AuditAction = Literal["insert", "update", "delete", "restore"]
ActorKind = Literal["user", "job", "script", "system"]
# One-time account links: a new person sets their first password, or anyone resets a forgotten one.
LinkPurpose = Literal["setup", "reset"]


def one_of(column: str, values: type) -> str:
    """SQL for a CHECK constraint limiting a text column to a Literal's values."""
    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in get_args(values))
    return f"{column} IN ({quoted})"


# Soft-deleted rows don't count toward uniqueness: see live_unique().
LIVE = text("deleted_at IS NULL")


def live_unique(table: str, *columns: str) -> Index:
    """A unique index over live (not soft-deleted) rows only.

    A plain UNIQUE constraint would count deleted rows too, so fixing a mistake by soft-deleting
    a row and re-entering it would fail.
    """
    return Index(f"uq_{table}_{'_'.join(columns)}_live", *columns, unique=True, postgresql_where=LIVE)


class Base(DeclarativeBase):
    # Every datetime is timestamptz: an absolute moment, not a wall-clock reading with no zone.
    type_annotation_map = {datetime: DateTime(timezone=True)}

    # Predictable constraint names, so Alembic migrations can find them to alter or drop.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class SoftDelete:
    """Soft delete: set deleted_at instead of removing the row.

    app/db.py filters deleted rows out of every query automatically. This is a plain mixin, not
    a mapped class, so that filter can refer to SoftDelete.deleted_at.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


class Record(SoftDelete):
    """Columns every table has: a UUID key, timestamps and (from SoftDelete) deleted_at.

    A plain mixin, like SoftDelete: tables are declared as `class X(Record, Base)`.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class User(Record, Base):
    """A rep or an admin."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(one_of("role", Role), name="role"),
        # Case-insensitive, and among live rows only, so a deleted user's email can be reused.
        Index("uq_users_email_live", func.lower(text("email")), unique=True, postgresql_where=LIVE),
    )

    name: Mapped[str]
    email: Mapped[str]
    role: Mapped[str]
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    # Argon2id (app/security.py). NULL until the person sets one through their setup link.
    password_hash: Mapped[str | None]
    password_changed_at: Mapped[datetime | None]


class Partner(Record, Base):
    """A referral partner. Shared across all reps; personal notes live on visits (later)."""

    __tablename__ = "partners"
    __table_args__ = (CheckConstraint(one_of("type", PartnerType), name="type"),)

    name: Mapped[str]
    type: Mapped[str]
    type_other: Mapped[str | None]
    business_name: Mapped[str] = mapped_column(server_default="")
    phone: Mapped[str] = mapped_column(server_default="")
    email: Mapped[str] = mapped_column(server_default="")
    territory: Mapped[str] = mapped_column(server_default="")
    # The rep who owns the relationship. Doesn't change who can see the partner.
    primary_rep_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    do_not_contact: Mapped[bool] = mapped_column(server_default=text("false"))
    # "Do not discuss": what nobody should bring up with this partner. Never sent to the AI.
    sensitive_items: Mapped[str] = mapped_column(server_default="")

    primary_rep: Mapped[User | None] = relationship()
    production: Mapped[list["PartnerProduction"]] = relationship(
        back_populates="partner", order_by="PartnerProduction.year"
    )
    referrals: Mapped[list["Referral"]] = relationship(back_populates="partner")


class PartnerProduction(Record, Base):
    """Dollar volume a partner personally closed in a year."""

    __tablename__ = "partner_production"
    __table_args__ = (live_unique("partner_production", "partner_id", "year"),)

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"))
    year: Mapped[int]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    verified: Mapped[bool] = mapped_column(server_default=text("false"))

    partner: Mapped[Partner] = relationship(back_populates="production")


class Carrier(Record, Base):
    __tablename__ = "carriers"

    name: Mapped[str]


class Referral(Record, Base):
    """A client a partner sent us, and how far it got."""

    __tablename__ = "referrals"
    __table_args__ = (
        CheckConstraint(one_of("status", ReferralStatus), name="status"),
        CheckConstraint(one_of("line_of_business", LineOfBusiness), name="line_of_business"),
    )

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    client_name: Mapped[str]
    # Client PII: blocked for anyone but the owner and admins.
    client_address: Mapped[str] = mapped_column(server_default="")
    client_birthday: Mapped[date | None]
    # "Do not discuss" for this client. Never sent to the AI.
    sensitive_items: Mapped[str] = mapped_column(server_default="")
    line_of_business: Mapped[str]
    carrier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carriers.id"))
    referred_date: Mapped[date]
    status: Mapped[str] = mapped_column(server_default="referred")
    # Annual premium. NULL until quoted, so "not quoted" never reads as $0 in averages.
    # Numeric, never float: this is money.
    premium: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bound_date: Mapped[date | None]
    # When it was marked lost. NULL for referrals lost before this column existed.
    lost_date: Mapped[date | None]

    partner: Mapped[Partner] = relationship(back_populates="referrals")
    carrier: Mapped[Carrier] = relationship()
    steps: Mapped[list["ReferralStepCredit"]] = relationship(
        back_populates="referral", order_by="ReferralStepCredit.date"
    )


class ReferralStepCredit(Record, Base):
    """Which rep did a step of a referral. Credit is split by step weight, so one rep per step."""

    __tablename__ = "referral_steps"
    __table_args__ = (
        CheckConstraint(one_of("step", ReferralStep), name="step"),
        live_unique("referral_steps", "referral_id", "step"),
    )

    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id"))
    step: Mapped[str]
    rep_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date]

    referral: Mapped[Referral] = relationship(back_populates="steps")
    rep: Mapped[User] = relationship()


class Activity(Record, Base):
    """A logged touch: a call, an email, a meeting. Never changes steps or credit.

    Belongs to exactly one parent. Referrals today; partners (visits) later. Each parent is a real
    foreign key, so the database won't let an activity point at nothing.
    """

    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("num_nonnulls(referral_id, partner_id) = 1", name="one_parent"),
        CheckConstraint(one_of("method", ContactMethod), name="method"),
        CheckConstraint("char_length(notes) <= 2000", name="notes_length"),
    )

    referral_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("referrals.id"), index=True)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id"), index=True)
    # Who made contact. May differ from logged_by: people log touches on a colleague's behalf.
    rep_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # Who entered it.
    logged_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    method: Mapped[str]
    notes: Mapped[str] = mapped_column(server_default="")
    date: Mapped[date]

    # Relationships to the parents also tell SQLAlchemy to insert a parent before its activities.
    referral: Mapped[Referral | None] = relationship()
    partner: Mapped[Partner | None] = relationship()
    rep: Mapped[User] = relationship(foreign_keys=[rep_id])
    logged_by: Mapped[User] = relationship(foreign_keys=[logged_by_id])


# A referral's last touch: the latest of its referral date, any live step credit, and any live logged
# activity (v1's definition, used for "stale"). Computed in SQL on every load, so it's never out of date.
# Defined after Activity because it reads that table; deleted rows are excluded explicitly because the
# automatic soft-delete filter doesn't reach inside a column expression.
Referral.last_touch = column_property(
    func.greatest(
        Referral.referred_date,
        # correlate_except: each subquery reads its own table even when the outer query joins that table
        # too (e.g. the stale job joins referral_steps); only Referral comes from the outer row.
        select(func.max(ReferralStepCredit.date))
        .where(ReferralStepCredit.referral_id == Referral.id, ReferralStepCredit.deleted_at.is_(None))
        .correlate_except(ReferralStepCredit)
        .scalar_subquery(),
        select(func.max(Activity.date))
        .where(Activity.referral_id == Referral.id, Activity.deleted_at.is_(None))
        .correlate_except(Activity)
        .scalar_subquery(),
    )
)


class RepGoal(Record, Base):
    """A rep's monthly goals. They carry over month to month until an admin changes them."""

    __tablename__ = "rep_goals"
    __table_args__ = (
        live_unique("rep_goals", "user_id"),
        CheckConstraint("clients >= 0", name="clients"),
        CheckConstraint("sales >= 0", name="sales"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    clients: Mapped[int] = mapped_column(server_default="0")  # referrals bound per month
    sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")  # bound premium per month

    user: Mapped[User] = relationship()


class CompanyGoal(Record, Base):
    """Company-wide targets that don't add up from reps' goals (a rate). Exactly one row."""

    __tablename__ = "company_goals"
    __table_args__ = (
        # A boolean that must be true and unique: the table can only ever hold one row.
        CheckConstraint("singleton", name="singleton"),
        live_unique("company_goals", "singleton"),
        CheckConstraint("close_rate IS NULL OR close_rate BETWEEN 0 AND 1", name="close_rate"),
    )

    singleton: Mapped[bool] = mapped_column(server_default=text("true"))
    close_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))  # 0.6000 = 60%


class SavedView(Record, Base):
    """A person's named view of a list: its filters, sort and columns, stored as the URL query."""

    __tablename__ = "saved_views"
    __table_args__ = (
        CheckConstraint(one_of("list", ListName), name="list"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="name_length"),
        CheckConstraint("char_length(query) <= 1000", name="query_length"),
        live_unique("saved_views", "user_id", "list", "name"),
    )

    # No separate index: the unique index above starts with user_id, so it serves "my views" lookups.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    list: Mapped[str]
    name: Mapped[str]
    # The list page's URL query, e.g. "status=quoted&sort=-premium&cols=client,partner,premium".
    query: Mapped[str] = mapped_column(server_default="")

    user: Mapped[User] = relationship()


class Notification(Record, Base):
    """Something a scheduled job (app/jobs/) tells one person: a stale referral, or their weekly digest.

    Stores references and numbers, never copies of names: a stale nudge holds the referral's id and the
    API looks the client up through visible_referrals() when it's read, so a nudge can't outlive the
    reader's access. `dedupe_key` makes the jobs idempotent in the database itself: a retried or
    double-fired run inserts nothing new (see live_unique below).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(one_of("kind", NotificationKind), name="kind"),
        # A stale nudge always names its referral; a digest never does.
        CheckConstraint("(kind = 'stale_referral') = (referral_id IS NOT NULL)", name="referral_for_stale"),
        CheckConstraint("char_length(dedupe_key) BETWEEN 1 AND 200", name="dedupe_key_length"),
        # Also serves "my notifications" lookups (it starts with user_id).
        live_unique("notifications", "user_id", "dedupe_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))  # the recipient
    kind: Mapped[str]
    referral_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("referrals.id"))
    # e.g. "stale:<referral id>:<last touch>" or "digest:<week start>"
    dedupe_key: Mapped[str]
    # Kind-specific numbers (a digest's tallies, a nudge's last-touch date), validated by app/schemas.py.
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    read_at: Mapped[datetime | None]


class AuditEvent(Base):
    """One change to one row, recorded automatically by app/audit.py. Append-only: a database trigger
    refuses UPDATE and DELETE on this table, and TRUNCATE outside the seed script.

    Not a Record on purpose: an event is never edited or soft-deleted, so it has no updated_at or
    deleted_at. No foreign keys either, so nothing can block or cascade into the log.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(one_of("action", AuditAction), name="action"),
        CheckConstraint(one_of("actor_kind", ActorKind), name="actor_kind"),
        CheckConstraint("(actor_kind = 'user') = (actor_id IS NOT NULL)", name="user_actor_has_id"),
        # A record's history: its own events, and those of rows that belong to it.
        Index("ix_audit_events_referral", "referral_id", "occurred_at", postgresql_where=text("referral_id IS NOT NULL")),
        Index("ix_audit_events_partner", "partner_id", "occurred_at", postgresql_where=text("partner_id IS NOT NULL")),
        Index("ix_audit_events_entity", "entity", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    # clock_timestamp(), not now(): now() is when the transaction began, so every event in one request would
    # share a timestamp and a history couldn't be put in order.
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
    actor_kind: Mapped[str]
    actor_id: Mapped[uuid.UUID | None]  # the person, when actor_kind is "user"
    actor_label: Mapped[str | None]  # the job or script name otherwise
    action: Mapped[str]
    entity: Mapped[str]  # the table name
    entity_id: Mapped[uuid.UUID]
    # The record whose history this belongs to (see audit.SUBJECTS), so a page can show its history.
    referral_id: Mapped[uuid.UUID | None]
    partner_id: Mapped[uuid.UUID | None]
    # {field: {"from": ..., "to": ...}}; sensitive fields are {"redacted": true} with no values.
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB)


class UserSession(Record, Base):
    """A signed-in browser. The token lives only in the person's cookie; this row holds its SHA-256.

    Ends at whichever comes first: `expires_at` (a workday after sign-in), two idle hours (see auth.py), or
    `revoked_at` (sign out, password change or reset, or deactivation).
    """

    __tablename__ = "sessions"
    __table_args__ = (live_unique("sessions", "token_hash"), Index("ix_sessions_user_id", "user_id"))

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str]
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    user_agent: Mapped[str] = mapped_column(server_default="")  # "which browser" for the person's own list

    user: Mapped[User] = relationship()


class AccountLink(Record, Base):
    """A one-time link an admin hands someone to set their password (setup) or choose a new one (reset).

    Only the token's SHA-256 is stored. Valid until `expires_at`, and only once; making a new link for the same
    person voids any earlier unused one.
    """

    __tablename__ = "account_links"
    __table_args__ = (
        CheckConstraint(one_of("purpose", LinkPurpose), name="purpose"),
        live_unique("account_links", "token_hash"),
        Index("ix_account_links_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str]
    token_hash: Mapped[str]
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    voided_at: Mapped[datetime | None]
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class LoginAttempt(Base):
    """Every sign-in attempt, for rate limiting (app/routers/auth.py). A security log of its own, so it isn't
    audited again. Keyed by a hash of the email typed, so attempts on made-up emails count the same way as
    real ones (and the log holds no addresses)."""

    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_key_at", "email_key", "attempted_at"), Index("ix_login_attempts_at", "attempted_at"))

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    attempted_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
    email_key: Mapped[str]  # security.email_key()
    succeeded: Mapped[bool]
