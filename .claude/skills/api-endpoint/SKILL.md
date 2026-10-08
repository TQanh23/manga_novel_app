---
name: api-endpoint
description: Add or change a FastAPI endpoint under /v1 and carry the change through to the Expo client. Use when adding routes, changing request or response schemas, or wiring a new screen to the API.
---

# API endpoint, end to end

A change is not done until the generated TS client and the app typecheck match the API.

## 1. Decide the shape before writing code

- Find the requirement ID in the spec. It goes in the test name and commit message.
- Is the work slow (LLM, OCR, embedding, image processing, anything over ~300 ms)? Then the endpoint enqueues a job and returns `202` with `{job_id}`. Write the job with the `worker-job` skill. The client follows progress on `GET /v1/author/jobs/{id}` or its SSE stream; don't add a new status endpoint.
- Does it move coins or create an unlock? Then it requires an `Idempotency-Key` header. Use the `billing-change` skill as well.
- Does it serve images? It returns signed URLs (5-minute expiry), never bytes.

## 2. Layering

Inside `api/<module>/`:

- `schemas.py`: Pydantic v2 request/response models. Response models are explicit; never return ORM objects. Give each model a stable name, since it becomes the TS type name.
- `repository.py`: all SQLAlchemy queries. Vector or `ai.*` queries take `work_id` as a required argument.
- `service.py`: business logic, transactions, permission checks beyond the role.
- `router.py`: thin. Parse, call the service, map to response. Use `require_role(...)` for RBAC. No ORM calls here.

Set `operation_id` explicitly on the route (`<module>_<verb>_<noun>`) so the generated client gets readable function names that don't change when the path does.

Errors go through the shared error envelope. Don't raise bare `HTTPException` with ad hoc bodies.

## 3. Tests

```bash
cd api && uv run pytest api/<module>/tests -k <name>
```

At minimum: happy path, wrong role (403), unauthenticated (401), and validation error. For author resources add: author B cannot read or change author A's resource. For drafts: the endpoint never exposes unpublished episodes to readers or the catalogue.

## 4. Regenerate the client

```bash
cd api && uv run ruff check . && uv run mypy .
cd app && npm run gen:api
cd app && npm run typecheck && npm run lint
```

Commit the regenerated client in the same commit as the API change. Never hand-edit generated files or write request types by hand.

## 5. Client

- Call the endpoint through the generated client only.
- UI strings go through i18n with both EN and VI keys.
- If the screen is new, check it on web and Android (`npx expo start`, then `w` and `a`).

## Done when

Backend tests, ruff, mypy, gen:api, app typecheck and lint all pass, and the regenerated client is in the diff.
