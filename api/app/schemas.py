"""API shapes (Pydantic). A field reaches a response only if a schema here names it.

These also define the OpenAPI schema the TypeScript client is generated from.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from app.models import ContactMethod, LineOfBusiness, ListName, PartnerType, ReferralStatus, ReferralStep, Role
from app.sorting import check_sort

# Money is Numeric in the database and a JSON number on the wire (Pydantic's default is a string).
Money = Annotated[Decimal, PlainSerializer(float, return_type=float)]
Blocked = Literal["blocked"]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # build straight from ORM objects


class UserRef(Schema):
    id: uuid.UUID
    name: str


class Me(Schema):
    """The signed-in person."""

    id: uuid.UUID
    name: str
    role: Role


class DevUserOut(Me):
    """A person the development "View as" switcher can act as."""


class CarrierRef(Schema):
    id: uuid.UUID
    name: str


class PartnerRef(Schema):
    id: uuid.UUID
    name: str
    business_name: str


class ProductionOut(Schema):
    year: int
    amount: Money
    verified: bool


class PartnerOut(Schema):
    id: uuid.UUID
    name: str
    type: PartnerType
    type_other: str | None
    business_name: str
    phone: str
    email: str
    territory: str
    primary_rep: UserRef | None
    do_not_contact: bool
    # "Do not discuss": shown to the whole team on purpose, so nobody raises the topic.
    sensitive_items: str
    production: list[ProductionOut]


class PartnerStats(BaseModel):
    """A partner's referral numbers for the chosen period (referrals referred in it)."""

    referrals: int  # team-wide
    bound: int  # team-wide
    # bound / referrals, by count. PLACEHOLDER definition: how the agency measures close rate is still
    # open (FIELD_QUESTIONS #2). Null when there were no referrals.
    close_rate: float | None
    # Money is scoped like v1: admins see the partner's total, a rep only referrals they're credited on.
    bound_premium: Money
    last_referred: date | None  # most recent referral, any period, team-wide


class PartnerRow(PartnerOut):
    stats: PartnerStats


class PartnerPage(BaseModel):
    items: list[PartnerRow]
    total: int
    limit: int
    offset: int


Period = Literal["r12", "ytd", "all"]  # last 12 months, year to date (Arizona), all time

PartnerSort = Literal[
    "name", "-name",
    "referrals", "-referrals",
    "bound", "-bound",
    "close_rate", "-close_rate",
    "bound_premium", "-bound_premium",
    "last_referred", "-last_referred",
]  # fmt: skip


class PartnerQuery(BaseModel):
    """Filters, sort, period and page for GET /partners. Unknown keys are refused."""

    model_config = ConfigDict(extra="forbid")

    type: list[PartnerType] = []
    primary_rep_id: uuid.UUID | None = None
    unassigned: bool | None = None  # no primary rep
    do_not_contact: bool | None = None
    no_referrals: bool | None = None  # none in the period
    min_referrals: int | None = Field(default=None, ge=1, le=1000)  # e.g. rank only partners with 3+
    q: str | None = Field(default=None, max_length=100)  # name or business contains
    period: Period = "r12"
    sort: list[PartnerSort] = ["-referrals"]  # several: sort by the first, then the next (?sort=-a&sort=b)

    @field_validator("sort")
    @classmethod
    def _at_most_three_each_once(cls, keys: list[str]) -> list[str]:
        return check_sort(keys)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class StepOut(Schema):
    step: ReferralStep
    rep: UserRef
    date: date


class ReferralOut(Schema):
    id: uuid.UUID
    partner: PartnerRef
    client_name: str
    client_address: str | Blocked
    client_birthday: date | Blocked | None
    sensitive_items: str
    line_of_business: LineOfBusiness
    carrier: CarrierRef
    referred_date: date
    status: ReferralStatus
    premium: Money | None  # null until quoted
    bound_date: date | None
    lost_date: date | None
    # Latest of the referral date, its step credits and its logged activity. "Stale" is judged by this.
    last_touch: date
    steps: list[StepOut]


ReferralSort = Literal[
    "referred_date", "-referred_date",
    "last_touch", "-last_touch",
    "client_name", "-client_name",
    "premium", "-premium",
    "status", "-status",
]  # fmt: skip


