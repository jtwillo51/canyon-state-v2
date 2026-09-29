# Decisions

The running log of what was decided for Canyon State v2 and why. Newest section last.

## Setup (2026-09-29)

- **What this is:** a rebuild of the Canyon State referral-partner reporting app (v1: Vue 3 on a mock API) on
  Next.js, FastAPI and Postgres, with Inngest for scheduled work. v1 is tagged `v1-vue` in its own repo and
  keeps building, so the two can be compared.
- **One repo, two apps:** `web/` (Next.js) and `api/` (FastAPI). One link to share, one CI pipeline, and the
  generated TypeScript client reads the API's OpenAPI schema from a sibling folder.
- **Private now, public later.** The repo holds synthetic data only, from the first commit, so it can be made
  public without rewriting history.
- **Python tooling: uv.** `pyproject.toml` + `uv.lock`, the Python equivalent of `package.json` + lockfile.
- **Database: Postgres 17 installed locally on Windows** for development. It works offline, and it is the
  only option under which the agency's real data could ever be loaded (locally, never deployed).
- **ORM: SQLAlchemy 2.0, with separate Pydantic schemas.** Database models and API shapes are different
  classes, so a field reaches a response only if a schema names it. Alembic handles migrations.
- **Async all the way down:** `async def` endpoints, `asyncpg`, SQLAlchemy `AsyncSession`. Lazy loading is
  unavailable under async, so every query states its relationships up front (`selectinload`). No surprise
  N+1 queries.
- **API layout:** a flat `api/app/` package (the FastAPI convention), run with `uv run fastapi dev app/main.py`.
- **Web:** Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind 4, ESLint, scaffolded by
  `create-next-app`. **npm** (already familiar, so the learning goes into Next itself), code under
  `web/src/app/`, imports through `@/*`.
- **Reads happen in Server Components.** Pages fetch FastAPI on the Next server and send finished HTML; the
  browser never calls the API, so there is no CORS and the API needn't be public. The API address is
  `API_URL` (server-only, no `NEXT_PUBLIC_` prefix). Interactive pieces (inline edit, drag-to-advance) will
  use client-side fetching when they arrive.

## Database (2026-09-29)

- **Local databases `canyon_dev` (and `canyon_test` for pytest), reached as the `postgres` superuser.**
  Chosen for simplicity in development; the connection string lives in `api/.env` (git-ignored). The known
  tradeoff: the app has full rights over the whole local server. A deployed database gets its own
  limited user.
- **UUID primary keys everywhere.** They can't be guessed from a URL, can safely appear in links, and map
  onto v1's string ids.
- **The Stage 1 slice carries the full v1 fields,** client PII and "do not discuss" notes included, so the
  blocked-field masking is built alongside the first endpoints rather than retrofitted.
- **Config through pydantic-settings** (`app/config.py`): typed settings from env vars or `api/.env`; the app
  refuses to start if `DATABASE_URL` is missing.
- **One async session per request** via the `get_db` dependency (`app/db.py`), with
  `expire_on_commit=False` so objects stay readable after a commit without a hidden re-query.
- **Single agency, no `tenant_id`.** Simpler queries now. Serving a second agency would mean a migration
  touching every table and query; accepted.
- **Fixed lists are text + CHECK constraints** (partner type, role, referral status, line of business,
  referral step). Changing a list is a one-line migration, and the statuses and lines of business are
  still unconfirmed with the agency. The lists are defined once as Python `Literal` types in `app/models.py`.
- **Every table has `created_at`, `updated_at` and `deleted_at` (soft delete).** Nothing in a CRM is
  really gone; the cost is that every query must exclude deleted rows, and uniqueness applies to live rows
  only (partial unique indexes, e.g. user email).
- **Money is `Numeric`, never float** (`premium`, partner production). **`premium` is NULL until quoted,**
  so "not quoted yet" never reads as $0 in averages.
- **Timestamps are `timestamptz`** (an absolute moment), set once for every datetime column in `Base`.
- **Uniqueness counts live rows only.** Because of soft delete, uniqueness rules are partial unique indexes
  (`WHERE deleted_at IS NULL`), not plain UNIQUE constraints; otherwise soft-deleting a wrong entry and
  re-entering it would fail. User email is unique case-insensitively (`lower(email)`).
