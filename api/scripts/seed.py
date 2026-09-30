"""Fill the local database with synthetic data. Wipes the tables first.

A port of v1's src/mock/seed.ts: same people, businesses and carriers, same shape of activity.
Everything comes from one seeded random generator, so every run produces the same records
(UUIDs included); only the dates move, ending on the day you seed.

Run from api/:  uv run python -m scripts.seed
Refuses to run unless DATABASE_URL points at this machine, or DEMO_MODE is on (the public demo,
which only ever holds synthetic data).
"""

import asyncio
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from random import Random

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import settings
from app.db import SessionLocal, engine
from app.models import (
    Activity,
    Base,
    Carrier,
    CompanyGoal,
    Partner,
    PartnerProduction,
    Referral,
    ReferralStepCredit,
    RepGoal,
    User,
)

rng = Random(20260918)

TODAY = date.today()
START = TODAY - timedelta(days=565)  # about 18 months, like v1's window


def new_id() -> uuid.UUID:
    """A UUID from the seeded generator, so ids are stable across reseeds."""
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def pick[T](xs: list[T] | tuple[T, ...]) -> T:
    return xs[rng.randrange(len(xs))]


def chance(p: float) -> bool:
    return rng.random() < p


def random_date(start: date = START, end: date = TODAY) -> date:
    return start + timedelta(days=rng.randrange((end - start).days))


def random_birthday(first_year: int, last_year: int) -> date:
    return date(rng.randint(first_year, last_year), rng.randint(1, 12), rng.randint(1, 28))


# --- People and companies (all fictional) ---------------------------------------------------

USERS = [
    ("Dana Whitfield", "dana@example.test", "admin"),
    ("Marcus Lee", "marcus@example.test", "admin"),
    ("Tessa Moreno", "tessa@example.test", "rep"),
    ("Jordan Pike", "jordan@example.test", "rep"),
    ("Ava Castillo", "ava@example.test", "rep"),
    ("Eli Brandt", "eli@example.test", "rep"),
    ("Nora Quinn", "nora@example.test", "rep"),
    ("Caleb Ortiz", "caleb@example.test", "rep"),
]
CARRIERS = [
    "Mesa Mutual",
    "Sonoran General",
    "Red Rock Indemnity",
    "Superstition Casualty",
    "Palo Verde Life",
    "Mogollon Specialty",
]
FIRST = ["Maya", "Derek", "Lena", "Victor", "Priya", "Owen", "Sofia", "Grant", "Hailey", "Rafael", "Jenna", "Tomás", "Brooke", "Isaiah", "Kara", "Wes", "Alma", "Reid", "Celeste", "Hector", "Paige", "Luis", "Megan", "Troy", "Iris", "Colby", "Nadia", "Shane", "Elena", "Garrett"]  # fmt: skip
LAST = ["Hollis", "Vance", "Ruiz", "Okafor", "Sterling", "Duarte", "Kemp", "Navarro", "Ashby", "Fong", "Lindqvist", "Rowe", "Serrano", "Batts", "Carrow", "Mendel", "Aguilar", "Pruitt", "Yazzie", "Holloway"]  # fmt: skip
BIZ = {
    "Loan officer": ["Saguaro Home Loans", "Desert Sky Mortgage", "Copperline Lending", "Four Peaks Funding", "Arcadia Mortgage Group"],
    "Realtor": ["Sun Corridor Realty", "Pinnacle Peak Properties", "Gilbert Gateway Homes", "Red Mountain Realty", "Queen Creek Living"],
    "Financial advisor": ["Camelback Wealth Partners", "Ocotillo Financial", "Tempe Town Advisors", "Ironwood Planning"],
}  # fmt: skip
TERRITORIES = ["East Valley", "East Valley", "East Valley", "West Valley", "Scottsdale", "Central Phoenix", "Las Vegas"]  # fmt: skip
CLIENT_FIRST = ["Aaron", "Bianca", "Carlos", "Dina", "Evan", "Fatima", "Gabe", "Holly", "Ivan", "Jada", "Kyle", "Lucia", "Mason", "Nina", "Oscar", "Piper", "Quincy", "Rosa", "Sam", "Tara"]  # fmt: skip
STREETS = ["E Baseline Rd", "S Val Vista Dr", "N Gilbert Rd", "E Queen Creek Rd", "S Power Rd", "W Ray Rd"]
CITIES = ["Gilbert", "Chandler", "Mesa", "Queen Creek"]
PARTNER_SENSITIVE = [
    "Recent family loss. Avoid asking about family.",
    "Going through a divorce; don't ask about their spouse.",
]
CLIENT_SENSITIVE = [
    "Recently divorced, so don't ask about their spouse.",
    "Lost a parent this spring; avoid family questions.",
    "Just had a claim denied elsewhere and is still upset about it.",
]


