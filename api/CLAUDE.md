# API (FastAPI)

Run everything from `api/` with `uv run …`. Layout is a flat `app/` package:

| File | Holds |
|---|---|
| `main.py` | the app, router registration, `/health` |
| `auth.py` | `Viewer` (who is asking) and `is_admin` |
| `scoping.py`, `routers/referrals.py:visible_referrals` | what each viewer may see |
| `policy.py` | blocked (masked) fields |
| `models.py` | SQLAlchemy tables; fixed lists as `Literal` types |
| `schemas.py` | Pydantic request/response shapes (separate from models on purpose) |
| `pipeline.py`, `progress.py` | the business rules for moving referrals and for progress/goals |
| `errors.py` | `FieldError(message, field)` → 422 `{message, field}` |
| `clock.py` | `agency_today()`: the agency's date (America/Phoenix) |
| `routers/` | one module per resource |
| `jobs/` | Inngest background jobs: `functions.py` (schedules, steps), `stale.py` and `digest.py` (logic), `endpoint.py` (/api/inngest) |

## Conventions

- **Every endpoint that touches data takes `viewer: Viewer`.** Referral queries start from
  `visible_referrals(viewer)`, which both scopes and preloads relationships (async can't lazy-load).
- **Someone else's record is a 404, not a 403**, so its existence isn't confirmed.
- **Refusals the UI shows next to a field are `FieldError`** (422 `{message, field}`), including "only admins
  can …". Raise it anywhere; one handler formats it.
- **Soft delete is automatic.** A session hook adds `deleted_at IS NULL` to every ORM query. To see deleted
  rows, opt in with `execution_options(include_deleted=True)`. Uniqueness uses partial indexes on live rows.
- **Money is `Decimal`/`Numeric`, never float.** `premium` is NULL until quoted, so "not quoted" never reads as $0.
- **Dates:** "today" is `agency_today()`, never `date.today()` (a UTC server is already tomorrow by 5 pm in Arizona).
- **Partial updates act on `model_fields_set`:** `null` clears a field, omitting it leaves it alone.
- **Response models name every field that leaves the API.** A column reaches the browser only if a schema lists it.
- After changing schemas or routes, regenerate the web client (see the root CLAUDE.md).

## Background jobs (`app/jobs/`)

- **Logic in plain async functions, Inngest in thin wrappers.** Tests call the logic directly; `functions.py`
  only adds schedules, retries and steps. Step results must be JSON (Inngest stores and replays them).
- **Idempotent in the database:** every notification has a `dedupe_key` under a live unique index, and inserts
  use `ON CONFLICT DO NOTHING`, so retries and repeat runs add nothing.
- **Schedules use the agency's clock** (`TZ=America/Phoenix` in the cron), and "today" is the first step so a
  retry after midnight works on the same day.
- **/api/inngest exists only when configured** and is left out of the OpenAPI schema (the matrix guard's one
  reviewed exception); `tests/test_jobs.py` proves it refuses unsigned requests.
- The Inngest SDK is pre-1.0 and **pinned exactly** (`inngest==0.5.19`). Read its source in `.venv` before
  relying on an API; older examples online won't match.

## Tests (`uv run pytest`)

- Run against a real Postgres database, `canyon_test`, migrated with Alembic at the start of each run. Each test is
  one transaction that's rolled back. `conftest.py` refuses any other database.
- The `world` fixture is a tiny agency: Dana (admin), Tessa and Jordan (reps), one partner, one referral each.
  Build extra rows in the test itself; don't use the seed.
- `as_user(world.tessa)` makes the dev header; requests go through the `api` fixture.
- `test_access_matrix.py` lists every endpoint × {nobody, owner, other rep, admin} → status. Content that
  differs by viewer (lists, board, progress) needs its own test, because the matrix only sees status codes.
