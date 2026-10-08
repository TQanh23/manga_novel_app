---
name: ai-change
description: Change anything in worker/ai or eval/ (providers, routes in config/ai.yaml, prompts, chunking, retrieval, lint, consistency check, findings) or any code that sends manuscript text off the server. Use before touching AI code or prompts.
---

# AI change

Design reference: `docs/ai-architecture.md`. Policy commitments: CLAUDE.md (AI data policy). This skill is the checklist that keeps both true while changing AI code.

## 1. Classify the change

| Change | Extra steps |
|---|---|
| New provider or route | Section 2 |
| Prompt, model, chunking, top-k, batching | Section 4 (eval run is required) |
| New AI feature or task | Sections 2, 3 and 4 |
| Code that touches chunks or findings | Section 3 |

## 2. Providers and the policy gate

- Providers go in `config/ai.yaml` with `trains_on_input` and `data_allowed`. A provider whose training terms are not confirmed is `data_allowed: sample`.
- Code gets a provider only through `policy.resolve(task, work)`. Never construct a provider or import a vendor SDK elsewhere. One `OpenAICompatProvider` covers Groq, Cloudflare and Ollama; prefer config over a new adapter.
- `policy.resolve` writes `ai_audit_log` before the call. A new task adds a route for both `real` and `sample`.
- The test that a real work never reaches a `data_allowed: sample` provider, even with a misrouted config, must cover the new route.

## 3. Data handling

- Vector queries pass `work_id` and run under RLS with `app.author_id` set. Shared features read only `episode_status = 'published'` and run as `app_public`.
- `ai_jobs` stores metadata only: provider, model, prompt hash, tokens, cost. No prompt or output columns.
- No manuscript text, prompts or model output in logs, exception messages or job results stored outside `ai_findings`. Check new log calls and `raise` messages.
- Structured output only: `complete_json` with a Pydantic schema; on invalid JSON, retry once, then fail the job.
- Consistency findings keep only `evidence_chunk_ids` that were in that call's context. Don't move this check into the prompt.
- New chunk-like data joins the hard-delete path and its test.

Tests use `FakeLLMProvider` with fixed responses:

```bash
cd worker && uv run pytest worker/ai -k "policy or rls or log or delete or evidence"
```

## 4. Eval

Required when a prompt, model, chunking or retrieval parameter changes.

```bash
cd eval && uv run python run.py --route sample   # Groq free tier, sample manuscripts only
```

- Run the same command on the base branch first if there is no stored previous result.
- Report in the PR: recall, precision, tokens and cost, before and after. Targets: recall at least 80%, precision at least 70%.
- A precision drop with a recall gain is not automatically better; say which findings changed.
- Mind the free-tier budget: one eval run per change, not one per edit. `--route real` (Cloudflare) only when comparing the real-work model.
- Author verdicts become new eval cases in `eval/cases.yaml`. They never feed training.
- Prompts live in `worker/ai/prompts/*.md`; the prompt hash is recorded in `ai_jobs`, so edit the file rather than inlining strings.

## Done when

Policy tests green including the new route, no content in logs (run a lint job and grep the logs for a sentence from the sample manuscript), and the PR has the eval table when section 4 applies.
