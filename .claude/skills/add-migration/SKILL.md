---
name: add-migration
description: Change the Canyon State v2 database schema safely with SQLAlchemy models and an Alembic migration, reviewed before it runs, reversible, with the seed and tests kept in step. Use when adding or changing a table, column, constraint or index.
---

# Add a migration

Conventions (Record mixin, soft delete, partial unique indexes, Numeric money, Literal + CHECK lists) are in
`.claude/rules/migrations.md`. This is a learning project, so explain each command before running it, and
ask before any choice about the data model (nullable or not, a new table or a column, what a list contains).

All commands run from `api/`.

1. **Change `app/models.py`.** A new table is `class X(Record, Base)`. A fixed list is a `Literal` plus
   `CheckConstraint(one_of("col", TheLiteral), name="col")`.
2. **Generate:** `uv run alembic revision --autogenerate -m "short description"`. The file lands in
   `migrations/versions/` named by date and time.
3. **Read it before running it.** Autogenerate can't see everything. Check for:
   - CHECK constraints and partial unique indexes (`postgresql_where=...`): it often misses them, so add them by hand.
   - `server_default`s on new NOT NULL columns, or existing rows fail the migration.
   - Anything it wants to drop that you didn't remove.
   - A `downgrade()` that really undoes `upgrade()`.
   Show the owner the migration and what you changed in it.
4. **Run and reverse:** `uv run alembic upgrade head`, then
   `uv run alembic downgrade -1 && uv run alembic upgrade head`.
5. **Seed:** if the new column needs data, update `scripts/seed.py` without shifting existing ids. Draw new
   random values from a separate `random.Random(...)`, so every existing record keeps its id and URL. Then
   `uv run python -m scripts.seed` (localhost only; it wipes and reseeds `canyon_dev`).
6. **Test:** `uv run pytest` (it migrates `canyon_test` from scratch, so it exercises the new migration too).
7. **Web:** if schemas changed, regenerate the client (`npm run gen:api` in `web/` with the API running).
8. **Deploy note:** Render runs `alembic upgrade head` in its build step against the demo database, so the
   migration must work on existing data, not just an empty database.
9. **Record** the schema decision in `DECISIONS.md`.
