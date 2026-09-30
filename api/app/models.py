"""Database tables (SQLAlchemy). API shapes live separately in app/schemas.py.

Fields mirror v1's src/types/index.ts. Fixed value lists are text columns guarded by CHECK
constraints; the lists themselves are the Literal types below, shared with the schemas.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, get_args

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Role = Literal["admin", "rep"]
PartnerType = Literal["Loan officer", "Realtor", "Financial advisor", "Other"]
ReferralStatus = Literal["referred", "contacted", "quoted", "bound", "lost"]
LineOfBusiness = Literal["Auto", "Home", "Umbrella", "Life", "Commercial"]
ReferralStep = Literal["introduction", "contact", "quote", "bind"]
# How a rep reached someone: the agency's own form uses these three.
ContactMethod = Literal["In person", "Phone", "Email"]


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
