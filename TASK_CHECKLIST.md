# Task Checklist

Working checklist for the whole project. It breaks [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) into tasks that can each be finished and verified on their own, and traces every requirement ID in the system spec to a phase.

- System spec (source of truth): https://claude.ai/code/artifact/2c8fd711-f47d-4e4a-a852-8d698d0cbf57
- Plan (order, sizes, "cut first" rules): [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)
- Architecture rules and conventions: [`CLAUDE.md`](CLAUDE.md)

## How to use

- Tick a box only when the task is merged and its test (where one is named) is green in CI.
- Work top to bottom. Do not start a phase until the previous phase's exit check is fully ticked.
- Refer to tasks by group number (`3.3`) and to requirements by ID (`FR-PAY-02`) in commits and PRs.
- Phases 0 to 5 are the MVP. Phases 6 and 7 are P2/P3 and stay untouched until the MVP demo runs.
- Tasks marked **(gap)** come from the spec or `CLAUDE.md` but are missing from the plan. Confirm them before building.
- If a task turns out wrong or the plan changes, edit this file in the same PR.

| Phase | Theme | Status |
|---|---|---|
| 0 | Foundation | Done |
| 1 | Catalogue and novel reader | In progress |
| 2 | Manga upload and reader | Not started |
| 3 | Billing | Not started |
| 4 | AI core | Not started |
| 5 | Analytics, hardening, demo | Not started |
| 6 | P2 | Not started |
| 7 | P3 | Not started |

## Decisions to make

Each one blocks the tasks listed next to it. The plan's default is in brackets; confirming the default is enough.

- [ ] **D1.** AI providers for testing and the policy flag names (`allows_training` vs `trains_on_input` + `data_allowed`) [Cloudflare Workers AI for real works, Groq for `is_sample` only]. Blocks 4.1, 4.2. Then reconcile `CLAUDE.md`.
- [x] **D2.** Ollama in the default Compose stack or behind a `local-ai` profile [profile]. Blocks 0.2. Then reconcile `CLAUDE.md`. Decided: `local-ai` profile; `CLAUDE.md` updated.
- [ ] **D3.** Editor role in MVP or P2 [P2]. Blocks nothing in MVP if P2.
- [ ] **D4.** Coin price in VND and default episode price [1 coin = 100 VND, 3 coins per episode; config only].
- [ ] **D5.** Can authors set episode prices in MVP [no, Admin default only]. Blocks 3.6.
- [x] **D6.** WUF preset list [3h, 12h, 1 day, 3 days]. Blocks seed data in 1.1. Decided: 3h, 12h, 1 day, 3 days, stored in seconds.
- [ ] **D7.** Demo host, and whether the demo uses a paid model only. Blocks 5.6.
- [ ] **D8.** pHash match: flag to Admin or auto-block, and the Hamming threshold [flag only]. Blocks 6.3.
- [x] **D9.** Vietnamese search without diacritics in MVP [yes]. Blocks 1.5. Decided: yes, a search matches with or without diacritics.
- [ ] **D10. (gap)** What happens to an author's works when the account is deleted (`FR-AUTH-05`). The spec does not say. Blocks 3.8.
- [ ] **D11. (gap)** `design/ai-architecture.md` is referenced by the plan but is not in the repo. Add it before Phase 4 starts.
- [x] **D12. (gap)** How a Reader becomes an Author. The spec does not say. Decided: self-serve. Registration always creates a Reader; `POST /v1/me/roles/author` adds the Author role. Update the spec to match.

## Phase 0: Foundation

Requirements: FR-AUTH-01, FR-AUTH-03, FR-AUTH-05 (model only), FR-AD-01 (API only), NFR-05, NFR-10, NFR-12, NFR-13 (UI i18n), NFR-14.

### 0.1 Repo skeleton
- [x] Create `api/`, `worker/`, `app/`, `infra/`, `eval/`, `docs/`
- [x] `api/`: `uv` project, `ruff`, `mypy --strict`, `pytest` configured and passing on an empty app
- [x] `app/`: Expo + Expo Router, TypeScript strict, ESLint, `typecheck` and `lint` scripts
- [x] `.gitignore`, `.env.example` (no secrets committed), root `README.md` stub
- [x] Fix the plan's `../CLAUDE.md` link (move the plan into `docs/` or correct the path)

