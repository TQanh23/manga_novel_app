# Implementation Plan

Build plan for the manga/novel reading platform. It turns the build order in the system spec (section 10) and the PRD release plan into phases one person can work through, each ending in something that runs and a set of tests that prove it.

- System spec (Vietnamese, source of truth, requirement IDs): https://claude.ai/code/artifact/2c8fd711-f47d-4e4a-a852-8d698d0cbf57
- PRD (English): https://claude.ai/code/artifact/7258408e-a56a-4d5a-8971-b2b86481e522
- Repo conventions and architecture rules: [`CLAUDE.md`](../CLAUDE.md)

If this plan and the spec disagree, the spec wins; fix the plan.

## How to use this plan

- Phases 0 to 5 are the MVP and the CV-ready version. Phases 6 and 7 are P2 and P3 from the spec.
- Each phase lists its requirement IDs, the work in build order, and an **exit check**. Do not start the next phase until the exit check passes in CI.
- Every phase ships backend and client together. The Expo app grows screen by screen instead of being built at the end, so a demo is always possible.
- Sizes assume roughly 15 to 20 hours a week of solo work. They are estimates for planning, not deadlines. If a phase runs more than 50% over, cut scope inside it (the "cut first" line) before moving on.

| Phase | Theme | Size | Cumulative |
|---|---|---|---|
| 0 | Foundation | 2 weeks | 2 |
| 1 | Catalogue and novel reader | 2.5 weeks | 4.5 |
| 2 | Manga upload and reader | 2 weeks | 6.5 |
| 3 | Billing: coins, unlocks, WUF, VNPay | 3 weeks | 9.5 |
| 4 | AI core | 4 weeks | 13.5 |
| 5 | Analytics, hardening, demo | 2.5 weeks | 16 |
| 6 | P2 | as time allows | |
| 7 | P3 | as time allows | |

Phase 2 is split out from the spec's "catalogue and reader" step on purpose: the novel path is the shortest route to a working reader, and manga tiling is the first thing to cut if time runs short (spec section 10).

## Decisions this plan assumes

These are defaults picked so work can start. Change them here and in `CLAUDE.md` when Quynh decides otherwise.

| Topic | Default used | Status |
|---|---|---|
| AI providers during testing | Cloudflare Workers AI (bge-m3 embeddings, LLM for real works); Groq free tier for `is_sample` works only. See the AI architecture design. | Proposed, awaiting confirmation |
| Ollama | Optional Compose profile `local-ai`, not required to run the stack | Follows from the row above |
| Editor role | P2 (Phase 6). MVP has Reader, Author, Admin only | PRD default, open question |
| Coin price in VND | Seeded config value, e.g. 1 coin = 100 VND, default episode price 3 coins | Open question; it is config, so the code doesn't depend on the answer |
| Author-set episode price | No; Admin default only in MVP | Open question |
| WUF presets | 3h, 12h, 1 day, 3 days | Spec draft |
| Revenue split presets | 50/50, 60/40, 70/30, assigned by Admin, snapshotted per unlock | Decided; settlement is P2 |
| Demo host | Decided in Phase 5; until then everything runs on Docker Compose | Open question |
| pHash on match | Flag to Admin, never auto-block | Open question, P2 |
| Vietnamese search without diacritics | Yes, via `unaccent` + `pg_trgm` in Phase 1, since it's cheap | Open question |

`CLAUDE.md` still describes the provider policy flag as `allows_training` and lists Ollama in the default Compose stack. The AI design uses `trains_on_input` + `data_allowed` and makes Ollama optional. Reconcile `CLAUDE.md` once the provider choice is confirmed.

## Phase 0: Foundation

**Goal:** `docker compose up` brings up the whole stack with seed data, CI is green, and a user can register, log in and see their role.

Requirements: FR-AUTH-01, FR-AUTH-03, FR-AUTH-05 (model only), FR-AD-01 (API only), NFR-05, NFR-10, NFR-12, NFR-14.

