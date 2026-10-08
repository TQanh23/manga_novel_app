# CLAUDE.md

Manga and novel reading platform in the style of Ridibooks/KakaoPage, for Android and web. Portfolio project for an AI engineer / backend role: the reader side stays thin, the author side carries the AI and data work.

Source of truth for requirements is the system spec (Vietnamese): https://claude.ai/code/artifact/2c8fd711-f47d-4e4a-a852-8d698d0cbf57 . The PRD (English) sits above it: https://claude.ai/code/artifact/7258408e-a56a-4d5a-8971-b2b86481e522 . Requirement IDs (`FR-PAY-02`, `NFR-06`, ...) come from the spec. Reference them in commit messages, test names and PR descriptions so work traces back to a requirement. If code and spec disagree, ask before changing either.

## Repository layout

Monorepo, one FastAPI monolith plus one worker. No microservices, no Kafka.

```
api/        FastAPI app (Python), modules: auth, catalogue, reader, billing, author, ai, analytics, admin
worker/     arq worker: image pipeline, OCR, indexing, AI checks, analytics rollup
app/        Expo (React Native) + Expo Router, TypeScript; one codebase for Android and web
infra/      Docker Compose, seed data, Grafana dashboards
eval/       Fixed AI eval set (manuscripts with planted contradictions) and runner
```

If the layout in the repo differs from this, the repo wins; update this file.

## Commands

<!-- Fill in once the tooling exists. Keep these exact and runnable. -->

```bash
docker compose up                 # Postgres+pgvector, Redis, MinIO, Ollama, api, worker, with seed data
cd api && uv run pytest           # backend tests
cd api && uv run ruff check . && uv run mypy .
cd api && uv run alembic upgrade head
cd api && uv run alembic revision --autogenerate -m "<msg>"
cd app && npx expo start          # client; press w for web, a for Android
cd app && npm run typecheck && npm run lint
cd app && npm run gen:api         # regenerate the TS client from the API's OpenAPI spec
cd eval && uv run python run.py --provider <name>
```

## Stack

- Backend: Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2.
- Database: Postgres 16 + pgvector (HNSW). One database, schemas per module: `core`, `billing`, `ai`, `analytics`. UUID v7 primary keys; every table has `created_at`, `updated_at`.
- Cache and queue: Redis + arq.
- Storage: MinIO locally, S3-compatible for the demo. Clients upload and download through presigned/signed URLs.
- Client: Expo + Expo Router, TypeScript. API client is generated from the OpenAPI spec and shared by Android and web; never hand-write request types.
- AI: `LLMProvider` and `EmbeddingProvider` interfaces. Ollama + bge-m3 (1024-dim) locally, free hosted APIs during testing (sample data only), a cheap paid model with a spend cap for the demo.
- OCR and images: manga-ocr (JP), PaddleOCR (KR/EN), Pillow/pyvips, imagehash.
- Payments: VNPay sandbox behind a `PaymentProvider` interface. No real money.
- Observability: structlog (JSON), Prometheus, Grafana.
- CI: GitHub Actions runs lint, typecheck, tests and the AI eval.

## Architecture rules

These are load-bearing. Breaking one is a bug even if tests pass.

1. **The API never calls an LLM, OCR engine or image processor directly.** Slow work goes to the arq worker. The endpoint returns `202` with a `job_id`; the client polls `GET /author/jobs/{id}` or listens on the SSE stream.
2. **Swappable providers.** `LLMProvider`, `EmbeddingProvider`, `Storage` and `PaymentProvider` are interfaces selected by config. No vendor SDK imports outside their provider implementation.
3. **Images never pass through the API.** Uploads go straight to the `raw/` bucket via presigned URL; reads use signed URLs that expire after 5 minutes.
4. **Worker jobs are idempotent** on `(kind, target_id, content_hash)`, retry at most 3 times with backoff, and land in a dead-letter list on final failure.
5. **API is REST under `/v1`.** Long tasks return `202 + job_id`. Endpoints that move coins require an `Idempotency-Key` header.
6. **Request id flows from API to worker** and appears in every log line.

## Money: coins, unlocks, wait-until-free