### 0.2 Docker Compose (NFR-14)
- [x] Postgres 16 + pgvector, Redis, MinIO services with healthchecks
- [x] MinIO buckets `raw/` and `tiles/` created on start
- [x] `api` and `worker` services, started after their dependencies are healthy
- [x] Ollama placed according to D2
- [x] `docker compose up` on a fresh clone works with no manual steps

### 0.3 Database baseline
- [x] Async SQLAlchemy 2 engine and session factory
- [x] Alembic wired to async, first migration creates schemas `core`, `billing`, `ai`, `analytics`
- [x] Extensions `vector`, `pg_trgm`, `unaccent`
- [x] UUID v7 primary-key helper
- [x] `created_at` / `updated_at` mixin used by every model
- [x] Test fixture running against real Postgres + pgvector (Testcontainers or the Compose service)

### 0.4 App roles for RLS
- [x] Migration creates `app_rw` and `app_public` roles
- [x] API connects as `app_rw`; migrations run as the owner role
- [x] Test: the API's DB role is not a superuser and not the table owner

### 0.5 Auth and RBAC (FR-AUTH-01, FR-AUTH-03, FR-AD-01, NFR-05)
- [x] `users`, `user_roles` models and migration (include `status` and `locale`)
- [x] `POST /v1/auth/register` with argon2 hashing
- [x] `POST /v1/auth/login` returning a short-lived JWT and a refresh token
- [x] `POST /v1/auth/refresh` with rotation; a reused refresh token is rejected
- [x] `require_role` dependency; one account can hold Reader and Author together
- [x] Redis rate limit by IP and by user on auth routes
- [x] `PATCH /v1/admin/users/{id}`: lock a user, change roles; a locked user cannot log in
- [x] Tests: register/login/refresh, rotation, role checks, lockout, rate limit

### 0.6 Cross-cutting (NFR-10)
- [x] structlog JSON logging
- [x] Request id middleware; the id is in every API log line
- [x] Request id passed into the arq job context and into every worker log line
- [x] Content-field log filter (`text`, `content`, `messages`, `input`) with a unit test
- [x] Shared error envelope for all routes
- [x] `/healthz`
- [x] `/metrics` (Prometheus) for request latency (cut first)

### 0.7 Worker skeleton
- [x] arq worker with a `ping` job, reachable from the API
- [x] Retry at most 3 times with backoff
- [x] Dead-letter list on final failure
- [x] Idempotency helper keyed on `(kind, target_id, content_hash)`, with a test that a repeat is a no-op

### 0.8 Client
- [x] `npm run gen:api` generates the TS client from the OpenAPI spec
- [x] i18n set up with EN and VI; no hard-coded copy
- [x] Login and register screens
- [x] Token storage: SecureStore on Android, web equivalent; silent refresh
- [x] Signed-in shell showing the user's roles

### 0.9 CI (NFR-12)
- [x] GitHub Actions: backend `ruff`, `mypy`, `pytest` against a Postgres + pgvector service container
- [x] GitHub Actions: app `typecheck` and `lint`
- [x] Coverage report for domain modules, with the 80% gate ready to switch on in Phase 3

### 0.10 Seed
- [x] Seed script: one admin, one author, two readers; runs on `docker compose up`

### Exit check
- [x] Fresh clone, `docker compose up`, register and log in from the web build
- [x] Same login works on Android
- [x] CI green
- [x] DB role test (0.4) green

## Phase 1: Catalogue and novel reader

Requirements: FR-RD-01, FR-RD-02 (no unlock states yet), FR-RD-03, FR-RD-05, FR-RD-06, FR-NV-01, FR-NV-02, FR-NV-03, FR-AD-04 (presets table only).

### 1.1 Content model
- [x] `works` with `is_sample` and `ai_opt_in_training`, both default `false`
- [x] `episodes` with status `draft` / `scheduled` / `published` / `removed`, `publish_at`, `price_coins`, `wuf_eligible`
- [x] `episode_versions`
- [x] `tags`, `work_tags`
- [x] `glossary_entries` with `aliases[]`, `attributes jsonb`, `translations jsonb`
- [x] `config_presets` (`kind`, `value`, `active`); `works.wuf_preset_id` and `works.revenue_share_preset_id` reference it
- [x] `reading_progress`
- [x] Seed the WUF and revenue-split presets (per D6). They are inserted by the migration, not by the seed script: every environment needs them.
- [x] RLS on `episode_versions` (`NFR-06`), moved here from 4.3: drafts are visible to their author only, the published version to everyone. `set_author_context` in `api/core/db.py` sets `app.author_id` for a transaction.

