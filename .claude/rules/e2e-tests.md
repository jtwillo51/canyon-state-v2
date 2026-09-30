---
paths:
  - "web/e2e/**"
  - "web/playwright.config.ts"
---

# Browser tests (Playwright)

- `npm run e2e` from `web/`. `playwright.config.ts` starts its own API on :8100 (`e2e/start-api.mjs`
  migrates and **reseeds `canyon_e2e`** first) and `next dev` on :3100 building into `.next-e2e/` (Next
  locks each output folder, so this runs beside `npm run dev`). One worker, since the tests share one database.
- Seeded people are in `e2e/helpers.ts`: Dana Whitfield (admin), Jordan Pike and Tessa Moreno (reps).
  `viewAs(context, request, name)` sets the same cookie as the "View as" switcher.
- Find records through the API (`referralOf`, `apiGet`) rather than hard-coding ids or seed counts: the seed
  is relative to today, and tests that change data must compare before and after.
- Locate elements by role and accessible name (`getByRole("button", { name: "Edit goal" })`), never by CSS
  classes. If an element has no good name, give it one in the component.
- Check hidden controls with `toHaveCount(0)`, and scope text checks to `getByRole("main")` (the dev "View as"
  list in the header names everyone).
- After clicking a link, `waitForURL` before reading `page.url()`: Next navigates on the client.
- Drag and drop: move the mouse in steps (`{ steps: 20 }`); the board starts a drag only after 6 px.
- These tests check what the UI *offers*. Access itself is enforced and tested in the API.
