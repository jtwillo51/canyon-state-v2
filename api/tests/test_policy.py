"""Blocked-field masking, tested directly: no endpoint shows a non-owner a referral yet."""

import uuid
from datetime import date

from app.models import User
from app.policy import BLOCKED, mask
from app.schemas import CarrierRef, PartnerRef, ReferralOut

OWNER = User(id=uuid.uuid4(), name="Owner", email="o@example.test", role="rep")
OTHER_REP = User(id=uuid.uuid4(), name="Other", email="x@example.test", role="rep")
ADMIN = User(id=uuid.uuid4(), name="Admin", email="a@example.test", role="admin")

REFERRAL = ReferralOut(
    id=uuid.uuid4(),
    partner=PartnerRef(id=uuid.uuid4(), name="P", business_name="B"),
    client_name="Client",
    client_address="1 Main St",
    client_birthday=date(1980, 1, 1),
    sensitive_items="",
    line_of_business="Auto",
    carrier=CarrierRef(id=uuid.uuid4(), name="C"),
    referred_date=date(2026, 1, 1),
    status="referred",
    premium=None,
    bound_date=None,
    lost_date=None,
    last_touch=date(2026, 1, 1),
    steps=[],
)


def test_non_owner_rep_gets_blocked_values() -> None:
    masked = mask(REFERRAL, "referral", OTHER_REP, owners=[OWNER.id])
    assert masked.client_address == BLOCKED
    assert masked.client_birthday == BLOCKED
    assert masked.client_name == "Client"  # not a blocked field


def test_owner_and_admin_see_real_values() -> None:
    for viewer in (OWNER, ADMIN):
        seen = mask(REFERRAL, "referral", viewer, owners=[OWNER.id])
        assert seen.client_address == "1 Main St"
        assert seen.client_birthday == date(1980, 1, 1)


def test_mask_does_not_modify_the_original() -> None:
    mask(REFERRAL, "referral", OTHER_REP, owners=[OWNER.id])
    assert REFERRAL.client_address == "1 Main St"
