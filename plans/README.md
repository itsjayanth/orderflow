# plans/

This directory holds the implementation plan for every major feature, significant change, or large task tracked through the Trello-linked development workflow. See the root [`CLAUDE.md`](../CLAUDE.md) → "Development workflow" section for the full rule; this file only covers the layout of `/plans` itself.

## Naming convention

Each subfolder is named `<TRELLO-CARD-ID>-<short-slug>`, where `<TRELLO-CARD-ID>` is the Trello card's short ID or short link (visible in the card URL, e.g. `https://trello.com/c/a1b2c3d4/...` → `a1b2c3d4`).

```
plans/a1b2c3d4-add-tax-calculation/
plans/ord-123-retry-order-queue/
```

## Contents of each subfolder

Each subfolder must contain a `PLAN.md` with the implementation plan: approach, steps, files to touch, and risks.

`PLAN.md` must also include:

- A subtask checklist (`- [ ]` / `- [x]`), checked off in the same commit that completes each subtask (not batched).
- A dated **Progress Log** section at the bottom recording what was done, the commit hash, and any deviation from the original plan and why.

Both the checklist and the Progress Log are kept in sync with the matching Trello card's comments and checklist items as work progresses — see the root `CLAUDE.md` for the full sync and pre-merge audit requirements.

## Full rule

For the complete workflow (Trello card lookup/creation, branch naming, commit/PR conventions, ongoing sync, and the pre-merge audit pass), see the root [`CLAUDE.md`](../CLAUDE.md) → "Development workflow" section.