- **Foreign keys used for per-rep scoping are indexed** (`partners.primary_rep_id`, `referral_steps.rep_id`);
  Postgres doesn't index foreign keys on its own.
- **Migrations are reviewed before they run.** Autogenerate output is read first. The first draft of
  migration 1 was thrown away (never applied) after review found the fixes above.
- **Stage 1 tables:** `users`, `partners`, `partner_production` (v1's `production[]`), `carriers`,
  `referrals`, `referral_steps` (one rep per step per referral, since credit is split by step weight).

## Seed data (2026-09-29)

- **`scripts/seed.py` ports v1's synthetic generator** (same fictional people, businesses and carriers, same
  logic: partner quality drives referral volume and close rate; step credit mostly goes to the primary rep),
  so v1 and v2 show comparable data.
- **Deterministic, UUIDs included:** one `random.Random(20260918)` drives everything, so a record keeps its
  id (and URL) across reseeds.
- **Dates are relative to the day you seed** (the last ~18 months), so "recent", "stale" and "renewing
  soon" always have data. Reseed to refresh.
- **It wipes and reseeds, and only on localhost:** it truncates every table, and refuses to run if
  `DATABASE_URL` points anywhere else.
- `scripts/create_databases.py` creates `canyon_dev` and `canyon_test` using the credentials in `.env`
  (no password prompt).

## Access and endpoints (2026-09-29)

- **Every data endpoint takes a `Viewer`** (`app/auth.py`). Until real sign-in (Stage 3), the viewer comes
  from a development-only `X-Dev-User: <user id>` header, accepted only when `DEV_AUTH=true`. Stage 3 swaps
  `get_viewer()` for a session cookie; endpoints don't change.
- **v1's access rules carry over.** Partners are shared (every rep sees every partner, "do not discuss"
  included, on purpose). A referral belongs to every rep with a live step credit on it; reps see only
  those, admins see all. Scoping lives in one function, `visible_referrals()`, that every referral query
  starts from.
- **Someone else's referral is a 404, not a 403,** so its existence isn't confirmed.
- **Blocked fields: policy in code for now** (`app/policy.py`: `client_address`, `client_birthday`, as in
  v1), moving to an admin-editable table with the admin screens. Non-owners who aren't admins get the string
  `"blocked"`. Under v1's rules, masking never triggers on the referral endpoints (reps only see their own),
  so scoping is what protects referrals; masking matters once visits and shared views arrive.
- **Soft-deleted rows are filtered automatically.** A session hook (`app/db.py`) adds
  `deleted_at IS NULL` to every ORM query, including subqueries and eager-loaded relationships, for every
  table (via the `SoftDelete` mixin). Seeing deleted rows is an explicit opt-in
  (`execution_options(include_deleted=True)`).
- **Money is a JSON number on the wire** (Pydantic defaults `Decimal` to a string). JavaScript has no
  decimal type either way; values are cents-precise dollar amounts, well within float precision.
- **No pagination yet** (338 referrals). Revisit with list views and saved filters in Stage 2.

## Tests (2026-09-29)

- **pytest now, for the access rules**, ahead of the plan's Stage 3: they're what a leak would come from.
  `uv run pytest` from `api/`.
- **Against a real Postgres (`canyon_test`), migrated with Alembic at the start of each run**, so the
  migrations are exercised too. `conftest.py` refuses to run against any other database.
- **Each test runs in a transaction that is rolled back** (app commits become savepoints); the API's
  session is swapped in with FastAPI's `dependency_overrides`. Tests can't leak data into each other.
- **Hand-built fixtures, not the seed:** a tiny `World` (an admin, two reps, one partner, one referral
  each), so every test reads as a rule: "given this, Jordan gets a 404".
- **Async tests use the anyio pytest plugin** (already installed with FastAPI), not pytest-asyncio.
- **Tests are checked by breaking the code:** disabling referral scoping made the four scoping tests fail.
