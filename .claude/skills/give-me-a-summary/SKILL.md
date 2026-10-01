---
name: give-me-a-summary
description: Summarize the Canyon State v2 repo as one short bulleted list covering what it is, the stack, the best features, security, data integrity, tests and CI, the Claude Code context files, deployment and known gaps. Use when someone asks for a summary, overview or tour of the repo, or types /give-me-a-summary.
---

# Give me a summary

Produce **one bulleted list** that tells a new reader (an engineer, a hiring manager, a collaborator)
everything worth knowing about this repo. Build it from the code as it is now, not from memory: the repo
changes daily, so anything stated has to be checked in the files.

## Output rules

- **Short lines.** One fact per bullet, ideally under 12 words. Cut filler ("This project uses...").
- **No important detail skipped.** Short beats long, but complete beats short.
- **Group under bold section labels**, in the order below. Use sub-bullets only for a list within a fact.
- **Specific over general:** "Argon2id, 64 MiB, 3 passes", not "secure hashing". Name versions.
- **Name the file** for anything a reader may want to check, as a markdown link (`[audit.py](api/app/audit.py)`).
- **Numbers are measured, not remembered:** count tests, endpoints and migrations from the files.
- **Honest:** placeholders, open questions and known gaps get their own section. Never oversell.
- Never mention real agency data, real people, or any employer or job this may be shown for.
- No intro paragraph and no closing summary. Just the lists.

## Headline first

Open with **Headline**: the 10 bullets a reader should remember if they read nothing else. Write it last,
after the full list, picking the strongest and most distinctive facts (what it is, the stack, the access
model, sign-in, the audit trail, tests and CI, the typed client, the Claude Code setup, the live demo, the
one gap that matters most). Each headline bullet still names a specific, not a category.

Then the full list, under the sections below.

## Sections, and where to look

Read each source before writing its section. Skip a bullet only if the thing doesn't exist.

1. **What it is**: purpose, users (admins, reps), the problem it solves. `CLAUDE.md`, `DECISIONS.md` top.
   Mention it rebuilds a Vue v1 and why that matters (same product, new stack).
2. **Stack**: every layer with its version.
   - API: `api/pyproject.toml` (FastAPI, SQLAlchemy 2 async, asyncpg, Alembic, Pydantic, Inngest, Python, uv).
   - Web: `web/package.json` (Next.js, React, TypeScript, Tailwind, shadcn/ui, TanStack, Playwright).
   - Database: Postgres version from `.github/workflows/ci.yml` or `DEPLOY.md`.
3. **Architecture**: how the pieces talk.
   - The browser never calls the API; Server Components and Server Actions do (`web/CLAUDE.md`).
   - TypeScript client generated from FastAPI's OpenAPI schema; CI fails if it's stale.
   - Business rules in plain modules (`pipeline.py`, `progress.py`), routes kept thin.
4. **Best features**: what a user sees. Walk `web/src/app/(app)/` for pages and `DECISIONS.md` headings.
   Pipeline board, saved views, inline edit, progress vs goals, top partners, activity timeline,
   notifications, change history, Team page, and anything newer.
5. **Security**: read `api/app/auth.py`, `security.py`, `routers/auth.py`, `routers/team.py`, `policy.py`,
   `scoping.py`, `config.py`, `.claude/rules/access-control.md`. Cover:
   - Access enforced in the API only; someone else's record is a 404, not a 403.
   - Sessions: token hashed at rest, lifetimes, idle timeout, revocation triggers, cookie name and flags.
   - Passwords: algorithm and parameters, NIST rules, timing-safe unknown-email path.
   - Rate limits: per account and global, values.
   - One-time setup and reset links; admins never see passwords.
   - Masked (blocked) fields, response schemas as an allowlist, dev header off unless configured.
   - Input validation: `extra="forbid"`, length and range limits, `Literal` sort keys, LIKE escaping.
   - Jobs endpoint signed and absent unless configured; secrets kept out (hooks, `.env.example`).
6. **Data integrity and correctness**: `api/CLAUDE.md`, `db.py`, `audit.py`, `models.py`, migrations.
   - Automatic soft delete; partial unique indexes on live rows.
   - Append-only audit trail (trigger), redacted fields, bulk writes refused.
   - Money as `Decimal`/`Numeric`; NULL premium means "not quoted".
   - Agency time zone for "today"; `FOR UPDATE` locks on pipeline moves; idempotent jobs.
7. **Tests and CI**: count tests (`grep -c "def test_\|async def test_"` across `api/tests`, Playwright specs
   in `web/`). Name the access matrix and its guard. List each CI job in `.github/workflows/ci.yml`.
   If a check isn't in CI (a linter, a type checker), say so in the gaps section.
8. **Claude Code setup** (the context and rules files):
   - `CLAUDE.md` files (root, `api/`, `web/`) and what each holds.
   - `.claude/rules/*.md`: one bullet each, saying when it loads and what it enforces.
   - `.claude/skills/*`: one bullet each (including this one).
   - `.claude/hooks/*` via `.claude/settings.json`: what each hook blocks or flags.
9. **Docs**: `DECISIONS.md` (dated decision log; count its sections), `DEPLOY.md`, any README.
10. **Deployment**: `DEPLOY.md`, `render.yaml`. Hosts for web, API and database; synthetic data only;
    nightly reseed; anything keeping the demo warm.
11. **Placeholders and known gaps**: grep for `PLACEHOLDER`, `TODO`, "open" items in `DECISIONS.md`,
    and checks missing from CI. Each as a plain, short bullet.

## Before answering

- Re-read your list once and cut every word that doesn't carry a fact.
- Check every number and version against the file you got it from.
