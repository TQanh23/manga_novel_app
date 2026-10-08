---
name: billing-change
description: Change anything in api/billing (wallets, ledger, unlocks, top-ups, WUF timers, presets, revenue split, refunds) or the PaymentProvider/VNPay integration. Use before touching code that moves coins.
---

# Billing change

The ledger rules in CLAUDE.md (Money section) are not negotiable. This skill is how to change billing code without breaking them, and which tests prove it (`NFR-04`, `NFR-12`).

## 1. Before writing code

- Name the requirement (`FR-PAY-xx`, `FR-AD-04`). If the change alters how revenue or balances are computed, check the spec first; if the spec is silent, ask Quynh rather than choosing.
- Write down the ledger entries the operation produces. Every transaction sums to zero. Example unlock at 3 coins with a 50/50 split: reader wallet -3, author payable +1.5, platform +1.5. If amounts don't split evenly, state the rounding rule and who gets the remainder.

## 2. Implementation rules

- One Postgres transaction per operation: lock the wallet (`SELECT ... FOR UPDATE`), check balance, insert ledger rows, update `cached_balance`, insert `unlocks` / `topups`.
- Ledger rows are insert-only. A correction or refund is a reversing entry referencing the original.
- Endpoints that move coins require `Idempotency-Key`. The same key returns the stored response, including the original status code. Store the key in the same transaction as the effect.
- Preset values (WUF period, revenue split, price) are snapshotted onto the `unlocks` row. Never compute past revenue from the current preset.
- WUF: Postgres `wuf_timers` decides; Redis is a cache. A running timer finishes on the period it started with.
- VNPay: verify `vnp_SecureHash` on Return URL and IPN. Only IPN credits coins, once per `vnp_TxnRef`. Secrets come from env vars only.

## 3. Required tests

All against real Postgres, in CI. Add to these rather than writing parallel versions:

- Concurrency: 50 concurrent unlocks on a wallet that can afford 3 episodes: exactly 3 succeed, balance never negative, ledger sums to zero.
- Same `Idempotency-Key` sent twice concurrently: one charge, both responses identical.
- Same IPN twice: one credit. Bad signature: rejected, no credit. Unknown `vnp_TxnRef`: rejected.
- After the suite: `cached_balance` equals the ledger sum for every wallet.
- New entry types: a test that the transaction sums to zero.
- Coverage for billing and WUF stays at 80% or higher.

```bash
cd api && uv run pytest api/billing -x
cd api && uv run pytest api/billing --cov=api/billing --cov-report=term-missing
```

## 4. Manual check without a public URL

Use `FakePaymentProvider` for local demos. To exercise the real VNPay code path, create a sandbox payment and replay its IPN with the replay script instead of opening a tunnel. Use a tunnel only when testing VNPay's real callback.

## Done when

Concurrency, idempotency and IPN tests pass, ledger sums to zero, coverage holds, and the PR description lists the ledger entries the change produces.
