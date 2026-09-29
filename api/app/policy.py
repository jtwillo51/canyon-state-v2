"""Blocked fields: values only a record's owners and admins may see.

Everyone else gets the string "blocked" in place of the value (v1's rule). The policy is a
constant for now, matching v1's defaults; it moves to an admin-editable table with the admin
screens.

Scoping, not masking, is what protects referrals today: a rep only ever sees referrals they
own. Masking matters wherever one person's record is shown to someone else (visits, shared views).
"""

import uuid
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel

from app.auth import is_admin
from app.models import User

BLOCKED: Literal["blocked"] = "blocked"

BLOCKED_FIELDS: dict[str, frozenset[str]] = {
    "referral": frozenset({"client_address", "client_birthday"}),
}


def mask[M: BaseModel](record: M, kind: str, viewer: User, owners: Iterable[uuid.UUID]) -> M:
    """Return `record` with its blocked fields replaced, unless the viewer is an owner or an admin."""
    if is_admin(viewer) or viewer.id in set(owners):
        return record
    return record.model_copy(update={field: BLOCKED for field in BLOCKED_FIELDS.get(kind, ())})
