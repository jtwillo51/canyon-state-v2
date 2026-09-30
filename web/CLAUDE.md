@AGENTS.md

# Web (Next.js 16, App Router)

Next 16 differs from most tutorials: check `node_modules/next/dist/docs/` before using an API you haven't
used here yet (the AGENTS.md above is Next's own note saying so).

## How data flows

- **The browser never calls the API.** Pages are Server Components that call FastAPI on the Next server
  through the server-only client (`src/lib/api/client.ts`, `getApi()` in `src/lib/viewer.ts`). `API_URL` has
  no `NEXT_PUBLIC_` prefix, so it never reaches the browser.
- **Writes are Server Actions** (`src/app/**/actions.ts`, `*-actions.ts`) that forward to the API as the
  viewer, then refresh. They're public endpoints, which is fine because the API enforces every rule.
- **Types come from the API:** `src/lib/api/schema.d.ts` is generated (`npm run gen:api` with the API
  running) and committed; `src/lib/api/types.ts` gives friendly names. Never hand-edit the generated file.
- **"View as"** is a dev/demo cookie (`dev_user`) holding a user id. Real sign-in replaces it in Stage 3.
- **Lists keep their state in the URL** (filters, sort, columns, page). Interactive pieces only change the URL.

## Conventions

- Client Components only where the browser is needed (events, `usePathname`, drag and drop). Mark them `"use client"`.
- Dates from the API are `"YYYY-MM-DD"`: format with `src/lib/format.ts` (`day`, `agencyToday`), never
  `new Date(string)`, which reads them as UTC midnight and shows the previous day in Arizona.
- Tables use the shared `DataGrid` (`src/components/list/data-grid.tsx`, TanStack Table v9). Editable
  fields use `InlineField`, with `canEdit` + `readOnlyReason` for fields the viewer can't change.
- React 19 resets a `<form action>` after it runs. Forms that must keep input after a refusal use
  `onSubmit` + a transition.
- UI copy is sentence case, plain and specific ("admins change this", not "Permission denied").

## Design

Theme tokens live in `src/app/globals.css` (see `.claude/rules/ui-design.md`). In short: flag blue (`brand`)
for structure, **copper only for "measured against a goal"**, IBM Plex Sans for words and Plex Mono for numbers.

## Tests

`npm run e2e` (Playwright, `e2e/`) starts its own API (:8100) and web server (:3100) on a freshly seeded
`canyon_e2e` database, so it never touches dev data. See `.claude/rules/e2e-tests.md`.
