# 48 — Security audit: fix JWT/webhook secret fallbacks + WhatsApp webhook signature verification

Trello card: https://trello.com/c/IjZk0bwq/48-high-security-audit-fix-jwt-webhook-secret-fallbacks-whatsapp-webhook-signature-verification
Branch: `claude/order-flow-backlog-review-ss547h`

**Deviation from the naming convention, flagged up front rather than silently followed:**
this branch does not follow the `feature/48-...` convention `plans/README.md` describes.
The session this work was done in was pre-assigned to develop on
`claude/order-flow-backlog-review-ss547h` by the environment/orchestration layer that
started it (explicit "never push to a different branch without permission" instruction),
and that branch already had unrelated prior commits on it before this task began. Renaming
or branching fresh would have meant either abandoning that instruction or losing/rebasing
already-pushed history. Trello card, plan folder, and PR all use ticket `48` consistently;
only the branch's literal name is off-convention.

## Problem / goal

A full-application security audit (not a diff review — four parallel sub-audits covering
auth/tenant isolation, crypto/secrets, webhook/integration security, and
injection/data-exposure) surfaced 4 launch-blocking findings. The user asked to fix 3 of
them now and explicitly defer the 4th:

1. `jwt_secret` (`shared/config.py`) defaulted to the hardcoded literal `"change-me"`.
   If `JWT_SECRET` was ever left unset in a deployment, anyone could forge a valid staff
   JWT for any merchant — a full auth bypass, not just a tenant-scoped issue.
2. `whatsapp_webhook_verify_token` had the identical hardcoded fallback, defeating Meta's
   webhook verification handshake if unset.
3. `POST /api/v1/whatsapp/webhook` had no payload authentication at all. Meta signs every
   webhook POST with `X-Hub-Signature-256`, but the endpoint trusted any JSON body outright
   — including a forged WhatsApp Flow order-completion payload, which could create real
   COD orders impersonating any customer.

**Explicitly deferred, not in scope for this card:** the dummy Razorpay gateway's webhook
secret (`payments/adapters/gateway_selector.py`) is deterministically derived from the
public `merchant_id`, making it forgeable for any merchant without real Razorpay keys on
file. Excluded at the user's explicit instruction ("ignore razorpay pay, remaining fix
it") — tracked as a known gap, not closed here.

## Scope

In scope:
- `backend/src/shared/config.py` — remove the two hardcoded fallback defaults.
- `backend/src/shared/security.py` — fail closed (raise) on JWT creation/decoding if
  `JWT_SECRET` is unset, mirroring `shared/encryption.py`'s existing `_fernet()` pattern.
- `backend/src/conversation/api/router.py` — verify `X-Hub-Signature-256` on every
  inbound webhook POST before it reaches `handle_inbound_message`; fail closed (503) if
  `META_APP_SECRET` isn't configured; the GET handshake also explicitly fails closed if
  its verify token is unset.
- `backend/.env.example` — document the no-default-plus-fail-closed behavior.
- `backend/tests/conftest.py` — deterministic test-only secrets (mirroring the existing
  `DATABASE_URL`/`INTERACTION_MODE` pinning convention) plus a `webhook_request_kwargs()`
  helper for signing test webhook POSTs.
- `backend/tests/test_conversation_webhook_endpoint.py`, `backend/tests/test_campaigns.py`
  — sign their existing webhook POSTs; add tests for missing signature, forged signature,
  and unconfigured app secret.

Out of scope: the Razorpay dummy-gateway secret (separate follow-up), CI/CD, hosting.

## Affected modules

- `backend/src/shared/config.py`
- `backend/src/shared/security.py`
- `backend/src/conversation/api/router.py`
- `backend/.env.example`
- `backend/tests/conftest.py`
- `backend/tests/test_conversation_webhook_endpoint.py`
- `backend/tests/test_campaigns.py`

## Acceptance criteria

- [x] No hardcoded fallback for `jwt_secret` or `whatsapp_webhook_verify_token`; both fail
      closed if unset.
- [x] `POST /api/v1/whatsapp/webhook` verifies `X-Hub-Signature-256` (HMAC-SHA256, constant
      time compare) before processing; missing/invalid signature → 401, unconfigured app
      secret → 503.
- [x] GET webhook handshake fails closed if the verify token is unset.
- [x] Full backend test suite passes; `ruff check` and `mypy` clean (aside from the one
      pre-existing, unrelated `payments/api/router.py` finding predating this change).

## Implementation steps

1. `shared/config.py`: `jwt_secret`/`whatsapp_webhook_verify_token` defaults changed from
   `"change-me"` to `""`, each with a comment explaining why no fallback is used.
2. `shared/security.py`: add `_require_jwt_secret()`, used by both `_create_token` and
   `decode_token` instead of reading `settings.jwt_secret` directly.
3. `conversation/api/router.py`: GET handshake gains an explicit
   `not settings.whatsapp_webhook_verify_token` guard; POST handler reads the raw body,
   calls a new `_verify_signature()` (HMAC-SHA256 over the raw body keyed with
   `META_APP_SECRET`, `hmac.compare_digest`) before `json.loads`-ing and dispatching to
   `handle_inbound_message`.
4. `.env.example`: updated comments for both changed defaults plus a note on
   `META_APP_SECRET` now also gating webhook signature verification.
5. `tests/conftest.py`: pin test-only `JWT_SECRET`/`WHATSAPP_WEBHOOK_VERIFY_TOKEN`/
   `META_APP_SECRET` via `os.environ.setdefault`; add `webhook_request_kwargs()` helper.
6. Update the 4 existing webhook-POST call sites (3 in
   `test_conversation_webhook_endpoint.py`, 1 in `test_campaigns.py`) to sign their
   requests via the new helper; add 3 new tests (no signature, forged signature,
   unconfigured secret).
7. Validate: started a local Postgres in the sandbox, ran the full suite before (baseline)
   and after, `ruff check .`, `uv run mypy src`.

## Progress Log

**2026-09-07** — Implemented, tested, and pushed in one pass (commit `6ee4cb7`).
- Baseline test run (with `SECRETS_ENCRYPTION_KEY` set, otherwise unset in this sandbox):
  719 passed.
- After changes: 722 passed (3 new tests), `ruff check` clean, `mypy` clean except the
  one pre-existing `payments/api/router.py` finding already documented in
  `IMPLEMENTATION_PLAN.md` as unrelated/predating recent work.
- Deviation: this Trello card and plan folder were created **after** the code was already
  committed and pushed, not before, because the fix was implemented directly in response
  to a security-audit request mid-conversation, ahead of realizing the repo's own
  `CLAUDE.md` workflow required a card/plan first. Flagged here rather than silently
  back-dated. No scope drift resulted — the card's acceptance criteria match exactly what
  was already built.
- Razorpay dummy-gateway secret (Vuln 2 from the original audit) intentionally left
  unfixed per explicit user instruction; not tracked by this card.