Where the schema differs from the spec's data model:
- `works.rating` is left out until content rating (`FR-MG-07`, P3) defines its values.
- A genre is a tag with `tags.kind = 'genre'`; there is no separate genre table.
- `episodes.published_version_id` names the version readers see.
- `episodes` and `episode_versions` repeat the work's `author_id`, held equal by composite foreign keys, so the RLS policy can trust it.

### 1.2 Author API (FR-NV-01)
- [x] `POST /v1/author/works`, `PATCH /v1/author/works/{id}`
- [x] `POST /v1/author/works/{id}/episodes`
- [x] `PUT /v1/author/episodes/{id}/draft`: each save is a new `episode_versions` row. Saving the text that is already the newest version adds nothing.
- [x] Version history: list and restore. Restoring adds a new version with the old text.
- [x] `POST /v1/author/episodes/{id}/publish` (publish now)
- [x] Every transaction that reads or writes drafts calls `set_author_context` first (the draft functions of `api/author/repository.py` do it themselves)
- [x] The service checks what the schema cannot: `wuf_preset_id` names a `wuf_period` preset, `published_version_id` names a version of the same episode
- [x] Ownership checks: an author cannot touch another author's work (test). Another author's work answers 404, like one that does not exist.
- [x] Read endpoints the author studio (1.8) needs: list and get works, list and get episodes, the current draft, one old version, the offered WUF periods
- [x] **(gap)** `PATCH /v1/author/episodes/{id}` to rename an episode: the spec says create and edit, no task had the edit

### 1.3 Scheduled publish (FR-NV-02)
- [x] Schedule publish with `publish_at`: `POST /v1/author/episodes/{id}/schedule`. Scheduling fixes the newest save as the one that goes live; saves made afterwards wait until the episode is scheduled again or published by hand.
- [x] `DELETE /v1/author/episodes/{id}/schedule` calls a schedule off (not in the original list; without it the only way out of `scheduled` was to publish)
- [x] arq cron every minute flips due `scheduled` episodes to `published`. Crons are registered with `@cron` in `worker/runtime.py`; they have no `core.jobs` row and no retries, the next run is the retry.
- [x] Test: running the cron twice is idempotent (also: two runs at once, and a run after a missed one)

### 1.4 Glossary (FR-NV-03)
- [x] `GET` / `POST` / `PATCH /v1/author/works/{id}/glossary` (`PATCH` is on `.../glossary/{entry_id}`)
- [x] Tests with KR, JP and VI names and aliases
- [ ] **(gap)** Deleting a glossary entry: the spec lists `GET`, `POST` and `PATCH` only, and `app_rw` has no `DELETE` on the table. Decide whether authors need it.

### 1.5 Catalogue API (FR-RD-01, FR-RD-02, FR-RD-06)
- [x] `GET /v1/works` for home, with filters: type, genre, completion status. A work is in the catalogue while it has at least one published episode; that rule is written once, in `_visible_works` in `api/catalogue/repository.py`.
- [x] **(gap)** Authors assign genres and tags to a work, and the fixed genre list exists (inserted by a migration). The genre filter has no data without it, and no task had it. Twelve genres, listed by `GET /v1/genres`; `genres` and `tags` on the author's work routes.
- [x] Ranking with a placeholder ordering (cut first: keep only "newest"). `sort=newest` and `sort=popular`; popular orders by published episodes until Phase 5 has reads.
- [x] `GET /v1/works/{id}` and `GET /v1/works/{id}/episodes`
- [x] `GET /v1/search?q=` over title, author and tag using Postgres full-text. Differs from the spec: it matches substrings on trigrams, not a `tsvector`, because full-text splits on whitespace and finds no words in Japanese.
- [x] `unaccent` + `pg_trgm` so Vietnamese matches without diacritics (per D9)
- [x] Test: drafts and scheduled episodes never appear in catalogue or search

### 1.6 Reader API (FR-RD-03, FR-RD-05)
- [x] `GET /v1/episodes/{id}/content` for novels; guests can read free episodes. The text comes back as `paragraphs`, split by `split_paragraphs` in `api/catalogue/text.py`; a signed-in reader also gets their saved `position`.
- [x] `PUT /v1/progress/{episode_id}` at paragraph granularity. The position is an index into `paragraphs`.
- [x] `GET /v1/library`: reading and favourites
- [x] Favourite / unfavourite a work: `PUT` and `DELETE /v1/favourites/{work_id}`
- [x] **(gap)** `favourites (user_id, work_id)` table: neither the spec's data model nor 1.1 has one. Added by migration `0006`.