def build() -> list[Base]:
    users = [User(id=new_id(), name=n, email=e, role=r) for n, e, r in USERS]
    reps = [u for u in users if u.role == "rep"]
    carriers = [Carrier(id=new_id(), name=n) for n in CARRIERS]

    partners: list[Partner] = []
    production: list[PartnerProduction] = []
    for i in range(32):
        ptype = "Other" if i % 11 == 10 else pick(["Loan officer", "Loan officer", "Realtor", "Realtor", "Realtor", "Financial advisor"])  # fmt: skip
        first, last = FIRST[i % len(FIRST)], LAST[(i * 7) % len(LAST)]  # unique first+last pairs
        partner = Partner(
            id=new_id(),
            name=f"{first} {last}",
            type=ptype,
            type_other=pick(["Builder", "CPA", "Property manager"]) if ptype == "Other" else None,
            business_name=f"{last} & Associates" if ptype == "Other" else pick(BIZ[ptype]),
            phone=f"(480) 555-{1000 + i * 37}",
            email=f"{first.lower()}.{last.lower()}@example.test",
            territory=pick(TERRITORIES),
            # A few partners have no primary rep yet, like unassigned rows in the spreadsheet.
            primary_rep_id=None if i % 10 == 9 else reps[i % len(reps)].id,
            do_not_contact=i in (7, 23),
            sensitive_items=PARTNER_SENSITIVE[0] if i % 9 == 4 else PARTNER_SENSITIVE[1] if i % 13 == 7 else "",
        )
        partners.append(partner)

        base = rng.randint(4, 60) if ptype == "Loan officer" else rng.randint(3, 30) if ptype == "Realtor" else rng.randint(2, 20)  # fmt: skip
        for k, year in enumerate(range(TODAY.year - 2, TODAY.year + 1)):
            amount = round(base * (0.85 + k * 0.1 + rng.random() * 0.2)) * 1_000_000
            production.append(
                PartnerProduction(
                    id=new_id(),
                    partner_id=partner.id,
                    year=year,
                    amount=Decimal(amount),
                    verified=year < TODAY.year or chance(0.4),
                )
            )

    # Work mostly comes from the partner's primary rep, sometimes from someone else.
    home_rep = {p.id: p.primary_rep_id or reps[i % len(reps)].id for i, p in enumerate(partners)}

    def rep_for(partner_id: uuid.UUID) -> uuid.UUID:
        return home_rep[partner_id] if chance(0.8) else pick(reps).id

    referrals: list[Referral] = []
    steps: list[ReferralStepCredit] = []
    for p in partners:
        quality = rng.random()  # partner quality drives referral volume and close rate
        for _ in range(round(quality * quality * 22) + rng.randint(0, 3)):
            referred = random_date()
            intro_rep = rep_for(p.id)
            work_rep = intro_rep if chance(0.7) else pick(reps).id
            roll = rng.random()
            progress = 1 if roll < 0.12 else 2 if roll < 0.25 else 3  # steps reached before the outcome
            bound = progress == 3 and rng.random() < 0.35 + quality * 0.5
            lost = not bound and referred < TODAY - timedelta(days=45) and chance(0.7)
            bound_date = min(referred + timedelta(days=rng.randint(7, 30)), TODAY) if bound else None
            lob = pick(["Auto", "Auto", "Home", "Home", "Home", "Umbrella", "Life", "Commercial"])
            low, high = (2500, 9000) if lob == "Commercial" else (250, 600) if lob == "Umbrella" else (900, 3200)
            status = "bound" if bound else "lost" if lost else ("referred", "contacted", "quoted")[progress - 1]

            referral_id = new_id()
            # Lost 20-45 days after referral. Derived from the id rather than drawn from rng, so
            # adding this field didn't shift the generator (and every id after it).
            lost_date = min(referred + timedelta(days=20 + referral_id.int % 26), TODAY) if lost else None
            referral = Referral(
                id=referral_id,
                partner_id=p.id,
                client_name=f"{pick(CLIENT_FIRST)} {pick(LAST)}",
                client_address=f"{rng.randint(100, 4999)} {pick(STREETS)}, {pick(CITIES)}, AZ",
                client_birthday=random_birthday(1960, 2000),
                sensitive_items=pick(CLIENT_SENSITIVE) if chance(0.06) else "",
                line_of_business=lob,
                carrier_id=pick(carriers).id,
                referred_date=referred,
                status=status,
                # NULL until quoted (see DECISIONS.md), rounded to $10.
                premium=Decimal(round(rng.randint(low, high) / 10) * 10) if progress == 3 else None,
                bound_date=bound_date,
                lost_date=lost_date,
            )
            referrals.append(referral)

            def credit(step: str, rep_id: uuid.UUID, on: date) -> None:
                steps.append(
                    ReferralStepCredit(id=new_id(), referral_id=referral.id, step=step, rep_id=rep_id, date=min(on, TODAY))  # fmt: skip
                )

            credit("introduction", intro_rep, referred)
            if progress >= 2:
                credit("contact", work_rep, referred + timedelta(days=rng.randint(0, 3)))
            if progress >= 3:
                credit("quote", work_rep, referred + timedelta(days=rng.randint(2, 9)))
            if bound_date:
                credit("bind", work_rep, bound_date)

    activities = build_activities(referrals, steps)

    # Monthly goals, sized so this synthetic agency lands near 100%: some reps ahead, some behind. Fixed values,
    # not drawn from rng, so adding them didn't shift any id.
    goals = [
        RepGoal(id=uuid.UUID(int=i + 1, version=4), user_id=rep.id, clients=clients, sales=Decimal(sales))
        for i, (rep, (clients, sales)) in enumerate(
            zip(reps, [(4, 9000), (3, 7000), (3, 6000), (3, 6000), (2, 5000), (2, 4000)], strict=True)
        )
    ]
    company_goal = CompanyGoal(id=uuid.UUID(int=100, version=4), close_rate=Decimal("0.60"))

    # Parents before children, so foreign keys are satisfied as rows go in.
    return [*users, *carriers, *partners, *production, *referrals, *steps, *activities, *goals, company_goal]