class ReferralQuery(BaseModel):
    """Filters, sort and page for GET /referrals, all from the query string. Unknown keys are refused."""

    model_config = ConfigDict(extra="forbid")

    status: list[ReferralStatus] = []
    line: list[LineOfBusiness] = []
    partner_id: uuid.UUID | None = None
    rep_id: uuid.UUID | None = None  # credited on at least one step
    stale_days: int | None = Field(default=None, ge=1, le=3650)  # open, no touch in this many days
    bound_from: date | None = None
    bound_to: date | None = None
    has_premium: bool | None = None
    q: str | None = Field(default=None, max_length=100)  # client name contains
    sort: list[ReferralSort] = ["-referred_date"]  # several: sort by the first, then the next

    @field_validator("sort")
    @classmethod
    def _at_most_three_each_once(cls, keys: list[str]) -> list[str]:
        return check_sort(keys)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ReferralPage(BaseModel):
    """One page of a filtered, sorted referral list."""

    items: list[ReferralOut]
    total: int  # matching referrals across all pages
    limit: int
    offset: int


class StatusChange(BaseModel):
    """Move a referral on the pipeline. See app/pipeline.py for the rules."""

    status: ReferralStatus
    premium: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    bound_date: date | None = None
    # Admins name the rep who did the work; reps are always credited themselves.
    credit_rep_id: uuid.UUID | None = None


class ActivityOut(Schema):
    id: uuid.UUID
    method: ContactMethod
    date: date
    notes: str
    rep: UserRef  # who made contact
    logged_by: UserRef  # who entered it


class PartnerPatch(BaseModel):
    """Inline edit of a partner. Only fields present in the request change (`model_fields_set`),
    so "primary_rep_id": null unassigns, while leaving it out leaves it alone."""

    model_config = ConfigDict(extra="forbid")

    do_not_contact: bool | None = None
    sensitive_items: str | None = Field(default=None, max_length=2000)
    territory: str | None = Field(default=None, max_length=100)
    primary_rep_id: uuid.UUID | None = None  # admins only


class ReferralPatch(BaseModel):
    """Inline edit of a referral's policy details. Pipeline moves go through /status instead."""

    model_config = ConfigDict(extra="forbid")

    line_of_business: LineOfBusiness | None = None
    carrier_id: uuid.UUID | None = None
    premium: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class Metric(BaseModel):
    """One progress number for the month so far, with its comparisons.

    Units: clients are a count, sales are dollars, close rate is a fraction (0.64 = 64%); a close-rate
    difference is in fraction points (0.05 = 5 pts).
    """

    value: float | None  # None: nothing to measure yet (e.g. no referral decided, so no close rate)
    goal: float | None
    vs_last_month: float | None  # value minus the same point last month
    vs_team: float | None  # value minus the average of the other reps (rep rows only)
    vs_team_pct: float | None  # the same as a relative difference, 0.38 = 38% above the others


class RepProgress(BaseModel):
    rep: UserRef
    clients: Metric
    sales: Metric
    close_rate: Metric


class CompanyProgress(BaseModel):
    """Company totals, for admins."""

    clients: Metric
    sales: Metric
    close_rate: Metric


class CompanyShare(BaseModel):
    """What a rep sees of the company: progress as a share of goal, never company dollars or counts."""

    clients_pct_of_goal: float | None
    sales_pct_of_goal: float | None
    close_rate: float | None  # already a percentage, so shown as is
    close_rate_goal: float | None


class ProgressOut(BaseModel):
    month: str  # "2026-09"
    through: date  # today (Arizona)
    compared_through: date  # the same point last month
    company: CompanyProgress | None  # admins only
    company_share: CompanyShare | None  # reps only
    reps: list[RepProgress]  # admins: every active rep; a rep: only themselves


class RepGoalIn(BaseModel):
    clients: int = Field(ge=0, le=10_000)
    sales: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CompanyGoalIn(BaseModel):
    close_rate: Decimal | None = Field(ge=0, le=1, max_digits=5, decimal_places=4)


class SavedViewOut(Schema):
    id: uuid.UUID
    list: ListName
    name: str
    query: str


class SavedViewIn(BaseModel):
    list: ListName
    name: str = Field(min_length=1, max_length=60)
    # The list page's URL query without the "?": only "key=value" pairs, joined by "&".
    query: str = Field(default="", max_length=1000, pattern=r"^[A-Za-z0-9_\-.,~%=&+]*$")


class ActivityIn(BaseModel):
    """Log a touch. Rules beyond these types (dates, who) are checked in the endpoint."""

    rep_id: uuid.UUID
    date: date
    method: ContactMethod
    notes: str = Field(default="", max_length=2000)
