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
- **Tests are checked by breaking the code (see below):** disabling referral scoping made the four scoping tests fail.

## Typed client (2026-09-29)

- **openapi-typescript + openapi-fetch.** One generated file of types (`web/src/lib/api/schema.d.ts`), no
  generated runtime code; openapi-fetch (~6 kB) checks paths, params and responses against it. A typo'd
  path, a missing path param, or using `premium` without handling `null` are compile errors.
- **Generated from the running API:** `npm run gen:api` reads `http://localhost:8000/openapi.json`, so the
  API must be up. **`schema.d.ts` is committed** so the web app builds without the API running (and on
  Vercel). Regenerate after any API change.
- **The client is server-only** (`import "server-only"` in `web/src/lib/api/client.ts`): it holds `API_URL`
  and the dev viewer header, and importing it from a Client Component fails the build. `types.ts` gives the
  shapes friendly names (`Partner`, `Referral`) and is safe to import anywhere.
- The Python `Literal` lists now reach the browser (see below): one definition drives the CHECK constraint, API
  validation, the OpenAPI schema and the TypeScript unions.

## Stage 1 pages (2026-09-29)

- **"View as" is a cookie set by a Server Action** (`web/src/app/actions.ts`). Server Components read it
  with `cookies()` and call the API as that user (`web/src/lib/viewer.ts`). The cookie is `httpOnly`, so
  browser JavaScript can't read it; the API still decides what that user may see. Stage 3 swaps it for a
  real session. The people come from a dev-only `GET /dev/users` (404 unless `DEV_AUTH` is on).
- **UI: shadcn/ui on Tailwind.** Component source is copied into `web/src/components/ui/` and owned by the
  repo. Its class-merging helper is shadcn's new `cn` npm package (verified: published by shadcn, source at
  github.com/shadcn-ui/cn, no install scripts).
- **Lists are plain server-rendered tables** with no client JavaScript; sorting, column picking and saved
  views come with TanStack Table in Stage 2. The only Client Component is the "View as" select (it submits
  on change).