### 1.7 Client: reader
- [x] Home, browse with filters, search. Guests browse without signing in: only the sign-in screens are guarded, and from the signed-out side.
- [x] Work page with episode list. Rows open the reader once it exists.
- [x] Client tests with jest-expo, run by CI (`cd app && npm test`)
- [ ] Novel reader: font, size, light/dark theme
- [ ] Restore reading position by paragraph
- [ ] Library screen

### 1.8 Client: author studio
- [ ] Works list, create/edit work
- [ ] Markdown editor with autosave
- [ ] Version history view
- [ ] Glossary editor
- [ ] Publish now and schedule

### 1.9 Seed
- [x] Sample novel with 5 episodes and a glossary, `is_sample = true`. In Vietnamese, under `infra/seed/sample_novel/`, published for `author@example.com` through the author services. Every glossary entry is stated in at least two chapters, so the eval set (4.9) has facts to contradict.

### Exit check
- [x] An episode scheduled one minute ahead becomes readable on its own
- [ ] Progress set on Android shows on web after refresh
- [x] Search finds a title typed without diacritics
- [x] Draft-visibility test (1.5) green
- [ ] Both targets (Android, web) run every screen in this phase

## Phase 2: Manga upload and reader

Requirements: FR-MG-01, FR-MG-02, FR-RD-04, NFR-02, NFR-03, NFR-05 (signed URL expiry), NFR-09 (`Storage`).

### 2.1 Storage interface (NFR-09)
- [ ] `Storage` protocol: presigned PUT, signed GET, delete by prefix
- [ ] MinIO/S3 implementation selected by config; no vendor SDK import outside it
- [ ] Signed GET URLs expire after 5 minutes (test)

### 2.2 Upload flow (FR-MG-01)
- [ ] `episode_pages`, `page_tiles` models and migration
- [ ] `POST /v1/author/episodes/{id}/uploads` returns presigned URLs to `raw/`
- [ ] `POST /v1/author/uploads/{id}/complete` creates `episode_pages`, enqueues `process_pages`, returns `202 + job_id`

### 2.3 Job status (NFR-03)
- [ ] `GET /v1/author/jobs/{id}`
- [ ] `GET /v1/author/jobs/{id}/stream` (SSE), built to be reused by AI checks
- [ ] Only the job's owner can read it (test)

### 2.4 Tiling pipeline (FR-MG-02)
- [ ] Validate format and size; reject with a clear job error
- [ ] Slice long strips into tiles, preferring blank gutters between panels
- [ ] Two resolutions in WebP, written to `tiles/` (AVIF only if free; cut first)
- [ ] `page_tiles` rows with `y_offset` and `height`
- [ ] Compute and store pHash per page (matching waits for 6.3)
- [ ] Progress updates published for SSE
- [ ] Test: re-running `process_pages` on the same content is a no-op

### 2.5 Manga reader (FR-RD-04, NFR-02)
- [ ] Content endpoint returns the tile list with signed URLs
- [ ] Client: upload screen with progress over SSE
- [ ] Client: vertical scroll reader with lazy tile loading
- [ ] Client: page-flip mode (cut first)
- [ ] Progress stored at tile granularity
- [ ] Test: the API has no route that streams image content

### Exit check
- [ ] Upload a 10,000 px strip from the web client and watch progress over SSE
- [ ] Read it on Android
- [ ] No-image-through-API test green
- [ ] Idempotent `process_pages` test green

## Phase 3: Billing

Requirements: FR-PAY-01, FR-PAY-02, FR-PAY-03, FR-PAY-04, FR-AD-04, FR-RD-02 (full states), FR-AUTH-05 (endpoint), NFR-04, NFR-09 (`PaymentProvider`), NFR-12.

Nothing in the ledger or unlock path may be cut. Cut client wallet polish instead.

### 3.1 Ledger (FR-PAY-03)
- [ ] `wallets`, `ledger_entries`, `topups`, `unlocks`, `idempotency_keys` in the `billing` schema
- [ ] Accounts for reader wallet, author payable and platform
- [ ] Every transaction's entries sum to zero (enforced and tested)
- [ ] `UPDATE` / `DELETE` on `ledger_entries` blocked by trigger or revoked privileges (test as `app_rw`)
- [ ] `unlocks` unique on `(user_id, episode_id)`; stores price and the revenue-split preset in force