ACTIVITY_NOTES = [
    "Left a voicemail, will try again tomorrow.",
    "Sent the quote comparison.",
    "Walked through coverage options and deductibles.",
    "Asked for their current declarations page.",
    "Confirmed the closing date with the lender.",
    "Followed up on the signed application.",
]


def build_activities(referrals: list[Referral], steps: list[ReferralStepCredit]) -> list[Activity]:
    """Touches with each referred client, by the reps on that referral, between referral and close.

    Uses its own generator: drawing from `rng` would shift every id generated after this was added.
    """
    arng = Random(20260929)
    reps_on: dict[uuid.UUID, list[uuid.UUID]] = {}
    for s in steps:
        reps_on.setdefault(s.referral_id, [])
        if s.rep_id not in reps_on[s.referral_id]:
            reps_on[s.referral_id].append(s.rep_id)

    activities = []
    for r in referrals:
        end = r.bound_date or r.lost_date or TODAY
        span = max(0, (end - r.referred_date).days)
        for _ in range(arng.randint(0, 1) if r.status == "referred" else arng.randint(1, 4)):
            rep = arng.choice(reps_on[r.id])
            activities.append(
                Activity(
                    id=uuid.UUID(int=arng.getrandbits(128), version=4),
                    referral_id=r.id,
                    rep_id=rep,
                    logged_by_id=rep,
                    method=arng.choice(["In person", "Phone", "Phone", "Phone", "Email"]),
                    notes=arng.choice(ACTIVITY_NOTES),
                    date=r.referred_date + timedelta(days=arng.randint(0, span)),
                )
            )
    return activities


async def main() -> None:
    url = make_url(settings.database_url)
    if url.host not in ("localhost", "127.0.0.1", "::1") and not settings.demo_mode:
        sys.exit(f"Refusing to seed: DATABASE_URL points at {url.host}, not this machine, and DEMO_MODE is off.")

    rows = build()
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with SessionLocal() as session:
        await session.execute(text(f"TRUNCATE {tables}"))
        session.add_all(rows)
        await session.commit()
    await engine.dispose()

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.__tablename__] = counts.get(row.__tablename__, 0) + 1
    print(f"Seeded {url.database} with data ending {TODAY}:")
    for table, n in counts.items():
        print(f"  {table:<20} {n}")


if __name__ == "__main__":
    asyncio.run(main())
