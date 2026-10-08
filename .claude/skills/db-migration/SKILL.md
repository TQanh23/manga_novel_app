---
name: db-migration
description: Add or change Postgres tables, columns, indexes, roles or RLS policies via Alembic. Use for any schema change in api/ or worker/, including new tables in core, billing, ai or analytics.
---

# Database migration

Rules this procedure enforces live in CLAUDE.md (Migrations, Architecture rules, AI data policy). This file is the order of work.

## 1. Model first

- Put the model in the owning module (`api/<module>/models.py`), in the right schema: `core`, `billing`, `ai` or `analytics`.
- Use the shared base: UUID v7 primary key, `created_at`, `updated_at`. Don't redefine them.
- Foreign keys to `works` or `episodes` need an explicit `ondelete` choice. Write down which one and why in the migration docstring.
- Text that may hold KR/JP/VI content is `text`, never `varchar(n)` sized for ASCII.

## 2. Generate, then read the migration

```bash
cd api && uv run alembic revision --autogenerate -m "<FR-ID> <what>"
```

Autogenerate misses things. Check the file by hand and add what it skipped:

- Extensions (`vector`, `pg_trgm`, `unaccent`) and HNSW / GIN trigram indexes.
- `GRANT` to the app roles. New tables need explicit grants: `app_rw` gets what the code uses, `app_public` gets `SELECT` only where shared features read the table.
- For `billing.ledger_entries` and any other append-only table (`ai_audit_log`): grant `INSERT, SELECT` only, no `UPDATE`/`DELETE`.
- Enum changes: `ALTER TYPE ... ADD VALUE` cannot run inside a transaction on older Postgres; use `op.get_context().autocommit_block()`.

Never edit a migration that has been applied anywhere (CI counts). Add a new one.

## 3. RLS, when the table holds author-private data

Anything keyed by `author_id` that holds manuscript-derived content (chunks, OCR blocks, findings, drafts) needs RLS in the same migration:

```sql
ALTER TABLE ai.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.chunks FORCE ROW LEVEL SECURITY;  -- without FORCE the table owner bypasses RLS
CREATE POLICY author_isolation ON ai.chunks
  USING (author_id = current_setting('app.author_id')::uuid);
CREATE POLICY public_published ON ai.chunks FOR SELECT TO app_public
  USING (episode_status = 'published');
```

The session sets `SET LOCAL app.author_id = :id` per transaction; check the repository layer does this for the new table.

## 4. Hard delete path

If the table or a new bucket references a work, episode or author: add it to the work deletion service and extend the hard-delete test so it asserts no rows reference the deleted `work_id` afterwards.

## 5. Downgrade

Write `downgrade()` for real (drop policies before tables). Then prove the round trip:

```bash
cd api && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

## 6. Tests

Run against the real Postgres+pgvector service, never SQLite.

- New RLS table: an isolation test that connects as `app_rw`, sets `app.author_id` to author B, runs raw SQL, and gets zero of author A's rows.
- The existing test that the API role is neither superuser nor table owner must stay green.

```bash
cd api && uv run pytest -k "migration or rls or delete"
cd api && uv run pytest
```

## Done when

- Migration reviewed by hand, grants and RLS present, downgrade round-trips.
- Hard-delete test covers the new table if it references a work.
- Full backend suite green.