### 3.2 Balance
- [ ] `cached_balance` updated in the same transaction as the entries
- [ ] `GET /v1/wallet`
- [ ] `reconcile_wallets` job recomputes from the ledger and alerts on mismatch

### 3.3 Unlock (FR-PAY-02, NFR-04)
- [ ] `POST /v1/episodes/{id}/unlock` requires `Idempotency-Key`; missing header is rejected
- [ ] One transaction: lock wallet row, check balance, write entries, insert `unlocks`
- [ ] Same key returns the stored response
- [ ] Insufficient balance and already-unlocked cases return clean errors with no entries written
- [ ] Episode content endpoint enforces unlock state for paid episodes. Until then `GET /v1/episodes/{id}/content` and `PUT /v1/progress/{episode_id}` answer 402 `episode_locked` to everyone for an episode with a price.
- [ ] **(gap)** `GET /v1/library` gains "purchased" (FR-RD-05); it has reading and favourites only

### 3.4 Wait-until-free (FR-PAY-04)
- [ ] `wuf_timers` in Postgres as source of truth
- [ ] Redis cache; when it disagrees, Postgres wins (test)
- [ ] Author picks the work's WUF preset; a running timer finishes on the old period (test)
- [ ] `GET /v1/works/{id}/wuf`
- [ ] WUF unlock writes `unlocks` with `method = wuf` and no ledger entries

### 3.5 Payments (FR-PAY-01, NFR-09)
- [ ] `PaymentProvider` interface selected by config
- [ ] VNPay sandbox: `POST /v1/wallet/topups` creates the payment URL
- [ ] Return URL verifies `vnp_SecureHash` and only displays the result
- [ ] IPN verifies `vnp_SecureHash` and credits coins once per `vnp_TxnRef`
- [ ] VNPay secrets come from env vars only
- [ ] `FakePaymentProvider` for tests and local demos
- [ ] IPN replay script for local testing without a public URL

### 3.6 Admin config (FR-AD-04)
- [ ] `PUT /v1/admin/config`: default coin price, WUF preset list, revenue-split preset list
- [ ] Assign a revenue-split preset to a work
- [ ] **(gap)** A new work has no revenue split (`revenue_share_preset_id` is null). Decide the default before the first unlock, which snapshots it.
- [ ] Test: changing a preset does not change the split stored on past unlocks

### 3.7 Client (FR-RD-02)
- [ ] Wallet screen with balance and history
- [ ] Top-up flow opening the VNPay sandbox page and showing the result
- [ ] Episode states: free / WUF countdown / price / unlocked
- [ ] Unlock confirm dialog
- [ ] "Purchased" tab in library

### 3.8 Account deletion (FR-AUTH-05) (gap)
The plan covers the model only; the spec tags the requirement MVP. Needs D10.
- [ ] `DELETE /v1/me` hard-deletes personal data
- [ ] Ledger rows survive untouched and carry no personal data
- [ ] Test: after deletion nothing identifies the user, and the ledger still sums to zero

### Exit check (all in CI)
- [ ] 50 concurrent unlocks on one wallet funded for 3 episodes: exactly 3 succeed, balance never negative, ledger sums to zero
- [ ] Same idempotency key sent twice concurrently: one charge
- [ ] Same IPN delivered twice: one credit
- [ ] IPN with a bad signature: rejected, no credit
- [ ] `cached_balance` equals the ledger sum for every wallet after the suite
- [ ] Domain coverage for billing and WUF at 80% or higher; gate switched on in CI

## Phase 4: AI core

Requirements: FR-AI-01, FR-AI-02, FR-AI-03, FR-AI-06, FR-AI-07, NFR-06, NFR-07, NFR-08, NFR-09, NFR-11, NFR-13 (multilingual embeddings), and the policy table in spec section 9. Needs D1 and D11 first.

### 4.1 Providers (FR-AI-06, NFR-09)
- [ ] `LLMProvider` (`complete_json`) and `EmbeddingProvider` protocols
- [ ] One OpenAI-compatible implementation covering the chosen hosted providers and Ollama
- [ ] `FakeLLMProvider` with fixed responses for tests
- [ ] Provider registry and allowlist from config, including the training-policy flag
- [ ] No vendor SDK import outside the provider implementation (lint rule or test)
- [ ] No image-generation endpoint, provider or dependency

