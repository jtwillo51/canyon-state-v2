"""Who may see which referrals. Every referral query, and every number derived from referrals,
applies these conditions. Admins see everything; a rep sees the referrals they're credited on."""

import uuid

from sqlalchemy import ColumnElement, select

from app.auth import is_admin
from app.models import Referral, ReferralStepCredit, User


def credited_to(rep_id: uuid.UUID) -> ColumnElement[bool]:
    """Referrals with a live step credit for this rep (the soft-delete filter covers the subquery)."""
    return Referral.id.in_(select(ReferralStepCredit.referral_id).where(ReferralStepCredit.rep_id == rep_id))


def referral_scope(viewer: User) -> list[ColumnElement[bool]]:
    """Conditions limiting referrals to what this viewer may see: nothing for admins, their own for reps."""
    return [] if is_admin(viewer) else [credited_to(viewer.id)]
