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
