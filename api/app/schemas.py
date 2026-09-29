"""API shapes (Pydantic). A field reaches a response only if a schema here names it.

These also define the OpenAPI schema the TypeScript client is generated from.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

from app.models import LineOfBusiness, PartnerType, ReferralStatus, ReferralStep, Role

# Money is Numeric in the database and a JSON number on the wire (Pydantic's default is a string).
Money = Annotated[Decimal, PlainSerializer(float, return_type=float)]
Blocked = Literal["blocked"]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # build straight from ORM objects


class UserRef(Schema):
    id: uuid.UUID
    name: str


class DevUserOut(Schema):
    """A person the development "View as" switcher can act as."""

    id: uuid.UUID
    name: str
    role: Role


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
    steps: list[StepOut]