### 4.2 Policy gate (FR-AI-07)
- [ ] `policy.resolve(task, work)` is the only way to obtain a provider
- [ ] `PolicyViolation` when a real work would reach a sample-only provider
- [ ] `ai_audit_log` row appended before every call; table is append-only
- [ ] Test (write first): a real work never reaches a sample-only provider, even with a misconfigured route
- [ ] Test: a dataset export skips works with `ai_opt_in_training = false`

### 4.3 Chunks and isolation (NFR-06)
- [ ] `ai.chunks` with `author_id`, `work_id`, `episode_id`, `episode_status`, `embed_model`, `vector(1024)`
- [ ] HNSW index
- [ ] RLS policy in a migration with `FORCE ROW LEVEL SECURITY`; `SET LOCAL app.author_id` per transaction
- [ ] Repository layer requires `work_id` on every vector query
- [ ] Test: author B running raw SQL as `app_rw` cannot see author A's chunks
- [ ] Published-only read path for shared features, with a test that drafts are excluded
- [x] **(gap)** RLS on episode drafts as well as embeddings, as `NFR-06` states. Done in 1.1.
- [ ] **(gap)** Admins cannot read unpublished drafts; break-glass access writes to the author-visible audit log (test)

### 4.4 Indexing pipeline (NFR-13)
- [ ] Paragraph chunking at roughly 300 to 500 tokens, keeping original offsets
- [ ] Chunking tests on KR, JP, EN and VI text (no ASCII or whitespace assumptions)
- [ ] Batched embedding with bge-m3 (1024-dim)
- [ ] Delete-and-insert in one transaction; old version's chunks are gone
- [ ] Triggered on draft save with a 30 s debounce and on publish
- [ ] Publishing updates `episode_status` on existing chunks

### 4.5 Rate limits and quota (FR-AI-06, NFR-08)
- [ ] Redis token buckets per provider
- [ ] `arq.Retry` on an empty bucket or a 429
- [ ] Separate `ai` queue with `max_jobs=2`
- [ ] Per-author daily token quota and rate limit checked before enqueue (test)

### 4.6 Lint (FR-AI-01)
- [ ] `POST /v1/author/episodes/{id}/checks` returns `202 + job_id`
- [ ] Episode split into windows of about 1,500 tokens
- [ ] Fixed JSON schema; invalid output is discarded
- [ ] Offsets mapped back to the episode; out-of-range spans dropped

### 4.7 Consistency check (FR-AI-02)
- [ ] Claim and entity extraction from the new episode
- [ ] Deterministic glossary name check with `pg_trgm`, no LLM
- [ ] Retrieve top-5 chunks from the same work, plus related glossary entries
- [ ] Batched comparison returning contradictions with `evidence_chunk_ids`
- [ ] Findings citing chunk ids that were not in that call's context are discarded (test)

### 4.8 Findings and verdicts (FR-AI-03)
- [ ] `ai_jobs` stores metadata only: provider, model, status, tokens, cost
- [ ] `ai_findings` with spans and `evidence_chunk_ids`
- [ ] Results pushed over the SSE stream from 2.3
- [ ] `PATCH /v1/author/findings/{id}` records the author's verdict
- [ ] Verdicts export to eval cases; nothing exports them to training

### 4.9 Eval (NFR-11)
- [ ] 3 to 5 self-written sample manuscripts
- [ ] 20 to 30 planted contradictions with locations
- [ ] Runner reports recall, precision, tokens and cost per provider
- [ ] CI job on schedule, manual trigger, and PRs touching prompts, models, chunking or retrieval
- [ ] First real numbers recorded in the README, even if below target

### 4.10 Privacy mechanics (NFR-07)
- [ ] Test: logs from a real lint job contain no manuscript text, prompt or raw output
- [ ] `httpx` / provider client debug logging disabled; no content in exception messages
- [ ] `DELETE /v1/author/works/{id}` removes episodes, versions, chunks, findings, pages, tiles and S3 objects
- [ ] Anonymised ledger and audit log survive the delete
- [ ] Test: after delete, no row or object references the `work_id`

### 4.11 Client
- [ ] "Run check" in the editor with live progress
- [ ] Findings inline with highlighted spans and evidence passages
- [ ] Right / wrong buttons on each finding
- [ ] AI audit log page (`GET /v1/author/ai-audit-log`)
- [ ] AI settings with the opt-in toggle (`PATCH /v1/author/works/{id}/ai-settings`)
- [ ] Public "AI data policy" page in plain language, EN and VI

