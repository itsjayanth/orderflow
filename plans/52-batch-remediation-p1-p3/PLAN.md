# 52 — Batch remediation: P1-P3 order-flow audit backlog

Trello card: https://trello.com/c/eQUcb6Gb/52-p1-p3-batch-remediation-indexes-races-coupling-tokens-pagination-pii-rate-limiting-logging-a11y-docs
Branch: `claude/order-flow-audit-0ybduw` (pre-assigned to this session, same
documented deviation from `feature/52-...` as cards #48/#50/#51).

**Deviation flagged up front:** this plan folder was created *after* the work was
already implemented and committed, not before — the card was created mid-orchestration
while dispatching parallel sub-agents across many backlog items, and creating a plan
folder per this repo's workflow was missed in the moment. Same category of deviation as
card #48's ("built first, workflow applied after"), flagged here rather than silently
backdated. No scope drift resulted — everything below matches what card #52's
description and Trello comments already say.

## Problem / goal

Continuation of card #50's P1-P3 remediation backlog, after card #51 closed out P0.
The user asked to pick up "all points, P0 to P3," authorized parallel sub-agents, and
required a final consolidation + full test run confirming mergeability before calling
it done.

## Approach

Work was dispatched to parallel sub-agents in file-non-overlapping waves (agents in the
same wave never touch the same file, so concurrent edits can't collide), except where a
prior item's file wasn't free yet (e.g. item 3/stock-recheck held `ordering_flow/domain/checkout.py`
until item 2/checkout-ordering finished). Every agent's diff was independently reviewed,
tested against an isolated scratch Postgres database, and re-validated by the
orchestrating session before being committed and pushed — no sub-agent's own commit/push
was trusted directly; the orchestrator did all git operations after review.

## Items completed (all pushed to `claude/order-flow-audit-0ybduw`)

| # | Item | Commit |
|---|---|---|
| P1 | DB indexes (orders composite, whatsapp_business_accounts unique) | `e610589` |
| P1 | Customer find_or_create race (ON CONFLICT DO NOTHING) | `e7696ce` |
| P1 | Orders/payments bidirectional coupling refactor | `f494009` |
| P1 | Structured JSON logging + request correlation IDs | `6b16de1` |
| P2 | Abandoned-order sweep audit trail | `5bf12b7` |
| P2 | Server-side refresh-token revocation | `f008278` |
| P2 | Backend pagination (orders/customers/catalog) | `21c6322` |
| P2 | Rate limiting (auth/checkout/webhooks, slowapi) | `2b11195` |
| P2 | Customer PII encryption at rest (whatsapp_number, address) | `aba20f5` |
| P3 | PublicTenant FastAPI dependency | `52cf5b4` |
| P3 | Shared EventBus extraction | `de6fad8` |
| P3 | Frontend a11y fixes | `afae7f4` |
| P3 | CLAUDE.md doc drift fix | `26b7e34` |

Deliberately **skipped** this pass (flagged in the Trello card description, not
attempted — too invasive/scope-creepy for unreviewed parallel automation on a payment
codebase):
- `conversation/domain/handler.py` god-file split (770 lines, 12-module fan-in)
- Repo-wide `StrEnum` conversion for payment/fulfillment status
- Frontend/backend transition-table codegen (a feature addition, not a pure fix)

## Notable deviations and incidents during this work

1. **Row-level locking migration index was too strict on the first pass** (actually
   card #51, but the same DB-invariant-modeling lesson applies here) — not repeated in
   this card's items, no similar issue found.
2. **Two sub-agents (rate limiting, PII encryption) failed mid-task with an API 429
   ("session limit, resets 5pm UTC")** — both had already produced substantial,
   near-complete diffs before failing. Rather than retry (risking the same rate limit),
   the orchestrator reviewed and finished both directly: verified the rate-limiting
   wiring, ran its test suite, and separately verified the PII migration's data backfill
   against a database seeded with real pre-existing plaintext rows (not just an empty
   schema) before committing either.
3. **A `git stash`/`git stash pop` mistake by the PublicTenant agent** (it didn't
   realize the working tree is shared live across concurrent agents) transiently
   scooped up the event-bus agent's and an already-committed checkout fix's uncommitted
   changes into stash entries. Caught and resolved: confirmed the event-bus agent's live
   work was still on disk (not lost), diffed both stash entries against current
   state/history to confirm they were fully redundant, then dropped them.
4. **Several agents' background test runs, and the orchestrator's own, occasionally hit
   `ConnectionRefusedError`** — the sandbox's local Postgres service died partway through
   the session at least twice; restarted with `service postgresql start` each time, not
   a code issue.
5. **A batch of ~30-130 test "failures" during final validation turned out to be
   cross-contamination from multiple pytest processes racing against the same shared
   scratch database** (`conftest.py`'s autouse fixture drops/recreates all tables per
   test, so two concurrent `pytest` runs against one database stomp on each other).
   Re-running in isolation against a dedicated fresh database each time confirmed zero
   real failures throughout. Final consolidated run (below) used one dedicated database
   with nothing else running concurrently.

## Final consolidation

Full backend suite, isolated database (`orderflow_test_final`), nothing else running
concurrently:

```
853 passed, 4 warnings in 273.81s
```

`uv run ruff check .`: all checks passed (whole repo).
`uv run mypy src`: 1 error — `payments/api/router.py`, `apply_payment_webhook_result`
argument type (`UUID | None` vs `UUID`) — pre-existing, predates this session's work,
already documented in card #48/#50/#51's plans as a known, unrelated finding.

Full migration chain (`alembic upgrade head` from a blank database) applies cleanly
through all of this session's new migrations, in order:
`fcd1cd201c55` (payment_events unique index) → `41a1324a64a2` (orders/whatsapp indexes)
→ `c0ca5d2bcc50` (revoked refresh tokens) → `1056afac7508` (customer PII encryption +
backfill). The PII migration was additionally verified against a database seeded with
real pre-existing plaintext customer/address rows (not just an empty schema) to confirm
the backfill actually encrypts in place rather than only working on empty tables.

Frontend, independently:
```
npm run lint       -- Checked 197 files, no issues
npm run typecheck   -- clean
npm run test         -- 218 passed (218)
npm run build        -- succeeds (pre-existing, unrelated warnings only:
                         a Google Fonts @import-ordering CSS warning and a
                         >500kB chunk-size advisory, both predate this session)
```

## Acceptance criteria

- [x] Every included backlog item implemented, tested in isolation, and committed.
- [x] Full backend suite green in a clean, non-contaminated run (853/853).
- [x] Full frontend suite green (lint/typecheck/test/build all clean).
- [x] ruff/mypy clean (one pre-existing, documented, unrelated finding).
- [x] Migration chain verified end-to-end from a blank database, and the PII
      migration's backfill separately verified against pre-existing plaintext data.
- [x] Skipped items explicitly flagged with reasoning, not silently dropped.

## Progress Log

**2026-09-07** — All 13 items in scope for this card implemented, reviewed, tested, and
pushed to `claude/order-flow-audit-0ybduw` (commits listed above). Final consolidated
test run (backend 853/853, frontend lint/typecheck/test/build all clean, ruff/mypy
clean aside from one pre-existing unrelated finding) confirms the branch is safe to
merge. Plan folder created retroactively (see deviation note above). No PR opened —
not requested.
