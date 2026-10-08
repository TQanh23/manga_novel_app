---
name: worker-job
description: Add or change an arq job or cron in worker/ (image tiling, OCR, indexing, AI checks, rollups, scheduled publish, reconciliation). Use whenever slow or scheduled work is added.
---

# arq worker job

## 1. Pick the queue

- `ai` queue (`max_jobs=2`): anything that calls an LLM or embedding provider. Also follow the `ai-change` skill.
- default queue: image processing, rollups, scheduled publish, reconciliation.

Don't put AI work on the default queue: rate-limited AI jobs would block manga uploads.

## 2. Idempotency

Every job is idempotent on `(kind, target_id, content_hash)`. Use the shared helper; don't write a new one.

- Compute `content_hash` from the input that determines the output (episode version text, raw image bytes hash), not from timestamps.
- Running the job twice on the same input is a no-op. Running it on new input replaces the old output in one transaction (delete-and-insert), never appends duplicates.
- Crons (scheduled publish, rollups) must be safe to run twice in the same minute and safe after a missed run.

## 3. Failure behaviour

- Use the shared retry settings: at most 3 retries with backoff, then the dead-letter list.
- Rate limit or 429: `raise arq.Retry(defer=retry_after)`. This does not count as a failure.
- Update `ai_jobs` / job status rows so `GET /v1/author/jobs/{id}` and the SSE stream show progress and the final state, including failure.

## 4. Context and logs

- Read `request_id` from the job context and bind it to structlog for every log line.
- Never log manuscript text, OCR text, prompts or model output. Log ids, counts, durations and token usage only.

## 5. Enqueue side

- The API enqueues and returns `202 + job_id`. Per-author quota and rate limits are checked in the API before enqueueing, not inside the job.
- Pass ids to the job, not large payloads. The job loads what it needs.

## 6. Tests

```bash
cd worker && uv run pytest -k <job_name>
```

Cover: one successful run; a second run on the same input does nothing (assert row counts unchanged); a run on changed input replaces output; a provider error leads to retry and, after the limit, the dead-letter list. AI jobs use `FakeLLMProvider` / a fake embedding provider; tests never call a real model.

## Done when

Idempotency, retry and dead-letter paths are tested, status is visible through the jobs endpoint, and no content fields appear in logs.