1. **Repo skeleton.** `api/`, `worker/`, `app/`, `infra/`, `eval/`, `docs/`. Python managed with `uv`; `ruff`, `mypy --strict`, `pytest`. Expo app with Expo Router, TypeScript strict, ESLint.
2. **Docker Compose.** Postgres 16 + pgvector, Redis, MinIO (with `raw/` and `tiles/` buckets created on start), api, worker. Ollama behind the `local-ai` profile.
3. **Database baseline.** Async SQLAlchemy 2, Alembic, schemas `core`, `billing`, `ai`, `analytics`. UUID v7 helper, `created_at`/`updated_at` mixin. Extensions: `vector`, `pg_trgm`, `unaccent`.
4. **App roles for RLS.** Create `app_rw` and `app_public` roles in a migration now, and have the API connect as `app_rw` from day one. Retrofitting this in Phase 4 is painful.
5. **Auth.** `users`, `user_roles`. Register, login, refresh with rotation, argon2 hashing, short-lived JWT. RBAC dependency (`require_role`). Redis rate limit by IP and user on auth routes.
6. **Cross-cutting.** structlog JSON logs, request id middleware that is passed into arq job context, `/healthz`, `/metrics` (Prometheus). Error envelope shared by all routes. A content-field log filter (`text`, `content`, `messages`, `input`) installed now, even before AI exists.
7. **Worker skeleton.** arq worker with one `ping` job, retry/backoff settings, dead-letter list, idempotency helper keyed on `(kind, target_id, content_hash)`.
8. **Client.** Login/register screens, token storage (SecureStore on Android, memory + refresh cookie or storage on web), i18n setup (EN, VI). Generated API client from OpenAPI (`npm run gen:api`).
9. **CI.** GitHub Actions: backend lint, typecheck, tests against a Postgres+pgvector service container; app typecheck and lint.
10. **Seed.** Script creating an admin, an author and two readers.

**Exit check:** fresh clone, `docker compose up`, register and log in from the web build; CI green; test proving the API's DB role is not a superuser and not the table owner.

**Cut first:** Prometheus metrics (keep the request id and JSON logs).

## Phase 1: Catalogue and novel reader

**Goal:** an author creates a novel and publishes episodes; a guest browses and reads free episodes; a reader resumes at the same paragraph on another device.

Requirements: FR-RD-01, FR-RD-02 (without unlock states yet), FR-RD-03, FR-RD-05, FR-RD-06, FR-NV-01, FR-NV-02, FR-NV-03, FR-AD-04 (presets table only).

1. **Content model.** `works`, `episodes`, `episode_versions`, `tags`, `work_tags`, `glossary_entries`, `config_presets`. Add `works.is_sample` and `works.ai_opt_in_training` now (both default false).
2. **Author API.** Create/edit work and episode, `PUT /author/episodes/{id}/draft` with autosave-friendly semantics (each save is a new `episode_versions` row; prune old autosaves later if needed), publish now, schedule publish.
3. **Scheduled publish.** arq cron every minute flips `scheduled` episodes whose `publish_at` has passed. Idempotent.
4. **Glossary CRUD** with `aliases[]` and `attributes jsonb`. It is needed by the consistency check in Phase 4, and having real data early makes the eval easier to write.
5. **Catalogue API.** Home, ranking (by reads; a placeholder ordering until Phase 5 has data), filters (type, genre, status), work page, episode list. Full-text search with `unaccent` + `pg_trgm` for Vietnamese without diacritics.
6. **Reader API.** `GET /episodes/{id}/content` for novels, `PUT /progress/{episode_id}` at paragraph granularity, `GET /library` (reading, favourites; "purchased" arrives in Phase 3).
7. **Client.** Home, browse, search, work page, novel reader (font, size, light/dark, restore paragraph), library. Author studio: works list, Markdown editor with autosave, glossary editor, publish/schedule.
8. **Seed.** One sample novel with 5 episodes and a glossary, marked `is_sample = true`. This becomes the basis of the eval set later.

**Exit check:** an episode scheduled one minute ahead becomes readable on its own; progress set on Android shows on web after refresh; search finds a title typed without diacritics; drafts never appear in catalogue or search (test).

**Cut first:** rankings beyond a single "newest" list.

## Phase 2: Manga upload and reader

**Goal:** an author uploads a long webtoon strip; it is tiled in the background and readable on phone and web through signed URLs.

Requirements: FR-MG-01, FR-MG-02, FR-RD-04, NFR-02, NFR-03.

1. **Storage interface.** `Storage` protocol with a MinIO/S3 implementation: presigned PUT, signed GET with 5-minute expiry, delete by prefix.
2. **Upload flow.** `POST /author/episodes/{id}/uploads` returns presigned URLs; client uploads straight to `raw/`; `POST /author/uploads/{id}/complete` creates `episode_pages` and enqueues `process_pages`, returning `202 + job_id`.
3. **Job status.** `GET /author/jobs/{id}` and the SSE stream `GET /author/jobs/{id}/stream`. Built here once and reused by the AI checks in Phase 4.
4. **Tiling pipeline.** Validate format and size, cut long strips into tiles preferring blank gutters between panels, produce 2 resolutions in WebP (AVIF if pyvips supports it on the image without extra work), write `page_tiles` with `y_offset`/`height` (needed for the heatmap in P2). Compute and store pHash per page now, but matching across authors waits until P2.
5. **Reader.** Content endpoint returns the tile list with signed URLs. Client: vertical scroll reader with lazy tile loading and a page-flip mode; progress stored at tile granularity.

**Exit check:** upload a 10,000 px strip from the web client, watch progress over SSE, read it on Android; image bytes never pass through the API (test that the API has no route that streams image content); re-running `process_pages` on the same content is a no-op.

