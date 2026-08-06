# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repository is pre-implementation: it currently contains only `README.md`, `.gitignore`, and `docs/project-brief.txt`. There is no source code, no build system, no dependency manifest, and no test suite yet. Do not assume any framework, language runtime, or file layout beyond what's described below — check current repo state before relying on anything here, since it will go stale fast as the project is built out.

The `.gitignore` is a stock Python template, which suggests a Python backend is planned, but this has not been confirmed by any actual code yet.

Since there's no code, there are no build/lint/test commands to document. Update this section once a backend/frontend scaffold exists.

## Product context (from `docs/project-brief.txt`)

Orderflow is a WhatsApp-based ordering system for independent restaurants (MVP phase, pilot target: a small cluster in Bangalore). Read the full brief at `docs/project-brief.txt` before making product/architecture decisions — key points to keep in mind:

- **Two sides**: a customer-facing WhatsApp chat flow (browse catalog → cart → order summary → payment link → confirmation → status updates), and a merchant-facing web dashboard (orders list/detail, manual status updates, menu/catalog management). No native mobile app for merchants — responsive web is sufficient.
- **Core pipeline**: WhatsApp conversation state → order object → payment status → merchant app order list. An order should appear in the merchant dashboard within seconds of payment confirmation.
- **Integrations implied by the brief**: WhatsApp Cloud API (via a Business Solution Provider) for chat/catalog/template messages; Razorpay (or similar) payment links with a webhook for payment confirmation.
- **Order status flow**: New → Preparing → Ready → Completed, staff-driven from the merchant app. At minimum, the "Ready"/"Completed" transition must trigger a WhatsApp message back to the customer.
- **Explicitly out of scope for MVP**: POS/KDS integration (Petpooja/UrbanPiper — planned Phase 2), kitchen printer auto-ticketing, loyalty/broadcast marketing, multi-outlet management, multi-user roles/permissions, free-text AI chatbot ordering (use structured/guided flows instead), any non-restaurant vertical, native mobile apps.
- **Data model guidance from the brief**: keep the order object "POS-integration-friendly" — don't bake in app-only assumptions — since Phase 2 needs to slot in a Petpooja order-injection API without re-architecting the order model. Per-order data: order ID, customer name/phone, items + quantities, total, payment status, order status, timestamps.

When scaffolding new code in this repo, favor structure that matches this brief (e.g., a clean separation between the WhatsApp conversation/webhook layer, the order/payment domain model, and the merchant dashboard) rather than inventing an unrelated architecture.
