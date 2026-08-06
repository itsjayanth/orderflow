# Orderflow Frontend — Merchant Dashboard

React + TypeScript + Vite, per `TECH_STACK.md` at the repo root.

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL, defaults to http://localhost:8000
```

## Run

```bash
npm run dev
```

Dev server: http://localhost:5173. API calls go straight to `VITE_API_URL` (no Vite dev proxy) — CORS is handled backend-side, see `backend/src/shared/config.py`'s `cors_allow_origins`.

## Checks

```bash
npm run typecheck
npm run lint        # biome check .
npm run lint:fix     # biome check --write .
npm run test
npm run build
```

## Layout

```
src/
├── features/        # one folder per product feature (orders, catalog, customers, onboarding, dashboard)
│   └── <feature>/   # pages + feature-local state (e.g. onboardingWizardStore.ts)
├── shared/
│   ├── api/         # apiFetch client (wraps fetch against VITE_API_URL)
│   ├── components/  # cross-feature components (Layout, nav)
│   └── hooks/       # cross-feature hooks (TanStack Query hooks)
├── components/ui/   # shadcn/ui primitives (owned source, not an npm dependency)
├── lib/utils.ts     # cn() class-merging helper
└── App.tsx          # route table
```

Server state goes through TanStack Query (`shared/hooks`); Zustand is reserved for genuinely client-only UI state (e.g. the onboarding wizard's current step before it's persisted — see `features/onboarding/onboardingWizardStore.ts`).

## shadcn/ui components

`components.json` is configured (`style: new-york`, Radix base). The CLI (`npx shadcn@latest add <component>`) fetches from `ui.shadcn.com`, which may be blocked by network policy in some sandboxed environments — in that case copy component source manually into `src/components/ui/`, following the existing `button.tsx` as the pattern.

## Deployment (Vercel)

`vercel.json` rewrites every path to `/index.html` — required because `main.tsx` uses `BrowserRouter` (real paths like `/orders` or `/order/:merchantId`, not hash routing), so a direct load or refresh on any route needs the SPA fallback or it 404s. This matters most for `/order/:merchantId`: it's the public link the WhatsApp bot sends customers, so it's opened directly (not navigated to from within the app) on essentially every real order.

**To deploy**: import this repo into a new Vercel project with **Root Directory set to `frontend`** (this is a monorepo — Vercel won't find `package.json` at the repo root). Framework preset "Vite" is auto-detected; build command and output directory don't need overriding.

**Set one Project environment variable** (Project Settings → Environment Variables):

| Key | Value |
|---|---|
| `VITE_API_URL` | your Render backend URL, e.g. `https://orderflow-backend.onrender.com` (no trailing slash) |

Vite bakes `VITE_*` env vars into the build at build time, not runtime — if you change `VITE_API_URL` after the first deploy, trigger a new deploy (redeploy, don't just "restart") for it to take effect.

**This must stay in sync with the backend's `CORS_ALLOW_ORIGINS` and `FRONTEND_BASE_URL`** (see `backend/README.md`'s Deployment section) — set `VITE_API_URL` to the Render URL here, and set `CORS_ALLOW_ORIGINS`/`FRONTEND_BASE_URL` to this Vercel URL there. Mismatched origins fail as CORS errors in the browser console and a silently-rejected login (the refresh cookie won't be accepted cross-site without the backend's `SameSite=None` cookie config, which is already conditional on `ENV=production` — see `identity/api/router.py`).

Live deployment itself (creating the Vercel project, wiring env vars, triggering the first deploy) needs to be done from the Vercel dashboard, or by Claude via the Vercel MCP connector once it's authorized for this workspace (Settings → Connectors on claude.ai) — it isn't authorized in this session, so it wasn't done here. Everything above is what's needed once it is.