**Cut first:** page-flip mode and AVIF; then cut to single-page uploads without strip slicing (spec section 10).

## Phase 3: Billing

**Goal:** a reader tops up coins in VNPay sandbox, unlocks an episode with coins or WUF, and can never be charged twice.

Requirements: FR-PAY-01, FR-PAY-02, FR-PAY-03, FR-PAY-04, FR-AD-04, FR-RD-02 (full states), NFR-04.

1. **Ledger.** `wallets`, `ledger_entries` (immutable, double-entry: every transaction sums to zero), `topups`, `unlocks` (unique `(user_id, episode_id)`, stores the price and the revenue-split preset in force), `idempotency_keys`. A DB trigger or revoked privileges that stop `UPDATE`/`DELETE` on `ledger_entries`.
2. **Balance.** `cached_balance` updated in the same transaction as the entries. A `reconcile_wallets` job that recomputes from the ledger and alerts on mismatch.
3. **Unlock.** `POST /episodes/{id}/unlock` with required `Idempotency-Key`. One transaction: lock the wallet row (`SELECT ... FOR UPDATE`), check balance, write entries (reader wallet, author payable, platform), insert `unlocks`. Same key returns the stored response.
4. **WUF.** `wuf_timers` in Postgres as source of truth, Redis cache. Author picks the work's WUF preset; a running timer finishes on the old period. Unlock by WUF writes an `unlocks` row with `method = wuf` and no ledger entries.
5. **PaymentProvider + VNPay sandbox.** Create payment URL, Return URL (display only), IPN (verify `vnp_SecureHash`, credit coins once per `vnp_TxnRef`). Plus a `FakePaymentProvider` for tests and local demos, and an IPN replay script so top-ups can be tested without a public URL. Use a tunnel only when testing the real IPN path.
6. **Admin config.** Default coin price, WUF preset list, revenue-split preset list, assign split to a work.
7. **Client.** Wallet screen, top-up flow opening the VNPay sandbox page, episode states (free / WUF countdown / price / unlocked), unlock confirm, "purchased" in library.

**Exit check (all in CI):**
- 50 concurrent unlock requests on one wallet with enough balance for 3 episodes: exactly 3 succeed, balance is never negative, ledger sums to zero.
- Same idempotency key sent twice concurrently: one charge.
- Same IPN delivered twice: one credit. Bad signature: rejected, no credit.
- `cached_balance` equals the ledger sum for every wallet after the test suite.
- Domain coverage for billing and WUF at 80% or higher (NFR-12).

**Cut first:** nothing in the ledger or unlock path. Cut the client wallet polish instead.

## Phase 4: AI core

**Goal:** an author runs lint and a consistency check on a novel episode; the check catches planted contradictions with cited evidence; the data policy holds under test.

