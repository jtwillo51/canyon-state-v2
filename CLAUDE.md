# Canyon State v2

Referral-partner reporting for a small Arizona insurance agency (Canyon State Insurance): which referral
partners (realtors, lenders, advisors) send business, how it closes, and how each rep is doing against goal.
A rebuild of an earlier Vue prototype (v1, kept in a separate private repo) on the stack below.

## The bar

**This is meant to be the best-built code its owner has ever shipped:** a portfolio piece that experienced
engineers will read closely. Hold every change to that standard:

- **Security first.** Least privilege, access enforced and tested on the server, nothing sensitive leaves the
  API unless a schema names it, no secrets or real data in the repo. When in doubt, choose the safer design.
- **The best UI we can make:** fast, accessible, consistent with the design system, and specific in its words.
- **Correct and proven:** rules have tests that fail when the rule breaks; edge cases (time zones, money,
  soft deletes, concurrent edits) are handled on purpose, not by luck.
- **Readable and explained:** small focused modules, comments that say *why*, and a decision log a reviewer
  can follow. Knowing what not to build is part of the craft; say so in `DECISIONS.md`.
- **No shortcuts that would embarrass it in review.** If something is a placeholder, it's labeled as one.

| Folder | What | Its context file |
|---|---|---|
| `api/` | FastAPI + SQLAlchemy 2 (async) + Postgres 17 + Alembic, Python 3.12, managed with **uv** | `api/CLAUDE.md` |
| `web/` | Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4 + shadcn/ui | `web/CLAUDE.md` |
| `DECISIONS.md` | The decision log: what was decided and why. **Read the relevant section before changing a rule.** | |

Also in `.claude/`: **rules** that load when you touch matching files (`rules/access-control.md`,
`migrations.md`, `ui-design.md`, `e2e-tests.md`), **skills** for repeated workflows (`add-endpoint`,
`add-migration`, `give-me-a-summary`), and **hooks** (`settings.json`) that block access to secrets and real data and flag a
stale API client.

## Working agreements

- **This is a learning project.** The owner is learning Next.js, FastAPI and Python by building it. Before a
  decision (a library, a data rule, a UI pattern), lay out the options briefly with a recommendation and
  **wait for their choice**. Explain what new commands and files do. Don't pick defaults silently.
- **Don't guess business rules.** What counts as "closed", how close rate is measured, who sees what: if
  `DECISIONS.md` doesn't settle it, ask. Unanswered agency questions are tracked outside this repo
  (cited in code and docs as "FIELD_QUESTIONS #n").
- **Record decisions.** When something is decided, add it to `DECISIONS.md` under a dated section.
- **Commit only when asked.** End commit messages with the Co-Authored-By line the session provides.

## Rules that must never break

1. **Synthetic data only in the repo.** Real agency data (people, partners, clients) never enters code,
   seeds, tests, fixtures, screenshots, commits or the deployed demo. The seed (`api/scripts/seed.py`) is
   fictional and deterministic. A hook blocks access to any `private-data/` folder.
2. **The API is the authority on access.** Every rule about who may see or change what is enforced in `api/`,
   and tested there. The web app only mirrors rules to decide what to *show*; never rely on it to protect data.
3. **Every endpoint is in the access matrix** (`api/tests/test_access_matrix.py`); a guard test fails otherwise.
4. **Every write is audited.** Change data through ORM objects (or `audit.audited_insert`); bulk
   UPDATE/INSERT/DELETE statements on audited tables are refused, and raw SQL writes aren't used in `app/`.
5. **Secrets stay out:** `.env` files are git-ignored and edited by the owner only (a hook blocks edits).
   Change `.env.example` and say what to set.

## Running it (Windows; commands work from Git Bash or PowerShell)

```bash
# once: databases canyon_dev, canyon_test, canyon_e2e (uses api/.env)
cd api && uv run python -m scripts.create_databases
cd api && uv run alembic upgrade head && uv run python -m scripts.seed   # dev data
cd api && uv run fastapi dev app/main.py                                 # API on :8000 (docs at /docs)
cd web && npm run dev                                                    # web on :3000
```

Background jobs (Inngest) run locally against a second API instance with jobs on:

```bash
cd api && uv run python -m scripts.dev_with_jobs                          # API with jobs on :8200
npx inngest-cli@1.45.1 dev --no-discovery -u http://localhost:8200/api/inngest   # dashboard on :8288
cd api && uv run python -m scripts.run_jobs                               # or: run both jobs once, no Inngest
```

Signing in locally: seeded people have no passwords (use **View as**), or give someone a link:
`cd api && uv run python -m scripts.make_link dana@example.test` prints a one-time setup link.

`.claude/launch.json` in the parent folder has preview configs for all of these servers. If `uv` isn't on PATH, it's at
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*\uv.exe`.

## Checks before calling work done

| What changed | Run |
|---|---|
| Anything in `api/` | `cd api && uv run pytest` (≈15 s; needs local Postgres) |
| An API schema, model or route | the API running, then `cd web && npm run gen:api && npm run typecheck` |
| Anything in `web/` | `cd web && npm run typecheck && npm run lint` |
| Behavior a user sees, or who sees what | `cd web && npm run e2e` (starts its own servers and database; set `UV` if uv isn't on PATH) |

CI (`.github/workflows/ci.yml`) runs all of the above on every push to `main` and every pull request,
including a check that the committed API client matches the API. Keep it green.

A test that has never failed proves little: when adding a rule's test, break the rule once and watch it fail.
