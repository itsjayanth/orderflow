# WhatsApp Embedded Signup — status & remaining work

Branch: `claude/whatsapp-embedded-signup-df38ux`

## Summary

Merchants can now connect WhatsApp two ways, side by side:

- **Manual** (unchanged): paste `phone_number_id` + `access_token` on the Settings page / onboarding wizard.
- **Embedded Signup** (new): click "Connect WhatsApp" → Meta's Facebook Login for Business popup → backend exchanges the returned code for a long-lived token, registers the phone number, subscribes webhooks, and stores credentials on the same `WhatsAppBusinessAccount` row the manual flow uses.

Both methods feed the exact same downstream code (message sending, Flows, notifications) — nothing else needed to change.

Files: `backend/src/onboarding/domain/embedded_signup.py`, new endpoints under `onboarding/api/router.py`, migration `b835a386e1a9`, frontend `EmbeddedSignupButton.tsx` + `embeddedSignup.ts`, wired into `SettingsPage.tsx` and `OnboardingPage.tsx`.

Lint/typecheck/tests all pass (ruff, mypy, biome, tsc, vitest). Backend `pytest` could **not** be run in the dev sandbox — no Postgres/Docker available.

## To do

1. **Run backend tests for real** — `cd backend && uv run pytest`, against a live Postgres (`TEST_DATABASE_URL`). Confirms the migration and the new `test_onboarding_embedded_signup.py` / `test_onboarding_whatsapp.py` cases actually pass.
2. **Apply the migration** — `uv run alembic upgrade head` (or let Render's `preDeployCommand` do it on deploy).
3. **Meta App Dashboard setup** (required before the button works at all):
   - Enable **WhatsApp Embedded Signup** for the app.
   - Create a **Login Configuration** (Facebook Login for Business) with WhatsApp Business scopes → gives you `META_CONFIGURATION_ID`.
   - Note the App ID / App Secret.
   - Add the deployed frontend's domain to the app's allowed domains for the JS SDK.
4. **Set env vars** on the backend deploy (Render): `META_APP_ID`, `META_APP_SECRET`, `META_CONFIGURATION_ID`, `META_GRAPH_API_VERSION` (defaults to `v21.0` if unset).
5. **Manual end-to-end test** once configured: click "Connect WhatsApp" in a real browser, complete the Facebook popup, confirm the row lands in `whatsapp_business_accounts` with `connection_method = embedded_signup`, then send a test message via the existing "Send yourself a test message" card to confirm delivery.
6. **Optional follow-up**: token refresh — the embedded-signup token's `expires_in` (if Meta returns one) is stored in `token_expiry_at` but nothing currently refreshes it before expiry; worth a reminder/alert once real usage starts.