- **Routes:** `/partners`, `/partners/[id]` (details, "do not discuss", production, the viewer's referrals for
  that partner), `/referrals`, `/referrals/[id]` (policy, client, step timeline). `/` redirects to
  `/partners`. An API 404 (including someone else's referral) renders Next's not-found page.
- **Dates from the API ("YYYY-MM-DD") are formatted from their parts**, never `new Date(string)`, which
  reads them as UTC midnight and shows the previous day in Arizona.
- **The browser never calls the API:** verified in the network log (no requests to :8000).

## Pipeline (2026-09-29)

v1 never moved a referral between statuses (status was set at creation), and "what counts as closed" is
still open with the agency (FIELD_QUESTIONS #1). These rules are decided for the app and live in
`api/app/pipeline.py`, tested in `api/tests/test_pipeline.py`:

- **Moves:** forward one or more steps (referred → contacted → quoted → bound, skipping allowed); any open
  referral can be marked lost. Moving backward, or reopening a bound or lost referral, is **admin-only**
  because it rewrites credit.
- **Credit:** every step passed on the way forward credits one rep: the person moving it, or, when an admin
  moves it, a rep the admin must name (an admin can't credit an admin). Reps can only credit themselves.
  Moving backward soft-deletes the credits for steps past the new status. Reopening a lost referral keeps
  the credits it already had.
- **Required data:** quoted needs a premium (an existing one counts); bound needs a premium and a bind date
  between the referral date and today. Moving back below quoted clears the premium (NULL = not quoted).
- **A refused move changes nothing:** `apply_move` validates everything before touching the referral; the
  API answers 422 with `{message, field}` so the UI can point at the field.
- **Concurrent moves:** the referral row is locked (`SELECT … FOR UPDATE`) for the length of the move.
- **New column `referrals.lost_date`** (migration 2): the board needs "lost in the last 30 days", and
  `updated_at` changes on any edit. Referrals lost before the column existed have none. The seed derives it
  from each referral's id so the random generator (and every id) stayed stable.
- **"Today" is the agency's today** (`America/Phoenix`, `app/clock.py`), not the server's: a UTC server is
  already on tomorrow by 5 pm in Arizona.
- **The board (`GET /referrals/pipeline`)** shows open referrals plus those bound or lost in the last 30
  days, scoped like every referral query.

## Pipeline board UI (2026-09-29)

- **Writes go through Server Actions** (`web/src/app/pipeline/actions.ts`), which call the API as the
  viewer through the same server-only client, then `refresh()` the page. The browser still never calls the
  API. Server Actions are public endpoints, which is fine because they only forward to the API, which
  enforces every rule.
- **`useOptimistic`** moves the card the moment it's dropped; a refused move snaps back and shows the
  API's own message.
- **Drag and drop: `@dnd-kit/core` 6.3** (stable; the newer `@dnd-kit/react` is pre-1.0). Keyboard dragging
  and screen-reader announcements (by client name) are on.
- **The browser mirrors the rules only to decide what to ask** (`web/src/lib/pipeline.ts`): a dialog asks
  for the premium (prefilled if known), the bind date (defaults to the agency's today), and, for an admin's
  forward move, which rep did the work. The API stays the authority; a rep's backward drag goes straight to
  it and comes back refused.
- **New API endpoints:** `GET /users/me` (who the API thinks is asking; the board needs the role) and
  `GET /users/reps` (the admin's rep picker; `/dev/users` can't be used because it disappears in production).
- **React 19 resets a form after its action runs.** Remounting with a `key` tied to the viewer keeps the
  "View as" select (and the board's leftover error state) in step with who is viewing.

## Activity timeline (2026-09-29)

- **v1's rules carry over:** anyone who can see a referral can log a touch on it; it records who made
  contact (any active team member, since people log on a colleague's behalf), a date between the referral date
  and today, a method (the agency's three: In person, Phone, Email) and notes up to 2,000 characters.
  **Activities never change steps or credit.**
- **One `activities` table with typed parents** (migration 3): `referral_id` and `partner_id` are real
  foreign keys, and a CHECK (`num_nonnulls(...) = 1`) makes the database require exactly one. Referral
  activity now; partner visits later need no new table. Chosen over a generic `entity_type/entity_id`, which
  can't be a foreign key.
- **`logged_by_id` alongside `rep_id`:** who typed it vs who made contact. Shown as "Logged by …" when they
  differ; the seed of an audit trail.
- **The timeline merges** logged activity with pipeline milestones (referred, each credited step, lost) into
  one newest-first stream, built in the web app from data it already loads. Nothing is stored twice.
- **One error shape for the whole API:** raise `FieldError(message, field)` anywhere; one handler turns it
  into 422 `{message, field}` (`app/errors.py`). `PipelineError` is now a `FieldError`.
- **`GET /users`** lists the active team for "who made contact" (admins included).
- **The log form uses `onSubmit` + a transition, not `<form action>`:** React 19 resets a form after its
  action even when the save fails, which would wipe what was typed. The form clears only on success and
  marks the failing field `aria-invalid`.
- **Seeded activity uses its own random generator**, so adding it didn't shift any existing id.

## Saved list views (2026-09-29)

- **The URL is the list's state:** filters, sort, visible columns and page (`/referrals?status=quoted,bound&
  stale=30&sort=-premium&cols=…&page=2`). A view is a link; Back works. The page is a Server Component that
  reads the URL and asks the API; the interactive pieces only ever change the URL.
- **The API filters, sorts and pages** (`GET /referrals` takes a `ReferralQuery` model as its query string,
  unknown keys refused, and returns `{items, total, limit, offset}`). Scoping applies to the count as well
  as the page, so a rep can't learn agency-wide totals; a test proves it (and caught its removal).
  50 rows per page. Search escapes LIKE wildcards. Premium sorts put "not quoted" last both ways.
- **`last_touch`** (latest of referral date, live step credits, live activity) is a SQL `column_property`,
  always current. **"Stale N days" = open and last touch N+ days ago**, v1's definition.
- **Built-in views** (in the web app, as query strings): All, Open referrals, Stale 30+ days, Bound this month
  (Arizona month), Lost after quoting (lost with a premium on file).
- **Saved views** (migration 4, `saved_views`): private to their owner; name unique per person among live
  views; the stored query is restricted to plain `key=value` characters, so it can only ever become a link
  to this list. Shown as tabs; "Save view" appears when the current URL matches no view.
- **TanStack Table v9** (`useTable`, features opted in with `tableFeatures`), read from the docs shipped in the
  package since v9 differs from v8 tutorials. Sorting is manual (the API sorts all rows, not one page) and
  both sorting and column visibility are controlled by the URL.
- **Error-path hygiene:** after a failed insert the endpoint rolls the session back before raising, so the
  session is never left unusable.
- Redundant index dropped in review: the unique `(user_id, list, name)` index already serves lookups by user.

## Partners list (2026-09-30)

- **Partner facts plus referral numbers** for a period (last 12 months by default; year to date; all time):
  referrals, bound, close rate, bound premium, last referral date. Sortable, filterable (type, primary rep,
  unassigned, do-not-contact, no referrals in the period, name/business search), paged, with built-in views
  (Most bound, Best close rate, No referrals in 12 months, No primary rep) and saved views.
- **v1's visibility rule for numbers: counts are team-wide, money is scoped.** Every rep sees how many
  referrals and binds a shared partner produced; a rep's bound premium counts only referrals they're
  credited on, and the column says "Your bound premium". A test pins it (and caught its removal).
- **Close rate = bound ÷ referred, by count** among referrals referred in the period. A placeholder until the
  agency answers FIELD_QUESTIONS #2; labeled as such in the code and under the table.
- **One aggregate query:** a `GROUP BY partner` subquery over referrals using Postgres `FILTER (WHERE …)` for
  the per-period counts, left-joined to partners so partners with no referrals still appear with zeros.
- **Shared list building blocks** (`components/list/`: `DataGrid`, `ViewTabs`, `Chips`; `lib/list-views.ts`),
  used by both lists; each list only defines its columns, URL parsing and built-in views. Scoping helpers
  moved to `app/scoping.py` and LIKE-escaping to `app/search.py`, shared by both routers.

## Inline edit (2026-09-30)

- **Partner (`PATCH /partners/{id}`):** anyone may change do-not-contact, the "do not discuss" note and the
  territory; only admins reassign the primary rep (to an active rep, or null to unassign). v1's rules, plus
  territory for anyone (a shared fact; v1 never covered it).
- **Referral (`PATCH /referrals/{id}`):** line of business, carrier and premium. Anyone who can see the
  referral may edit before bind; **once bound, admins only**, because carrier and line set the commission rate
  and premium is the revenue. Premium exists from quoted on; it can't be set on a referral that hasn't been
  quoted (that happens through the pipeline move). Status changes stay on `/status`.
- **Partial updates honor "not sent" vs "null":** endpoints act only on `model_fields_set`, so
  `"primary_rep_id": null` unassigns while omitting it leaves it alone. Unknown fields are refused.
- **`GET /carriers`** feeds the carrier picker.
- **One error shape, including FastAPI's own validation:** schema errors (e.g. premium ≤ 0) also answer
  `{message, field}`, with FastAPI's standard `detail` kept so the documented schema holds.
- **UI:** a reusable `InlineField` (text, note, number, select): pencil to edit, Enter or ✓ saves, Escape
  cancels; the new value shows optimistically and, if refused, the editor reopens with what was typed and the
  API's reason. Fields the viewer can't change say why ("admins change this"). Edits live on the partner and
  referral pages; the lists stay read-only for now.

## Public demo deployment (2026-09-30)

- **A labeled demo on synthetic data, before real sign-in.** `DEMO_MODE` keeps the "View as" switcher (so a
  visitor can flip between an admin and a rep and watch scoping work), shows a "fictional data, resets
  nightly" banner, and lets the seed script run against the hosted database. Real sign-in is Stage 3; demo
  mode must never point at real data.
- **All free:** Neon Postgres (doesn't expire), Render free web service for the API (sleeps after 15 idle
  minutes; about a minute to wake), Vercel for the web app. Steps in `DEPLOY.md`.
- **Neon URLs work as pasted:** `postgresql://…?sslmode=require` becomes `postgresql+asyncpg://` with
  `ssl` in `connect_args` (asyncpg rejects libpq options); a pooler host disables asyncpg's prepared-statement
  cache. Tested in `tests/test_config.py`.
- **Migrations run in Render's build step** (the free plan has no pre-deploy step).
- **Nightly reseed via a scheduled GitHub Actions workflow** (free; Render cron jobs aren't), using the
  `DEMO_DATABASE_URL` secret. It undoes visitors' changes and keeps "last 30 days" current.
- The viewer cookie is `Secure` in production (HTTPS only).

## Progress and goals (2026-09-30)

- **Three numbers, this month so far:** **clients** = referrals bound; **sales** = their bound premium; both
  credited to the rep with the **bind** credit, so reps' totals add up to the company's. **Close rate** = of
  referrals **decided** this month (bound or lost), the share bound, credited to the rep who **introduced**
  them. Close rate stays a placeholder until FIELD_QUESTIONS #2.
- **"Vs last month" compares the same span:** on the 29th, 1-29 September vs 1-29 August (capped at a short
  month's end). **"Vs everyone"** = the average of the *other* active reps (reps with no close rate yet are
  skipped for that average).
- **Goals:** each rep has monthly clients and sales goals (carry over until changed); the company's goal is
  their sum. Close rate has one company target (a rate doesn't add up). Admins edit goals inline on the
  dashboard; the API refuses anyone else. Migration 5: `rep_goals`, and `company_goals` constrained to one row.
- **Who sees what (`GET /progress`):** admins get company totals and every active rep. A rep gets only their own
  row and the company as **shares of goal** (`company_share`), never company or colleagues' counts or
  dollars. Their sales-vs-team arrives only as a percentage (`vs_team_pct`); a test pins it (and caught
  its removal).
- **Where:** a new **Dashboard** (`/`, `/dashboard`) and a **compact, collapsible strip** under the nav on every
  page. A **"vs myself / vs everyone" switch** picks the one comparison shown beside each number, on both,
  shared live and remembered per person (cookies). Company totals always compare with last month; the
  company has no "everyone", so the admin strip has no switch.
- ▲ green = better, ▼ red = worse, – = level; close rate moves in points.
- Seeded goals are sized so the synthetic agency sits near 100% (some reps ahead, some behind).

## Table sorting everywhere (2026-09-30)

- **Every table uses the shared `DataGrid`:** click a header to sort (click again to flip), shift-click
  another to add it as the next sort, up to 3, with 1/2/3 markers.
- **Paged lists** (Referrals, Partners, Top partners) sort in the API: `sort` is a list (each column once, at
  most 3; `app/sorting.py`), carried in the URL as `sort=-close_rate,-referrals` (saved views keep working).
  **Top partners re-ranks** by the clicked columns. **Small tables** (dashboard reps, a partner's referrals)
  sort in the browser ("local" mode).

## Top partners (2026-09-30)

- **Its own page** (`/top-partners`): the top 10 referral partners ranked by **close rate, then number of
  referrals**, over the last 12 months (switchable: year to date, all time), using the Partners list's
  close-rate definition (bound ÷ referred, a placeholder).
- **Only partners with 3+ referrals in the period are ranked**, so one lucky bind can't put a partner on top.
- **Every partner sort now breaks ties on more referrals, then name** (`GET /partners`), so "close rate, then
  referrals" is simply `sort=-close_rate`; plus a `min_referrals` filter. Tests pin both (and caught the
  tie-break's removal).
- Columns: rank, partner, primary rep, referrals, bound, close rate, bound premium. Counts are team-wide;
  premium follows the existing rule ("Your bound premium" for reps).

## Visual design (2026-09-30)

- **Direction: "A3 copper".** Chosen from mockups of three directions (classic CRM, Sonoran brand, modern minimal),
  then four variations on the classic CRM (a tidied Salesforce shell, "copper state", a global header with
  scoreboard, an icon rail with bullet charts). The pick: the global header and scoreboard, in the copper-state
  colors.
- **Arizona's flag colors: blue for structure, copper for goals.** Flag blue (`--brand`, `#0b2349`) for the header
  and primary buttons, warm paper neutrals for the page. **Copper means "measured against a goal" and nothing
  else:** the active tab, the scoreboard's edge and goal meters, the chosen comparison. Links stay blue. Holding
  copper to one meaning is what lets it carry meaning.
- **Type: IBM Plex Sans for words, IBM Plex Mono for numbers** (money, counts, rates, and every right-aligned
  table column), so figures line up like a scoreboard.
- **Navigation across the top, no sidebar,** so wide tables get the full width. The progress strip became a
  dark scoreboard band under it (still collapsible, still scoped: reps see the company only as a share of goal).
- **The theme lives in `globals.css`:** shadcn's variables point at the palette, plus named tokens (`brand`,
  `copper`, `link`, `up`, `down`, and their on-dark variants) usable as Tailwind classes (`bg-copper`).
  Smaller corners (`--radius` 0.375rem) for a crisper, denser look.
- **Shared `GoalMeter`** (`components/progress/goal-meter.tsx`): counts and money fill toward the goal; a rate
  is drawn on its own 0-100% scale with a tick at the target.
- **No search box in the header yet:** it was in the mockup, but a box that does nothing is worse than none. It
  arrives with the command palette.
- **Light mode only for now.** Dark mode is an open decision; shadcn's stock `.dark` block is still in
  `globals.css`, unused.

## Access tests (2026-09-30)

- **An access matrix covers every endpoint** (`api/tests/test_access_matrix.py`): each endpoint (and, where the
  rule depends on what's sent, each kind of request) is asked by four people: nobody, the owning rep, another
  rep and an admin, each with its expected status. 84 cases, each in its own rolled-back transaction.
- **A guard fails the build when an endpoint has no row,** so a new endpoint can't ship until someone decides
  who may call it. Deliberately public endpoints (`/health`, the dev-only `/dev/users`) are listed with a reason.
- **The guard reads the OpenAPI schema, not `app.routes`:** since FastAPI 0.14x, `app.routes` holds included
  routers as unexpanded wrappers, so the first draft of the guard saw no routes and passed. It now also fails
  on an empty or incomplete list, and a second check fails if `include_in_schema` ever appears in the app
  (a hidden endpoint would escape the guard).
- **Statuses in the matrix, contents in focused tests.** Endpoints everyone may call but whose contents are
  scoped (lists, the board, progress) are pinned by content tests; a leak there still answers 200. Added
  `test_board_is_scoped_like_the_list` (the board was only tested as an admin).
- **Checked by breaking the code:** leaking the board to every rep failed only the new board test (as
  designed: the matrix sees statuses); dropping the admin check on the company target failed its matrix rows;
  adding an unlisted endpoint failed the guard.

## Browser tests (2026-09-30)

- **Playwright** (`web/e2e/`, `npm run e2e`), Chromium only. The plan had it in Stage 3; pulled forward to check
  the UI agrees with the API's access rules.
- **Its own stack:** the API on :8100 against **`canyon_e2e`**, migrated and reseeded before the server answers
  (`e2e/start-api.mjs`, so the order doesn't depend on Playwright), and `next dev` on :3100. Dev data and
  running dev servers are never touched. Next 16 locks each output folder per server, so `distDir` is
  configurable (`NEXT_DIST_DIR=.next-e2e`); Next adds that folder's types to `tsconfig.json`, which is kept.
- **Dev mode, not a production build:** in production the viewer cookie is HTTPS-only and wouldn't be set on
  `http://localhost`.
- **First tests:** admin-only controls are shown to admins and absent for reps (goal editors, the reps table,
  primary-rep reassignment, bound-referral edits), a rep gets a 404 on someone else's referral, and the
  critical path: a rep drags a quoted referral to Bound, confirms, and sees it counted on the dashboard.
- Tests find records through the API and elements by accessible name; dashboard cards gained
  `role="group"` names for that (and for screen readers). Checked by breaking the code: showing the
  primary-rep editor to everyone failed its test.

## Working with Claude Code (2026-09-30)

- **Layered context:** a root `CLAUDE.md` (what, how to run, rules that must never break), `api/CLAUDE.md` and
  `web/CLAUDE.md` (conventions per app), and path-scoped rules in `.claude/rules/` that load only when matching
  files are touched (access control, migrations, UI design, e2e tests).
- **Skills for repeated workflows:** `add-endpoint` (contract → route → access matrix → tests → typed client →
  page) and `add-migration` (reviewed, reversible, seed ids kept stable). Rules hold conventions; skills hold steps.
- **Hooks** (`.claude/settings.json`, Node scripts in `.claude/hooks/`): block reading, searching or editing
  anything under `private-data` and editing `.env` files; after an API contract edit, remind Claude to
  regenerate the TypeScript client and, for a new endpoint, to add its access-matrix row. No format-on-save
  or tests-on-stop hooks (chosen against).

## CI (2026-09-30)

- **GitHub Actions on every push to `main` and every pull request** (`.github/workflows/ci.yml`), three jobs in
  parallel: **API** (pytest against a Postgres 17 service container), **Web** (lint, typecheck, production
  build, and the API client check), **E2E** (the Playwright suite on its own seeded database; the report and
  traces are kept as an artifact when a test fails).
- **The committed TypeScript client must match the API.** `api/scripts/export_openapi.py` writes the schema
  straight from the app (no server, no database); CI regenerates `schema.d.ts` from it and fails on any
  difference. Checked by adding a schema field without regenerating: the check failed.
- **Least privilege:** the workflow token is read-only (`permissions: contents: read`); no secrets are used;
  all data is synthetic. A newer push cancels the run it replaces.
- **Third-party actions are pinned to a commit SHA** (`astral-sh/setup-uv@<sha> # v10.2.0`): a tag can be
  moved to different code, a commit can't. GitHub's own `actions/*` stay on major tags. (The first run failed
  because setup-uv publishes no `v10` tag; the reseed workflow had the same bug and is fixed too.)
- **Node 24** (the current LTS line) in CI; local development happens to run Node 23.
- **`typecheck` runs `next typegen` first.** `PageProps`/`LayoutProps` are generated by Next into `.next/types`;
  a clean checkout has none until something generates them, so plain `tsc` failed in CI (reproduced locally
  on a fresh clone: 6 errors before, none after).
- The production build needs no API: every page renders per request, so nothing is fetched at build time.

## Background jobs: Inngest (2026-09-30)

- **Python SDK inside FastAPI** (chosen over the TypeScript SDK in Next.js): jobs run beside the data and reuse
  the same rules (`visible_referrals`, `agency_today`, `progress.tallies`), and no all-seeing service credential
  has to exist. The SDK is pre-1.0 (`inngest==0.5.19`), so it's pinned exactly and read from source.
- **Two jobs**, on the agency's clock (`TZ=America/Phoenix` crons):
  - **Stale referrals**, daily at 6:00 am: a referral is **stale when it's open and has had no touch in 14 days**
    (`last_touch`, the same measure as the list's Stale view). Every active rep credited on it gets a nudge.
  - **Weekly digest**, Mondays at 7:00 am: last week (Monday to Sunday) per person. A rep's holds only their own
    numbers; an admin's holds the company and every rep, the same split as the dashboard, from the same math.
- **Delivered in the app first** (email later, as a second channel): a `notifications` table (migration 6), a bell
  with the unread count in the header, and a Notifications page ("Needs attention", then "Weekly digests").
- **Notifications store references and numbers, never copied names.** A stale nudge holds the referral's id and
  is resolved at read time through the reader's own scoping, so it never outlives their access or names a client
  they can't see. It shows only while the referral is still stale **in the same spell**; once someone acts, it
  disappears, and going stale again later is a new nudge. Most overdue first.
- **Idempotent in the database, not just in Inngest:** a `dedupe_key` per person (`stale:<referral>:<last touch>`,
  `digest:<week start>`) under a live unique index, with `ON CONFLICT DO NOTHING`. A retried or double-fired
  run writes nothing new (tested; on the real Dev Server a second pass wrote 0).
- **Durable steps:** "today" is the first step (memoized, so a retry after midnight works on the same day); the
  digest runs one step per person, so one failure retries alone. The logic is plain async functions tested
  directly; the Inngest functions are thin wrappers, tested with a stand-in step runner that insists on JSON.
- **The endpoint Inngest calls (`/api/inngest`) is locked down:**
  - it exists only when configured (`INNGEST_SIGNING_KEY`, or `INNGEST_DEV` locally); otherwise it's a 404. The SDK
    *raises at startup* in production mode without a key, so mounting it unconditionally would have crashed the
    deployed API;
  - in production every request must be signed (tested: unsigned GET, POST and PUT all get 401), and unsigned
    re-registration is off (the SDK defaults it on);
  - `INNGEST_DEV` (no signing) is refused unless `DEV_AUTH` is on, so it can't be switched on for a deployed server;
  - it's left out of the OpenAPI schema so the API contract doesn't change with configuration: the access-matrix
    guard's one reviewed exception, listed in the test with where its security is tested instead.
- **Found and fixed on the way:** `Referral.last_touch`'s subqueries auto-correlated away when a query also joined
  step credits (SQLAlchemy removed the subquery's own table). They now `correlate_except` their own table.
- **`scripts/run_jobs.py`** runs both jobs once without Inngest. The e2e stack and the demo's nightly reseed call it
  after seeding, so there are notifications to show. The deployed demo doesn't run Inngest yet: connecting it to
  Inngest Cloud (a free account, keys set by the owner) is the next step.
- Tests: the matrix covers the three new endpoints; `test_jobs.py` and `test_notifications.py` cover the rules,
  idempotency, the visibility split and the endpoint's security. Checked by breaking the code: reading nudges
  without the reader's scoping, giving a rep the admin digest, and changing the dedupe key each run each failed
  their tests. Two browser tests cover the bell and the page for a rep and an admin.

## Audit trail (2026-09-30)

- **Captured automatically, for every table** (the log itself excepted): a SQLAlchemy `after_flush` hook
  (`app/audit.py`) records each insert, update and soft delete with before/after per field, in the same
  transaction as the change, so a change and its record commit or roll back together (a refused move leaves
  nothing; tested). Endpoints call nothing, so none can forget. New tables are covered without a change.
- **Actor:** the signed-in viewer (set in `get_viewer`), a job by name (`stale-referrals`), a script
  (`run_jobs`), or "system". Soft deletes read as "delete" and "restore". The seed script alone turns recording off.
- **Nothing skips it:** bulk `update()/insert()/delete()` statements on audited tables are refused at runtime;
  the jobs' many-row inserts go through `audit.audited_insert`, which records what it wrote, and "mark read"
  became an ordinary ORM change. A test also fails if `app/` contains raw SQL writes.
- **Sensitive values are never copied into the log** (client name, address and birthday; "do not discuss" notes;
  partner phone and email; user email; activity notes; notification payloads): the event says the field changed,
  not what it held. The log shouldn't become a second store of personal data. A test fails if a redaction rule
  names a column that doesn't exist (a typo would silently log the value).
- **Append-only, enforced by the database:** a trigger refuses UPDATE and DELETE on `audit_events`, and TRUNCATE
  unless the transaction sets `canyon.allow_audit_reset` (only the seed, which already refuses anything but
  localhost or the demo). With real data in production, the next step is a separate database role for the app
  without UPDATE/DELETE/TRUNCATE on the table, so even a compromised app can't rewrite history.
- **Visible to anyone who can see the record:** a "Change history" section (collapsed) on referral and partner
  pages. A referral's history (its changes, step credits and activity) follows referral access; someone else's
  is a 404. A partner's history is shared like the partner, but holds **only the partner's own changes**, never
  its referrals', which would reveal colleagues' clients. Ids read as names (reps, carriers), including people
  who've since been deactivated.
- **Found on the way:** `occurred_at` defaulted to `now()`, which in Postgres is when the *transaction* began:
  every event in one request shared a timestamp, so a history couldn't be ordered. It's `clock_timestamp()`
  (the moment of the write). Also: editing an already-applied migration needs every database re-migrated;
  `canyon_test` kept the old default until it was downgraded and upgraded again.
- Tests: `test_audit.py` (coverage, redaction, attribution, soft delete, jobs, bypass refusal, append-only,
  the seed's reset, history visibility and labels), matrix rows for both history endpoints, and a browser test
  that edits a partner inline and finds the change in its history. Checked by breaking the code: removing a
  redaction, allowing bulk bypass, leaking referral events into partner history, and dropping the actor each
  failed their tests.

## Real sign-in (2026-09-30)

- **Email and password, done right** (chosen over Google sign-in, which depends on the agency's accounts, and
  passkeys, the most work). Builds on v1's decision: accounts are managed by admins only, no self-signup.
- **Passwords:** Argon2id with RFC 9106's recommended profile (64 MiB, 3 passes), stated explicitly; rehashed at
  sign-in if settings strengthen. **NIST SP 800-63B rules:** at least 15 characters (the current minimum for a
  single factor), up to 128, anything printable, no composition rules, no forced rotation, and a check against
  predictable choices (common words, the agency's own name and places, the person's name or email).
- **Server-side sessions** (chosen over JWTs, which can't be revoked early): a 256-bit token in an httpOnly cookie
  (`__Host-session` in production: HTTPS only, this host only, whole site; SameSite=Lax). The API stores only its
  SHA-256, so a leaked database can't be used to sign in. A session ends after 12 hours (a workday), 2 idle hours,
  or at once on sign-out, "sign out everywhere", a password change or reset, or deactivation.
- **One-time links for passwords** (chosen over admin-set temporary passwords): an admin adds a person and gets a
  48-hour, single-use link to hand over; resets work the same way. Admins never see or choose a password. Making a
  new link voids the old one. The token rides in the URL's `#fragment` (never sent to a server, so it stays out of
  logs and Referer headers), is dropped from the address bar once read, and only its hash is stored.
- **Guessing is slowed** before any password is checked: 5 failures per account in 15 minutes (keyed by a hash of
  the email typed, so made-up emails pause the same way and a pause reveals nothing), and a global ceiling of 100
  failures in 5 minutes against password spraying (a real person may wait a few minutes during an attack).
  Every failure is the same message and takes about as long (a dummy hash is verified for unknown emails).
  Changing a password needs the current one and counts as an attempt. Attempts older than 30 days are pruned daily.
- **Team page, admins only**, enforced by a router-level dependency: found in the access matrix, a rep sending a
  bad body got a detailed validation error (confirming the endpoint exists) because FastAPI validates the body
  before the handler runs. Now it's a plain 404 whatever they send. Admins can't deactivate or demote themselves.
- **"View as" stays for development and the demo only.** A session always wins; a bad session never falls back to
  the dev header. With neither DEV_AUTH nor DEMO_MODE set, sign-in is the only way in.
- **The first admin:** `scripts/make_link.py`, run from the API server's shell (already the most privileged place),
  creates an admin if needed and prints a one-time link. Also the way back in if every admin is locked out.
- **Web:** route groups `(app)` and `(auth)`: the sign-in pages load nothing that needs a session, so an expired
  session can't redirect them to themselves. Any 401 from the API redirects to sign-in ("your session ended").
  Account page (change password, sign out everywhere); Team page with a copy-once link box.
- **Audit:** sessions and links are audited (sign-ins, sign-outs, resets appear in the trail); password and token
  hashes are redacted; a session's `last_seen_at` bookkeeping is ignored so requests don't flood the log. The
  attempt log itself is the one other table not audited (it's already a record of every attempt), listed with its
  reason.
- **Found by running it in a browser:** React runs effects twice in development, and the second run lost the link
  token after the first had cleaned the address bar (now read once into a ref). React 19's form reset cleared the
  email after a wrong password (now sent back with the error as the field's default).
- Tests: `test_auth.py` (password rules, uniform failures, hashed storage, no dev-header fallback, both rate limits,
  session lifetime, sign-out everywhere, deactivation, password change, links, team safeguards), matrix rows for
  all nine endpoints with probes for the public ones, and browser tests for the whole lifecycle (add a person,
  set a password through the link, sign out, fail, sign in, reused link refused, ended session, reps and Team).
  Checked by breaking the code: removing the account limit, letting a bad token fall back to the dev header,
  making sign-out-everywhere a no-op, storing tokens in plain text, dropping the idle timeout, and making links
  reusable each failed their tests.

## Demo polish from a full walkthrough (2026-09-30)

A click-through of every page as an admin and a rep, in dev and a production build, at desktop and phone
widths. Nothing crashed; these are what a first-time visitor could trip on.

- **First visit offers the people, not a pointer to the dropdown.** With no one chosen, pages showed one line
  ("Choose a person in View as"). `ChooseViewer` now lists admins and reps as one-click buttons (the same
  `viewAs` action as the header), each group with a line on what that role sees. Only reachable with
  DEV_AUTH or DEMO_MODE; otherwise the layout sends people to sign in.
- **Our own 404.** `app/not-found.tsx` (unknown addresses, with its own header like the sign-in pages) and
  `app/(app)/not-found.tsx` (a `notFound()` from an app page, inside the shell). Next's default follows the OS
  color scheme, so in dark mode it was a black box inside the light app.
- **Admins' "Needs attention" says where stale referrals are.** Nudges go only to credited reps
  (`app/jobs/stale.py`), so an admin's empty list claimed "No stale referrals" beside a digest counting 38. It
  now links to the Referrals list's 14-day stale filter.
- **Close rate's two placeholder definitions are named side by side** in each footnote (partner lists: bound ÷
  referred; dashboard and digest: bound ÷ decided), so the different numbers don't read as a bug. Relabeling
  waits for FIELD_QUESTIONS #2.
- **A page past the end redirects to the last page** (Referrals and Partners), instead of "Page 999 of 7" and
  "No referrals match these filters".
- **Smaller fixes:** the pipeline move dialog keeps its content while it fades out (it emptied mid-animation);
  inline number editors can align to the end of a numeric cell (the dashboard's goal editors spilled left);
  the Team table doesn't wrap; on phones the scoreboard's three numbers sit side by side and the nav fades at
  its right edge to show it scrolls.

## Local only, one command to run (2026-10-01)

- **No deployment.** The app runs locally only. Removed DEPLOY.md, render.yaml, the keep-warm and nightly
  reseed workflows, the production-preview script and its smoke tests (`web/e2e-prod/`), and the Neon setup.
  DEMO_MODE stays in the code for now.
- **`npm run dev` at the root starts everything** ([scripts/dev.mjs](scripts/dev.mjs)): create databases,
  migrate, seed only if there are no users (`seed.py --if-empty`, so edits survive a restart), then the API and
  web side by side with prefixed output. Plain Node, no new dependency. `npm run reseed` starts the data over.