### Exit check
- [ ] Eval recall at least 80% and precision at least 70% on the sample route, or the real numbers recorded with a note
- [ ] Policy tests green: no-training export, sample-only routing, RLS isolation, drafts out of shared features, no content in logs, hard delete
- [ ] An author runs lint and a consistency check end to end from Android and web

## Phase 5: Analytics, hardening and demo

Requirements: FR-AN-01, FR-AN-02, NFR-01, NFR-08 (spend cap), NFR-10 (dashboards), NFR-12, NFR-14.

### 5.1 Events (FR-AN-01)
- [ ] `reading_events` partitioned by month
- [ ] `POST /v1/events/batch` with bulk insert
- [ ] Client batching for open, progress, complete, unlock

### 5.2 Rollups
- [ ] `episode_daily_stats`
- [ ] arq cron every 15 minutes; idempotent on re-run (test)
- [ ] Replace the Phase 1 ranking placeholder with real reads

### 5.3 Author dashboard (FR-AN-02)
- [ ] `GET /v1/author/works/{id}/stats?from&to` reading rollups only
- [ ] `GET /v1/author/revenue` using the split snapshotted on each unlock
- [ ] Client: reads and coin revenue per episode and per day

### 5.4 Load test and observability (NFR-01, NFR-10)
- [ ] k6 or Locust script against Compose
- [ ] Catalogue and episode metadata p95 under 200 ms at 50 concurrent users
- [ ] Prometheus metrics for queue depth and AI cost
- [ ] Grafana dashboard in `infra/`: latency, queue depth, AI cost

### 5.5 Demo seed and script
- [ ] Seed: 5-chapter novel with a planted contradiction
- [ ] Seed: 2-episode manga
- [ ] Seed: two readers with coins
- [ ] `docs/DEMO.md` matching the spec's MVP definition

### 5.6 Demo host (needs D7)
- [ ] Deploy to the chosen host with S3-compatible storage
- [ ] Demo model configured, provider spend cap set
- [ ] VNPay sandbox IPN reachable on the demo URL

### 5.7 README
- [ ] Architecture diagram and how to run
- [ ] Eval results table
- [ ] Load test results
- [ ] Ledger and RLS design notes
- [ ] Links to the policy tests and to the providers' current data terms

### Exit check
The demo script runs on Android and web with no manual DB edits.
- [ ] Author publishes the 5-chapter novel and the 2-episode manga
- [ ] Consistency check catches the planted contradiction
- [ ] Reader on Android unlocks with coins and with WUF
- [ ] Author sees the revenue on the dashboard

## Phase 6: P2

Do not start before the Phase 5 exit check. Each group is independent; take them in this order and stop anywhere.

- [ ] **6.1** Admin refunds as reversing ledger entries (FR-PAY-05), with a concurrency test
- [ ] **6.1** Monthly revenue-split settlement (FR-PAY-06)
- [ ] **6.2** Speech-bubble OCR: manga-ocr for JP, PaddleOCR for KR/EN, `ocr_blocks`, author edits (FR-MG-03)
- [ ] **6.2** Confirmed OCR text enters indexing, the consistency check and search (FR-MG-04); add `ocr_blocks` to the hard-delete path and its test
- [ ] **6.3** pHash matching across authors and `phash_matches` (FR-MG-05, needs D8)
- [ ] **6.3** Admin report queue (FR-AD-02) and takedown with reason and author notice (FR-AD-03)
- [ ] **6.4** Drop-off by paragraph and by tile, with a heatmap (FR-AN-03)
- [ ] **6.4** Conversion from free/WUF to paid, per episode (FR-AN-04)
- [ ] **6.5** Semantic search and "more like this" on published chunks only, via `app_public` (FR-RD-07)
- [ ] **6.6** Editor role per work and inline draft comments (FR-NV-04, FR-AUTH-03)
- [ ] **6.6** Episode comments and comment reports (FR-RD-08)
- [ ] **6.6** Google login (FR-AUTH-02)
- [ ] **6.6** Push notifications for new episodes and WUF ready (FR-RD-10)
- [ ] **6.6** Translation assist KR/JP to EN using glossary names (FR-AI-04)
- [ ] **6.6** Tag and blurb suggestions, author approves (FR-AI-05)
- [ ] **6.6** AI spend and queue dashboard for Admin (FR-AD-05)
- [ ] **6.6** Device management, at most 3 offline devices (FR-AUTH-04)

