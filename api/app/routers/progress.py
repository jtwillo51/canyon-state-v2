"""Progress toward monthly goals, and setting the goals.

What each viewer gets (DECISIONS.md, "Progress and goals"):
- Admins: company totals and every active rep's numbers, with goals and both comparisons.
- A rep: only their own numbers (both comparisons; sales vs the team only as a percentage) and the
  company's progress as a share of goal, never company or colleagues' dollars and counts.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth import DB, Viewer, is_admin
from app.clock import agency_today
from app.errors import FIELD_ERROR_RESPONSE, FieldError
from app.models import CompanyGoal, RepGoal, User
from app.progress import Tally, diff, month_windows, others_average, relative, tallies
from app.schemas import (
    CompanyGoalIn,
    CompanyProgress,
    CompanyShare,
    Metric,
    ProgressOut,
    RepGoalIn,
    RepProgress,
    UserRef,
)

router = APIRouter(tags=["progress"])


def _f(x: Decimal | int | float | None) -> float | None:
    return None if x is None else float(x)


@router.get("/progress")
async def progress(viewer: Viewer, db: DB) -> ProgressOut:
    today = agency_today()
    (start, end), (prev_start, prev_end) = month_windows(today)
    company, reps_now = await tallies(db, start, end)
    company_prev, reps_prev = await tallies(db, prev_start, prev_end)

    reps = (await db.execute(select(User).where(User.role == "rep", User.active).order_by(User.name))).scalars().all()
    goals = {g.user_id: g for g in (await db.execute(select(RepGoal))).scalars()}
    company_goal = (await db.execute(select(CompanyGoal))).scalar_one_or_none()
    close_rate_goal = _f(company_goal.close_rate) if company_goal else None

    now = {r.id: reps_now.get(r.id, Tally()) for r in reps}
    prev = {r.id: reps_prev.get(r.id, Tally()) for r in reps}
    values = {
        "clients": {k: float(t.clients) for k, t in now.items()},
        "sales": {k: float(t.sales) for k, t in now.items()},
        "close_rate": {k: t.close_rate for k, t in now.items()},
    }

    def rep_metric(rep_id: uuid.UUID, name: str, goal: float | None) -> Metric:
        value = values[name][rep_id]
        before = {"clients": float(prev[rep_id].clients), "sales": float(prev[rep_id].sales),
                  "close_rate": prev[rep_id].close_rate}[name]  # fmt: skip
        avg = others_average(values[name], rep_id)
        return Metric(value=value, goal=goal, vs_last_month=diff(value, before), vs_team=diff(value, avg),
                      vs_team_pct=relative(value, avg))  # fmt: skip

    def rep_row(r: User) -> RepProgress:
        g = goals.get(r.id)
        return RepProgress(
            rep=UserRef.model_validate(r),
            clients=rep_metric(r.id, "clients", _f(g.clients) if g else None),
            sales=rep_metric(r.id, "sales", _f(g.sales) if g else None),
            close_rate=rep_metric(r.id, "close_rate", close_rate_goal),
        )

    goal_clients = _f(sum(g.clients for g in goals.values() if g.user_id in now)) if goals else None
    goal_sales = _f(sum(g.sales for g in goals.values() if g.user_id in now)) if goals else None
    month = {"month": today.strftime("%Y-%m"), "through": today, "compared_through": prev_end}

    if is_admin(viewer):
        return ProgressOut(
            **month,
            company=CompanyProgress(
                clients=Metric(value=company.clients, goal=goal_clients, vs_last_month=company.clients - company_prev.clients,
                               vs_team=None, vs_team_pct=None),  # fmt: skip
                sales=Metric(value=_f(company.sales), goal=goal_sales,
                             vs_last_month=_f(company.sales - company_prev.sales), vs_team=None, vs_team_pct=None),  # fmt: skip
                close_rate=Metric(value=company.close_rate, goal=close_rate_goal,
                                  vs_last_month=diff(company.close_rate, company_prev.close_rate), vs_team=None,
                                  vs_team_pct=None),  # fmt: skip
            ),
            company_share=None,
            reps=[rep_row(r) for r in reps],
        )

    # A rep: themselves only. Sales vs the team only as a percentage: no colleague dollars.
    mine = [rep_row(r) for r in reps if r.id == viewer.id]
    for row in mine:
        row.sales.vs_team = None
    return ProgressOut(
        **month,
        company=None,
        company_share=CompanyShare(
            clients_pct_of_goal=company.clients / goal_clients if goal_clients else None,
            sales_pct_of_goal=float(company.sales) / goal_sales if goal_sales else None,
            close_rate=company.close_rate,
            close_rate_goal=close_rate_goal,
        ),
        reps=mine,
    )


def _require_admin(viewer: User, field: str) -> None:
    if not is_admin(viewer):
        raise FieldError("Only an admin can change goals.", field=field)


@router.put("/goals/reps/{user_id}", responses=FIELD_ERROR_RESPONSE)
async def set_rep_goal(user_id: uuid.UUID, goal: RepGoalIn, viewer: Viewer, db: DB) -> RepGoalIn:
    _require_admin(viewer, "clients")
    rep = (await db.execute(select(User).where(User.id == user_id, User.role == "rep"))).scalar_one_or_none()
    if rep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rep not found")
    row = (await db.execute(select(RepGoal).where(RepGoal.user_id == user_id))).scalar_one_or_none()
    if row is None:
        row = RepGoal(user_id=user_id)
        db.add(row)
    row.clients, row.sales = goal.clients, goal.sales
    await db.commit()
    return goal


@router.put("/goals/company", responses=FIELD_ERROR_RESPONSE)
async def set_company_goal(goal: CompanyGoalIn, viewer: Viewer, db: DB) -> CompanyGoalIn:
    _require_admin(viewer, "close_rate")
    row = (await db.execute(select(CompanyGoal))).scalar_one_or_none()
    if row is None:
        row = CompanyGoal()
        db.add(row)
    row.close_rate = goal.close_rate
    await db.commit()
    return goal