- **Double-entry ledger.** Every balance change is one or more immutable rows in `billing.ledger_entries`. Never `UPDATE` or `DELETE` a ledger row. Corrections are reversing entries. `wallets.cached_balance` is a cache and must be reproducible from the ledger.
- **Unlocks are atomic.** Debit, credit and the `unlocks` row commit in one Postgres transaction. `unlocks` has a unique `(user_id, episode_id)`. Idempotency keys stop double charging on retries.
- **VNPay.** Verify `vnp_SecureHash` on both Return URL and IPN. Only the IPN credits coins; the Return URL only displays the result. Process each `vnp_TxnRef` once. Never commit VNPay secrets; they come from env vars.
- **Presets, not free-form values.** The WUF period (author picks per work) and the revenue split (admin assigns per work) both reference `config_presets`. The preset in force is snapshotted onto each unlock, so changing a preset never rewrites past revenue.
- **WUF timers.** Postgres `wuf_timers` is the source of truth; Redis holds a cache. If they disagree, Postgres wins.
- Any change to billing code needs a concurrency test proving no double spend (`NFR-04`).

## AI data policy

Each commitment below has a mechanism and a test. Do not weaken the mechanism, and do not delete or skip its test.

- **No training without opt-in.** `works.ai_opt_in_training` defaults to `false`. Nothing that exports or fine-tunes reads a work with the flag off.
- **Providers that may train get sample data only.** Providers are allowlisted in config with an `allows_training` flag. A provider with `allows_training=true` must never receive a real author's manuscript; enforce this in code, not by convention.
- **Per-author vector isolation.** `ai.chunks` carries `author_id` and is protected by Postgres RLS. The repository layer requires `work_id` on every vector query. Never add a query path that bypasses RLS or omits the filter. The test is that author B can never retrieve author A's chunks, even bypassing the service layer.
- **Drafts stay out of shared features.** Recommendations, semantic search and auto-tagging only read chunks with `episode_status = 'published'`.
- **No prompt or output logging by default.** `ai_jobs` stores metadata only (provider, model, tokens, cost). The logger filters content fields. Do not log manuscript text, prompts, or raw LLM output, including in debug logs and exception messages.
- **Hard delete.** Deleting a work removes episodes, versions, chunks, OCR blocks, S3 objects and AI findings. Only the anonymised ledger and the audit log survive. When adding a table or bucket that references a work, add it to the delete path and its test.
- **Audit log.** Every AI call on a manuscript appends to `ai_audit_log`, which the author can read. Append-only.
- **Admins cannot read unpublished drafts** except through break-glass access that writes to the author-visible audit log.
- **No AI image generation.** No endpoint, provider or dependency that generates images.

## AI features

- Lint and consistency checks ask the LLM for output matching a fixed JSON schema. Validate it; discard findings that lack evidence. Consistency findings must cite `evidence_chunk_ids`.
- Chunking: by paragraph, roughly 300 to 500 tokens, keeping original offsets for citations. Re-indexing deletes the old version's chunks.
- Author verdicts on findings feed the eval set, never training.
- Per-author AI quota and rate limit are checked before a job is enqueued.
- Changing a prompt, model, chunking or retrieval parameter means running the eval and reporting precision, recall and cost against the previous run. Eval targets to start: recall at least 80%, precision at least 70%.

## Conventions

- Python: type hints everywhere, `ruff` + `mypy` clean. Async SQLAlchemy sessions; no ORM calls from route handlers, go through the module's service/repository layer.
- Migrations via Alembic only. Never edit an applied migration; add a new one. RLS policies live in migrations.
- Passwords hashed with argon2. JWT access tokens are short-lived; refresh tokens rotate.
- Rate limiting by IP and user in Redis.
- TypeScript strict mode. UI strings go through i18n (EN and VI); no hard-coded copy.
- Content languages are KR, JP, EN and VI; never assume ASCII or space-separated words in text processing.
- Code, comments, commits and docs in English.

## Testing

- Domain logic (coins, WUF, permissions) needs at least 80% coverage (`NFR-12`).
- Tests that hit the database use a real Postgres with pgvector (Testcontainers or the Compose service), not SQLite, because RLS and vector queries are part of what is tested.
- AI tests use a fake `LLMProvider` with fixed responses. Only the eval job calls a real model.
- Every policy commitment above keeps its test green.

## Scope

MVP is the requirements tagged MVP in the spec. The demo script that defines "done": an author publishes a 5-chapter novel and a 2-episode manga, the consistency check catches a planted contradiction, a reader on Android unlocks chapters with coins and WUF, and the author sees revenue on the dashboard. Build order: foundation, catalogue and reader, billing, AI core, analytics; then P2 (OCR, pHash, heatmap, translation, semantic search, comments, push) and P3.

Do not build P2/P3 features or new infrastructure unless asked. Open questions in the spec (Editor role in MVP, coin price in VND, demo host, pHash auto-block vs flag) are undecided; ask rather than pick.
