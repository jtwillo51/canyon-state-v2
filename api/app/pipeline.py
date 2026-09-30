"""The referral pipeline: which status changes are allowed, and what each one records.

Rules (DECISIONS.md, "Pipeline"):
- Forward one or more steps: referred -> contacted -> quoted -> bound. Skipping is allowed.
- Any open referral can be marked lost.
- Moving backward, or reopening a bound or lost referral, is admin-only: it rewrites credit.
- Each step passed on the way forward credits one rep: the person moving it, or, when an admin
  moves it, a rep the admin names.
- Quoted needs a premium; bound needs a premium and a bind date.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import get_args

from app.errors import FieldError
from app.models import Referral, ReferralStatus, ReferralStepCredit, User

# Position on the pipeline. "lost" is off the line: it's an outcome, not a step.
ORDER: dict[str, int] = {"referred": 0, "contacted": 1, "quoted": 2, "bound": 3}
# The step a rep gets credit for when a referral reaches each status.
STEP_FOR: dict[str, str] = {"contacted": "contact", "quoted": "quote", "bound": "bind"}
OPEN = ("referred", "contacted", "quoted")
assert set(ORDER) | {"lost"} == set(get_args(ReferralStatus))


class PipelineError(FieldError):
    """A change the rules don't allow. The message is shown to the user as-is."""


def check_move(referral: Referral, target: str, viewer: User) -> None:
    """Raise PipelineError unless `viewer` may move `referral` to `target`."""
    current = referral.status
    if target == current:
        raise PipelineError(f"It's already {current}.")
    admin = viewer.role == "admin"
    if target == "lost":
        if current not in OPEN and not admin:
            raise PipelineError("Only an admin can mark a bound referral lost.")
        return
    forward = current in OPEN and ORDER[target] > ORDER[current]
    if not forward and not admin:
        raise PipelineError("Only an admin can move a referral backward or reopen it.")


def apply_move(
    referral: Referral,
    target: str,
    *,
    credit_rep: User | None,
    premium: Decimal | None,
    bound_date: date | None,
    today: date,
) -> list[ReferralStepCredit]:
    """Change the referral's status and return the new step credits (not yet added to a session).

    Call check_move first. `credit_rep` is required when the move passes a step. Raises
    PipelineError before changing anything.
    """
    if target == "lost":
        referral.status, referral.lost_date, referral.bound_date = "lost", today, None
        return []

    # 1. Validate everything first, so a refused move changes nothing.
    quoted = ORDER[target] >= ORDER["quoted"]
    if quoted:
        # An existing premium counts, so quoted -> bound needn't repeat it.
        premium = premium if premium is not None else referral.premium
        if premium is None or premium <= 0:
            raise PipelineError("Enter the annual premium.", field="premium")
    if target == "bound":
        if bound_date is None:
            raise PipelineError("Enter the bind date.", field="bound_date")
        if not referral.referred_date <= bound_date <= today:
            raise PipelineError("The bind date must be between the referral date and today.", field="bound_date")

    live = {c.step: c for c in referral.steps if c.deleted_at is None}
    # From lost, the steps already credited stand; start from the furthest one.
    start = ORDER[referral.status] if referral.status in ORDER else _furthest(live)
    to_credit = [STEP_FOR[s] for s, rank in ORDER.items() if s in STEP_FOR and start < rank <= ORDER[target]]
    to_credit = [step for step in to_credit if step not in live]
    to_uncredit = [live[STEP_FOR[s]] for s, rank in ORDER.items() if rank > ORDER[target] and STEP_FOR.get(s) in live]
    if to_credit and credit_rep is None:
        raise PipelineError("Choose the rep who did this work.", field="credit_rep_id")

    # 2. Then change the referral.
    referral.premium = premium if quoted else None  # "not quoted yet" is NULL, never $0
    referral.bound_date = bound_date if target == "bound" else None
    referral.status, referral.lost_date = target, None
    for credit in to_uncredit:
        credit.deleted_at = datetime.now(UTC)  # moving back past a step un-credits it (soft delete keeps history)
    assert credit_rep is not None or not to_credit
    return [
        ReferralStepCredit(
            referral_id=referral.id,
            step=step,
            rep_id=credit_rep.id,  # type: ignore[union-attr]
            date=referral.bound_date if step == "bind" else today,
        )
        for step in to_credit
    ]


def _furthest(live: dict[str, ReferralStepCredit]) -> int:
    """How far a lost referral had got, judged by its live credits."""
    reached = [ORDER[s] for s, step in STEP_FOR.items() if step in live]
    return max(reached, default=ORDER["referred"])
