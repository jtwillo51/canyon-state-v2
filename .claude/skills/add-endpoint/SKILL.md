---
name: add-endpoint
description: Add or change a FastAPI endpoint end to end in Canyon State v2, from the schema and route to access rules, the access matrix, tests, the generated TypeScript client and the page that uses it. Use when a feature needs new API data or a new write.
---

# Add an endpoint, end to end

This is a learning project: at each step that involves a choice (URL shape, who may call it, what
the response includes), explain the options, recommend one, and wait for the owner's decision.

## 1. Decide the contract first
- Method and path, following the existing routers (`/referrals/{referral_id}/...`).
- **Who may call it:** nobody / the owning rep / another rep / an admin. Check the table in
  `.claude/rules/access-control.md` and `DECISIONS.md`. If the rule isn't settled, ask. Don't guess.
- What the response contains, and whether it differs by viewer.

## 2. Build it (`api/`)
1. Request/response models in `app/schemas.py`. Requests that update use `extra="forbid"` and act on
   `model_fields_set`. Responses name every field that leaves the API.
2. The route in `app/routers/<resource>.py`, taking `viewer: Viewer, db: DB`. Referral data starts from
   `visible_referrals(viewer)`. Put business rules in a module like `app/pipeline.py` and keep routes thin.
3. Refuse with `FieldError` (422, shown next to a field) or `HTTPException(404)` for records the viewer
   can't see (never 403).
4. A new router module needs `app.include_router(...)` in `app/main.py`.

## 3. Prove who may use it
1. Add a row to `CASES` in `api/tests/test_access_matrix.py` with the expected status for all four people.
2. Add behavior tests next to the related ones (`tests/test_<area>.py`), using the `world` fixture.
3. If the contents differ by viewer, add a content test: what a rep must *not* see.
4. `uv run pytest`. Then break the new rule once (drop the check), confirm a test fails, and restore it.

## 4. Reach the web app (`web/`)
1. With the API running: `npm run gen:api`. This regenerates `src/lib/api/schema.d.ts` (commit it). Add a
   friendly name in `src/lib/api/types.ts` if the page uses the shape.
2. Reads go in the Server Component page through `getApi()`. Writes go in a Server Action that forwards
   to the API and refreshes. The browser never calls the API directly.
3. `npm run typecheck && npm run lint`.
4. If what the UI offers depends on the viewer, add a Playwright check in `e2e/roles.spec.ts` and run `npm run e2e`.

## 5. Record it
Add the decisions (who may call it, and why) to `DECISIONS.md` under a dated section.