Requirements: FR-AI-01, FR-AI-02, FR-AI-03, FR-AI-06, FR-AI-07, NFR-06, NFR-07, NFR-08, NFR-09, NFR-11, plus the policy table in spec section 9. Design detail: `design/ai-architecture.md` (to be copied into `docs/` with this plan's first PR in this phase).

Build in the order the AI design gives (its section 10):

1. **Providers.** `LLMProvider` (`complete_json` only) and `EmbeddingProvider` protocols, one `OpenAICompatProvider` for Cloudflare, Groq and Ollama, a `FakeLLMProvider` for tests. Registry from `config/ai.yaml`.
2. **Policy gate.** `policy.resolve(task, work)` is the only way to get a provider. Raises `PolicyViolation` if a real work would reach a provider with `data_allowed: sample`. Writes `ai_audit_log` before every call. Test first: a real work never reaches Groq even with a misconfigured route.
3. **Chunks and isolation.** `ai.chunks` with `author_id`, `work_id`, `episode_status`, `embed_model`, `vector(1024)`, HNSW index. RLS with `FORCE ROW LEVEL SECURITY`, `SET LOCAL app.author_id` per transaction. Test: author B running raw SQL as `app_rw` cannot see author A's chunks.
4. **Indexing pipeline.** Triggered on draft save (30 s debounce) and on publish. Paragraph chunking at 300 to 500 tokens with offsets, batched embedding, delete-and-insert in one transaction.
5. **Rate limits and quota.** Redis token buckets per provider (rpm, tpm, tpd, Cloudflare neurons), `arq.Retry` on empty bucket or 429, a separate `ai` queue with `max_jobs=2`, per-author daily token quota checked before enqueue.
6. **Lint.** Episode split into ~1,500-token windows, fixed JSON schema, offsets mapped back to the episode, out-of-range spans dropped.
7. **Consistency check.** Claim extraction, deterministic glossary name check with `pg_trgm` (no LLM), retrieval of top-5 chunks from the same work, batched comparison, and code-level evidence validation: findings whose `evidence_chunk_ids` were not in that call's context are discarded.
8. **Findings and verdicts.** `ai_jobs` (metadata only), `ai_findings`, `PATCH /author/findings/{id}`. Verdicts export to eval cases, never to training.
9. **Eval.** `eval/` with 3 to 5 self-written sample manuscripts and 20 to 30 planted contradictions with locations. `python -m eval.run --route sample|real` reports recall, precision, tokens and cost. CI runs it on a schedule or manual trigger (not every push, to protect free-tier quota) and on any PR that changes prompts, models, chunking or retrieval.
10. **Privacy mechanics.** Content-field log filter verified on a real lint job; `httpx`/`openai` debug logging disabled; hard delete of a work removes episodes, versions, chunks, findings and S3 objects (test: nothing references the `work_id` afterwards).
11. **Client.** "Run check" in the editor, live progress over SSE, findings inline with highlighted spans and evidence passages, right/wrong buttons, AI audit log page, AI settings (opt-in toggle), public "AI data policy" page.

**Exit check:** eval recall ≥ 80% and precision ≥ 70% on the sample route (starting targets; record the first real numbers in the README even if below target); all policy tests green: no-training export, sample-only provider routing, RLS isolation, drafts out of shared features, no content in logs, hard delete.

**Cut first:** lint (keep the consistency check, it is the headline). Then the deterministic glossary check can stay while the LLM compare step uses a single model only.

## Phase 5: Analytics, hardening and demo

**Goal:** the MVP demo script runs end to end and the README shows the numbers.

Requirements: FR-AN-01, FR-AN-02, NFR-01, NFR-12, NFR-14.

1. **Events.** `POST /events/batch`, `reading_events` partitioned by month, client batching (open, progress, complete, unlock).
2. **Rollups.** arq cron every 15 minutes into `episode_daily_stats`. Dashboard reads rollups only. Replace the Phase 1 ranking placeholder with real reads.
3. **Author dashboard.** Reads and coin revenue per episode and per day, revenue using the split snapshotted on each unlock.
4. **Load test.** k6 or Locust against Compose: catalogue and episode metadata p95 under 200 ms at 50 concurrent users. Add indexes or caching until it passes.
5. **Demo seed and script.** A 5-chapter novel with a planted contradiction, a 2-episode manga, two readers with coins. A written demo script in `docs/DEMO.md` matching the spec's MVP definition.
6. **Demo host.** Pick the host (open question). Deploy with the capped paid or Cloudflare model; set the provider spend cap.
7. **README.** Architecture diagram, how to run, eval results table, load test results, the ledger and RLS design notes, links to the policy tests.

**Exit check:** the demo script from spec section 10 runs on Android and web without manual DB edits: author publishes the novel and manga, the consistency check catches the planted contradiction, a reader unlocks with coins and WUF, the author sees revenue on the dashboard.

## Phase 6: P2

Pick in this order; each is independent, so stop anywhere.

1. Revenue-split monthly settlement (FR-PAY-06) and admin refunds as reversing entries (FR-PAY-05). Small, and strengthens the billing story.
2. Speech-bubble OCR into the same consistency checker (FR-MG-03, FR-MG-04). Highest portfolio value of the P2 list.
3. pHash piracy matching and the admin report queue (FR-MG-05, FR-AD-02, FR-AD-03).
4. Drop-off heatmap by paragraph and tile, conversion (FR-AN-03, FR-AN-04).
5. Semantic search and "more like this" on published chunks only (FR-RD-07), using the `app_public` role.
6. Editor role and inline comments (FR-NV-04), comments and reports (FR-RD-08), Google login (FR-AUTH-02), push notifications (FR-RD-10), translation assist (FR-AI-04), tag and blurb suggestions (FR-AI-05), AI spend and queue dashboard (FR-AD-05), device management (FR-AUTH-04).

## Phase 7: P3

Offline downloads with device-bound licences (FR-RD-09), alt-text (FR-MG-06), content rating (FR-MG-07), promotions and rental tickets (FR-PAY-07), CSV export (FR-AN-05).

## Risks to watch while building

| Risk | Early signal | Response |
|---|---|---|
| Scope creep from the reader side | Spending time on UI polish before Phase 4 | Reader UI stays functional, not pretty, until Phase 5 |
| Free AI tier limits or terms change | 429s or quota exhaustion during eval runs | Ollama profile and the paid-model route behind the same interface; eval only on demand |
| Noisy consistency findings | Precision under 50% on the first eval | Tighten evidence validation and claim extraction before touching the UI |
| VNPay IPN unreachable locally | Top-ups stuck as pending | `FakePaymentProvider` and the IPN replay script; tunnel only for the real path |
| Expo web and Android diverge | A screen works on one platform only | Run both targets at the end of every phase's exit check |
