# Canyon State v2

Referral-partner reporting for a small Arizona insurance agency. It shows which partners (realtors, lenders,
financial advisors) send business, how that business closes, and how each rep is doing against goal.

Next.js on the front, FastAPI and Postgres behind it, Inngest for scheduled work. **All data in this repo is
synthetic**: fictional people, partners and clients from a deterministic seed.

> **Live demo:** not deployed yet. [DEPLOY.md](DEPLOY.md) has the steps (Neon, Render, Vercel).

## What it does

- **Pipeline board:** drag referrals through referred → contacted → quoted → bound, or to lost. Each step
  records which rep did the work.
- **Referrals and partners lists:** filters, multi-column sort and paging, all kept in the URL, plus private
  saved views.
- **Inline editing** on records, with a read-only reason shown when you can't change a field.
- **Progress dashboard:** clients, sales and close rate against monthly goals, compared with last month and
  with the rest of the team.
- **Top partners** over the last 12 months, year to date, or all time.
- **Activity timeline:** log calls, emails and meetings on a referral.
- **Notifications:** a nudge when a referral goes 14 days untouched, and a weekly digest.
- **Change history** on every referral and partner, read from the audit trail.
- **Team page:** admins add people, send one-time setup and reset links, and deactivate accounts.

Two roles: **admins** see everything; **reps** see the referrals they're credited on, and never colleagues'
dollars.

## Stack

| Layer | Choice |
|---|---|
| API | Python 3.12, FastAPI, Pydantic 2, managed with [uv](https://docs.astral.sh/uv/) |
| Database | Postgres 17, SQLAlchemy 2 (async, asyncpg), Alembic migrations |
| Background jobs | Inngest (Python SDK) |
| Web | Next.js 16 (App Router), React 19, TypeScript, Tailwind 4, shadcn/ui, TanStack Table |
| API client | Generated from FastAPI's OpenAPI schema with openapi-typescript |
| Tests | pytest against real Postgres, Playwright in the browser |
| CI | GitHub Actions |

## How it fits together

```
browser ──▶ Next.js (Server Components read, Server Actions write) ──▶ FastAPI ──▶ Postgres
                                                                          ▲
                                                Inngest (cron) ───────────┘  /api/inngest, signed
```

- **The browser never calls the API.** The Next server does, so the API needn't be public and there is no CORS.
- **One contract.** The TypeScript types are generated from the API's OpenAPI schema; CI fails if the
  committed client is out of date.
- **Thin routes, plain rules.** Business rules live in ordinary modules ([pipeline.py](api/app/pipeline.py),
  [progress.py](api/app/progress.py)) that tests call directly.
- **Database models and API schemas are separate classes**, so a column leaves the API only if a response
  schema names it.

## Security

- **The API is the only authority on access.** Every endpoint, for each of four viewers (nobody, owner, another
  rep, admin), has a pinned status in [test_access_matrix.py](api/tests/test_access_matrix.py), and a guard
  test fails if an endpoint is missing from it.
- **Someone else's record is a 404**, not a 403, so its existence isn't confirmed.
- **Passwords:** Argon2id (64 MiB, 3 passes, 4 lanes). NIST 800-63B rules: 15+ characters, no composition
  rules, common words and the person's own name refused. An unknown email still runs a hash check, so timing
  doesn't reveal who has an account.
- **Sessions:** 256-bit tokens stored only as SHA-256, in an httpOnly, Secure, `__Host-` cookie. They end after
  12 hours, after 2 idle hours, or on sign-out, password change, reset or deactivation.
- **Rate limits:** 5 failed sign-ins per account per 15 minutes, and a global ceiling of 100 per 5 minutes
  against password spraying. Every failure gets the same message.
- **No admin ever sees a password.** New people and forgotten passwords get one-time links (48 hours).
- **Validated input:** query models refuse unknown parameters, sort keys come from a fixed list, strings and
  numbers are bounded, money is `Decimal`, and search escapes LIKE wildcards. No hand-built SQL.

## Data integrity

- **Audit trail on every table**, written in the same transaction as the change ([audit.py](api/app/audit.py)).
  A database trigger makes it append-only, bulk writes that would skip it are refused, and personal data is
  recorded as "changed", never copied.
- **Soft delete is automatic:** a session hook hides deleted rows from every query; uniqueness uses partial
  indexes on live rows.
- **Money is `Decimal`/`Numeric`.** A premium is NULL until quoted, so "not quoted" never reads as $0.
- **"Today" is Arizona's date**, not the UTC server's.
- **Pipeline moves lock the row**, so two people moving the same card can't both win.
- **Jobs are idempotent:** every notification has a dedupe key, so retries add nothing.

## Running it locally

Needs Python 3.12 with uv, Node 24 and Postgres 17. Copy [api/.env.example](api/.env.example) to `api/.env`
and set your database password.

```bash
cd api && uv run python -m scripts.create_databases                      # canyon_dev, canyon_test, canyon_e2e
cd api && uv run alembic upgrade head && uv run python -m scripts.seed   # schema and synthetic data
cd api && uv run fastapi dev app/main.py                                 # API on :8000, docs at /docs
cd web && npm install && npm run dev                                     # web on :3000
```

Use **View as** in the header to switch between an admin and a rep and watch the scoping change.

## Tests

```bash
cd api && uv run pytest     # 313 tests against a real Postgres, each in a rolled-back transaction
cd web && npm run e2e       # Playwright: starts its own API, web server and database
```

CI runs the API tests, web lint, typecheck and build, an API-client sync check, and the browser tests on every
push and pull request ([ci.yml](.github/workflows/ci.yml)).

## Repo layout

| Path | What |
|---|---|
| [api/](api/) | FastAPI app (`app/`), migrations, tests, scripts (seed, one-time links, jobs) |
| [web/](web/) | Next.js app, generated API client, Playwright tests |
| [DECISIONS.md](DECISIONS.md) | The decision log: what was decided and why, by date |
| [DEPLOY.md](DEPLOY.md) | Deploying the demo on Neon, Render and Vercel |
| `CLAUDE.md`, `.claude/` | Context, rules, skills and hooks for Claude Code (see below) |

## Built with Claude Code

This repo is set up for AI-assisted development, with guardrails:

- **Context files** ([CLAUDE.md](CLAUDE.md), [api/CLAUDE.md](api/CLAUDE.md), [web/CLAUDE.md](web/CLAUDE.md)) hold
  the conventions and the rules that must never break.
- **Rules** in [.claude/rules/](.claude/rules/) load when matching files are touched: access control,
  migrations, UI design, browser tests.
- **Skills** for repeated work: adding an endpoint end to end, a safe migration, and a repo summary.
- **Hooks** block reading anything under `private-data/` or editing `.env` files, and flag a stale API client
  or a missing access-matrix row after an API change.

## Known gaps

- **Close rate** has a placeholder definition until the agency confirms how it measures it.
- Notifications are in the app only; email is planned.
- Python linting and type checking (ruff, mypy) aren't in CI yet.
- A few text fields trim spaces after the length check, so a name of only spaces is accepted.
