"""Monthly progress toward goals: clients, sales and close rate, for the company and each rep.

Definitions (DECISIONS.md, "Progress and goals"):
- Clients: referrals bound in the period. Sales: their bound premium. Both count toward the rep credited
  with the bind step, so reps' totals add up to the company's.
- Close rate: of referrals decided in the period (bound or lost), the share bound, attributed to the rep
  who introduced them. PLACEHOLDER until the agency answers FIELD_QUESTIONS #2.
- "This month" runs from the 1st to today (Arizona); "last month" is the same span of the previous month,
  so mid-month comparisons are fair.
"""

import calendar
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Referral, ReferralStepCredit


@dataclass
class Tally:
    clients: int = 0
    sales: Decimal = Decimal(0)
    decided: int = 0
    won: int = 0

    @property
    def close_rate(self) -> float | None:
        return self.won / self.decided if self.decided else None


def month_windows(today: date) -> tuple[tuple[date, date], tuple[date, date]]:
    """(this month so far, the same span of last month). On 31 March, last month's span ends 28/29 Feb."""
    start = today.replace(day=1)
    prev_start = (start - timedelta(days=1)).replace(day=1)
    prev_len = calendar.monthrange(prev_start.year, prev_start.month)[1]
    return (start, today), (prev_start, prev_start.replace(day=min(today.day, prev_len)))


async def tallies(db: AsyncSession, start: date, end: date) -> tuple[Tally, dict[uuid.UUID, Tally]]:
    """The company's tally and each rep's, for referrals bound or decided between start and end."""
    live = Referral.deleted_at.is_(None)
    bound_in = and_(Referral.status == "bound", Referral.bound_date.between(start, end))
    decided_in = or_(bound_in, and_(Referral.status == "lost", Referral.lost_date.between(start, end)))
    won = func.count().filter(Referral.status == "bound")

    def credit(step: str):
        c = aliased(ReferralStepCredit)
        return c, and_(c.referral_id == Referral.id, c.step == step, c.deleted_at.is_(None))

    bind, bind_on = credit("bind")
    intro, intro_on = credit("introduction")
    reps: dict[uuid.UUID, Tally] = {}

    sales_by_rep = select(bind.rep_id, func.count(), func.sum(Referral.premium)).join(bind, bind_on)
    for rep_id, n, total in await db.execute(sales_by_rep.where(live, bound_in).group_by(bind.rep_id)):
        reps.setdefault(rep_id, Tally()).clients, reps[rep_id].sales = n, total or Decimal(0)

    decided_by_rep = select(intro.rep_id, func.count(), won).join(intro, intro_on)
    for rep_id, n, w in await db.execute(decided_by_rep.where(live, decided_in).group_by(intro.rep_id)):
        t = reps.setdefault(rep_id, Tally())
        t.decided, t.won = n, w

    clients, sales = (await db.execute(select(func.count(), func.sum(Referral.premium)).where(live, bound_in))).one()
    decided, won_total = (await db.execute(select(func.count(), won).where(live, decided_in))).one()
    company = Tally(clients=clients, sales=sales or Decimal(0), decided=decided, won=won_total)
    return company, reps


def diff(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def relative(a: float | None, b: float | None) -> float | None:
    """a relative to b: 0.38 = 38% above. None when b is zero or missing."""
    return None if a is None or not b else a / b - 1


def others_average(values: dict[uuid.UUID, float | None], rep_id: uuid.UUID) -> float | None:
    """The mean over every rep except this one, skipping reps with no value (no close rate yet)."""
    others = [v for k, v in values.items() if k != rep_id and v is not None]
    return mean(others) if others else None