## Phase 7: P3

- [ ] Offline downloads on Android with device-bound licences (FR-RD-09)
- [ ] Auto alt-text, author approves before publish (FR-MG-06)
- [ ] Content rating check before publish (FR-MG-07)
- [ ] Promotions: episode discounts and time-limited rental tickets (FR-PAY-07)
- [ ] CSV export (FR-AN-05)

## Requirement coverage

Every ID in the spec and where it lands. Update this when a task moves.

| Requirement | Stage | Tasks |
|---|---|---|
| FR-AUTH-01 | MVP | 0.5, 0.8 |
| FR-AUTH-02 | P2 | 6.6 |
| FR-AUTH-03 | MVP | 0.5 (Editor per work: 6.6) |
| FR-AUTH-04 | P2 | 6.6 |
| FR-AUTH-05 | MVP | 0.5 (model), 3.8 |
| FR-RD-01 | MVP | 1.5, 1.7, 5.2 |
| FR-RD-02 | MVP | 1.5, 1.7, 3.7 |
| FR-RD-03 | MVP | 1.6, 1.7 |
| FR-RD-04 | MVP | 2.5 |
| FR-RD-05 | MVP | 1.6, 1.7, 3.7 |
| FR-RD-06 | MVP | 1.5, 1.7 |
| FR-RD-07 | P2 | 6.5 |
| FR-RD-08 | P2 | 6.6 |
| FR-RD-09 | P3 | 7 |
| FR-RD-10 | P2 | 6.6 |
| FR-PAY-01 | MVP | 3.5, 3.7 |
| FR-PAY-02 | MVP | 3.3 |
| FR-PAY-03 | MVP | 3.1, 3.2 |
| FR-PAY-04 | MVP | 3.4 |
| FR-PAY-05 | P2 | 6.1 |
| FR-PAY-06 | P2 | 6.1 (snapshot per unlock: 3.1) |
| FR-PAY-07 | P3 | 7 |
| FR-NV-01 | MVP | 1.2, 1.8 |
| FR-NV-02 | MVP | 1.3, 1.8 |
| FR-NV-03 | MVP | 1.4, 1.8 |
| FR-NV-04 | P2 | 6.6 |
| FR-MG-01 | MVP | 2.2 |
| FR-MG-02 | MVP | 2.3, 2.4 |
| FR-MG-03 | P2 | 6.2 |
| FR-MG-04 | P2 | 6.2 |
| FR-MG-05 | P2 | 6.3 (hash stored: 2.4) |
| FR-MG-06 | P3 | 7 |
| FR-MG-07 | P3 | 7 |
| FR-AI-01 | MVP | 4.6, 4.11 |
| FR-AI-02 | MVP | 4.7, 4.11 |
| FR-AI-03 | MVP | 4.8, 4.11 |
| FR-AI-04 | P2 | 6.6 |
| FR-AI-05 | P2 | 6.6 |
| FR-AI-06 | MVP | 4.1, 4.5 |
| FR-AI-07 | MVP | 4.2, 4.11 |
| FR-AN-01 | MVP | 5.1 |
| FR-AN-02 | MVP | 5.3 |
| FR-AN-03 | P2 | 6.4 |
| FR-AN-04 | P2 | 6.4 |
| FR-AN-05 | P3 | 7 |
| FR-AD-01 | MVP | 0.5 (API only, no admin screen) |
| FR-AD-02 | P2 | 6.3 |
| FR-AD-03 | P2 | 6.3 |
| FR-AD-04 | MVP | 1.1, 3.6 (API only, no admin screen) |
| FR-AD-05 | P2 | 6.6 |
| NFR-01 | | 5.4 |
| NFR-02 | | 2.5 |
| NFR-03 | | 2.2, 2.3, 4.6 |
| NFR-04 | | 3.3, Phase 3 exit check |
| NFR-05 | | 0.5, 2.1 |
| NFR-06 | | 4.3 |
| NFR-07 | | 0.6, 4.10 |
| NFR-08 | | 4.5, 5.6 |
| NFR-09 | | 2.1, 3.5, 4.1 |
| NFR-10 | | 0.6, 5.4 |
| NFR-11 | | 4.9 |
| NFR-12 | | 0.9, Phase 3 exit check |
| NFR-13 | | 0.8, 1.4, 4.4 |
| NFR-14 | | 0.2, 0.10, 5.5 |
