# Product Roadmap

This document tracks OrderFlow's repositioning from a restaurant-only WhatsApp ordering MVP into **"OrderFlow — AI Revenue & Operations Engine for WhatsApp Businesses"**: a platform helping SMBs take orders, book appointments, support customers, retain customers, recover lost customers, track revenue, and automate operations, all through WhatsApp. The full product vision lives in `docs/product-vision.md`.

It has three parts:

- **Part A — Gap Analysis**: where the current implementation stands against the product vision.
- **Part B — Phased Roadmap**: the six phases that take us from today's state to the full vision.
- **Part C — Backlog**: concrete, scoped tickets for phases 2 through 6.

---

## Part A: Gap Analysis

OrderFlow's core today is a genuinely complete, production-quality WhatsApp ordering and appointment-booking platform — the commerce pipeline, the appointment pipeline, catalog, customers, payments, and a working merchant dashboard are all real, shipped code, not scaffolding. What's missing is essentially the entire layer that the new vision is named after: there is no AI anywhere in the codebase (zero LLM integration), and no growth/retention layer (no segmentation, campaigns, or win-back logic). In short: this is a solid data platform today, not yet an AI platform.

| Area | Status | Notes |
|---|---|---|
| WhatsApp Ordering | Complete | Full pipeline: Meta WhatsApp Cloud API webhook intake, tenant resolution, customer find-or-create, intent routing, native WhatsApp Flow (4-screen) as primary surface with a web fallback, cart/checkout, Razorpay payment links with signature-verified webhook, COD support, two coupled state machines (`payment_status`, `fulfillment_status`), staff-driven dashboard transitions, WhatsApp status notifications. Production-quality. |
| Appointment Booking | Complete (undocumented on Trello) | A parallel, fully-built module set mirrors the orders architecture — booking, reschedule, cancel via native WhatsApp Flow plus a web fallback, and dashboard pages with status transitions. This exists in the code but the Trello board has zero cards mentioning it — worth flagging as a documentation/visibility gap, not an engineering one. Missing: automated appointment reminders (see below). |
| AI Customer Assistant | Missing | No LLM/NLU integration anywhere in the codebase (zero grep hits for openai/anthropic/llm/gpt/embedding/chatbot/nlp in `backend/src`). Conversation routing today is deterministic intent matching, not AI. |
| Customer Support (24/7 AI) | Missing | The existing `faq` module (`backend/src/faq/`) is a static keyword/trigger-word lookup table that merchants author themselves — not an AI assistant, and not conversational (no follow-up handling, no order-status reasoning). |
| Customer Retention Engine | Missing | No segmentation, retention, or churn-detection logic anywhere (zero grep hits for segment/retention/churn outside unrelated matches). |
| Lost Customer Recovery Engine | Missing | No win-back or lapsed-customer detection logic; depends on the same missing segmentation primitives as the Retention Engine. |
| Campaign Engine | Missing | No broadcast/campaign engine of any kind, and WhatsApp Cloud API is the only outbound channel today — no email channel exists. |
| Revenue Dashboard | Partial | `DashboardHomePage.tsx` shows total revenue, total orders, order lifecycle counts, COD order count, a trend chart, and a recent-orders list. No customer lifetime value, no repeat-purchase rate, and no campaign performance (there are no campaigns to measure yet). |
| AI Business Copilot | Missing | No natural-language query interface over business data exists; this depends on both an LLM layer (Phase 3) and richer analytics (Phase 4 itself). |
| AI Action Engine | Missing | No autonomous action-taking capability of any kind. Depends on the Copilot's insight layer (Phase 4) and the campaign/retention primitives (Phase 2) to have anything meaningful to act on. |
| Industry-Specific Templates | Missing | The platform is vertical-agnostic at the data-model level only — `business_category` is a plain select field (Restaurant/Retail/Clothing/Auto Parts/Pharmacy/Other) with no vertical-specific workflow behind it (no pharmacy refill-subscription logic, no salon membership-renewal logic, no clinic no-show recovery, no grocery replenishment cadence). |
| Merchant Onboarding & Multi-tenancy | Complete | Self-serve onboarding wizard, JWT + Argon2 auth, per-merchant Razorpay and WhatsApp credentials, multi-tenant customer scoping. Meta Embedded Signup OAuth is in progress separately (existing Trello card, blocked on Meta App Review) — already tracked, not duplicated here. |
| Payments | Complete (flat pricing only) | Razorpay payment links plus COD are fully wired with signature-verified webhooks. Pricing itself is minimal by design: flat `Item.price` only, no tax, delivery fee, or discount/coupon logic anywhere. Existing Trello backlog cards already track adding tax, delivery fee, and discounts — not duplicated here. |

---

## Part B: Phased Roadmap

### Phase 1 — MVP (DONE)

Shipped. WhatsApp Commerce, Customer Ordering, Basic Catalog, Customer Profiles, Order Management, and WhatsApp Notifications are all complete, per `IMPLEMENTATION_PLAN.md`'s nine completed phases. Appointment Booking also shipped as a full parallel module set — arguably ahead of where this phase list originally expected. The one real gap left in this phase's scope is automated appointment reminders: booking, reschedule, and cancel all work end-to-end, but nothing proactively reminds a customer of an upcoming appointment (the only scheduled job today is the abandoned-order-cancellation sweep in `shared/scheduler.py`).

### Phase 2 — Growth Engine

This phase builds the primitives every later growth feature depends on: the ability to group customers by behavior (segmentation), the ability to message them at scale (the campaign engine), and the two concrete use cases that make those primitives valuable on day one — bringing lapsed customers back and keeping active ones engaged with reorder/refill/appointment reminders. It comes immediately after Phase 1 because it needs nothing but the order and customer data that already exists, and it's the direct revenue lever a merchant feels fastest: more repeat orders and recovered customers, with no AI dependency yet. This phase also closes the one leftover Phase 1 gap (appointment reminders), since it's really a special case of the same "automated outreach" capability being built here.

### Phase 3 — AI Employee

This phase introduces the platform's first LLM integration: a conversational AI layer that sits in front of (and eventually replaces parts of) the deterministic intent-routing and static FAQ lookup that exist today. It delivers AI-handled customer support, FAQ answering that can actually reason instead of keyword-match, and natural-language order/appointment support (status checks, rescheduling, troubleshooting) inside the existing WhatsApp conversation flow. It comes after Phase 2 rather than before it because it's architecturally independent of segmentation/campaigns but represents a much larger, riskier build (first LLM integration, cost controls, latency, hallucination risk) that benefits from the team having already shipped one growth-oriented phase and re-learned the codebase's extension points. Business value: reduces merchant staff support load and improves response time and availability (24/7) without adding headcount.

### Phase 4 — AI Business Copilot

With an LLM integration now proven in production (Phase 3), this phase turns it toward the merchant's own data: natural-language queries over revenue and operations ("how did I do last week versus the week before", "who are my top 10 customers"), a proper revenue/retention analytics dashboard (CLV, repeat-purchase rate, campaign performance — all currently missing per Part A), and AI-generated insights and recommendations surfaced proactively. It depends on Phase 3 for the LLM/prompt infrastructure and on Phase 2 for there to be campaign and retention data worth analyzing. Business value: turns raw operational data merchants already generate into decisions they wouldn't otherwise have time to find themselves.

### Phase 5 — AI Action Engine

This is where the platform stops just informing the merchant and starts acting on their behalf: autonomous campaign execution, automated customer recovery, and automated follow-ups, all gated behind an audit/approval log so every autonomous action is reviewable and reversible. It has to come last among the AI phases because it is a strict consumer of everything before it — it needs the Copilot's insight layer (Phase 4) to decide what's worth acting on, and the campaign/retention primitives (Phase 2) as the mechanism it acts through. Business value: this is the fullest expression of "AI Employee" — a system that not only tells the merchant what to do but does it, which is the highest-leverage (and highest-trust-requirement) capability in the vision, hence the mandatory guardrail ticket shipping alongside it at P0.

### Phase 6 — Industry Solutions

The final phase specializes the now-general platform for five verticals — Cloud Kitchens, Pharmacies, Clinics, Salons & Spas, and Grocery Stores — each layering vertical-specific workflows (refill subscriptions, no-show recovery, membership renewals, replenishment cadences) on top of the commerce, appointment, retention, and AI capabilities already built. It comes last by design: every vertical template is really a thin, opinionated configuration of Phases 1-5's general primitives (ordering, booking, segmentation, campaigns, AI support/copilot/actions), so building it earlier would mean building it against a moving, incomplete foundation. Business value: turns a generic platform into a set of sellable, industry-tailored products, which is typically where SMB SaaS sees its sharpest jump in conversion and willingness to pay.

---

## Part C: Backlog Tickets

### Phase 2 — Growth Engine

#### Customer Segmentation Engine
**Description:** Every growth feature in this phase and beyond (campaigns, retention, win-back, and eventually AI-driven actions) needs a way to group customers by behavior. This ticket builds that foundational primitive: rule-based segments (e.g. "ordered in last 7 days," "no order in 30+ days," "3+ orders lifetime," "high AOV") computed from existing order and customer data, with no new external dependencies.
**Acceptance Criteria:**
- New `segmentation` module following the existing modular-by-domain pattern (`domain/adapters/api`), scoped per-merchant like all other domain modules.
- Segment definitions are rule-based (field, operator, value) and stored per merchant; at minimum support recency, frequency, and monetary-value rules against `Order` history.
- A scheduled recompute job registered in `shared/scheduler.py` keeps segment membership fresh (e.g. nightly), plus an on-demand recompute API for the dashboard.
- Dashboard API exposes segment CRUD and segment membership counts; segments are queryable by other modules (campaigns, retention) via a stable interface, not by re-implementing the rules.
- Unit tests cover at least the recency/frequency/monetary rule types against seeded order fixtures.

**Priority:** P1
**Phase:** Phase 2

#### WhatsApp Broadcast Campaign Engine
**Description:** No broadcast/campaign capability exists today — WhatsApp Cloud API is only used for transactional order/appointment messages. This ticket adds the ability for a merchant to send an approved WhatsApp template message to a segment of customers, which is the delivery mechanism every later retention, win-back, and eventually autonomous-campaign ticket builds on.
**Acceptance Criteria:**
- New `campaigns` module (`domain/adapters/api`) with a `Campaign` entity: target segment, WhatsApp template reference, schedule (send-now or scheduled time), and status (draft/scheduled/sending/completed/failed).
- Reuses the existing `conversation/adapters/whatsapp_client.py` send path and its per-merchant token handling; sends are best-effort with failures logged per-recipient, matching the existing outbound-send convention, not raised as hard errors.
- Respects WhatsApp template-message rules (pre-approved templates only, no free-form text outside the 24-hour session window) and records per-recipient delivery status.
- Scheduled sends are driven by a new job in `shared/scheduler.py`; a merchant can view send progress and a basic delivery report from the dashboard.
- Rate-limits sends to avoid tripping Meta's per-number throughput limits.

**Priority:** P1
**Phase:** Phase 2

#### Automated Reorder / Refill Reminders
**Description:** There is currently no proactive outreach of any kind based on order history — this is the first concrete use of the segmentation + campaign primitives, nudging customers who order on a predictable cadence (e.g. weekly groceries, restaurant regulars) to reorder before they lapse.
**Acceptance Criteria:**
- Builds on the Customer Segmentation Engine's recency/frequency rules to identify customers "due" for a reorder based on their own historical ordering cadence per merchant.
- New scheduled job in `shared/scheduler.py` evaluates due customers daily and triggers a WhatsApp template send via the Broadcast Campaign Engine.
- Reminder cadence and eligibility (e.g. minimum order history required before a customer is eligible) are configurable per merchant, not hardcoded.
- Customers who already have an order in `new`/`processing`/`ready` status are excluded from that day's reminder run to avoid redundant nudges.
- Reminder sends are tracked distinctly from manual campaigns in reporting (i.e. attributable as "automated reorder reminder").

**Priority:** P1
**Phase:** Phase 2

#### Automated Appointment Reminders
**Description:** This closes the one concrete Phase 1 gap called out in Part A: appointment booking, reschedule, and cancel are fully built, but nothing reminds a customer of an upcoming appointment. Missed appointments are a direct revenue loss for appointment-based verticals (clinics, salons), so this is high-value and low-risk to ship early in Phase 2.
**Acceptance Criteria:**
- New scheduled job in `shared/scheduler.py`, following the same pattern as the existing abandoned-order-cancellation sweep, that finds upcoming appointments within a configurable reminder window (e.g. 24 hours before).
- Sends a WhatsApp template reminder via the existing `conversation/adapters/whatsapp_client.py` send path per appointment, respecting per-merchant WhatsApp credentials.
- Reminder is only sent once per appointment (idempotent — a flag or timestamp on the appointment record prevents duplicate sends on repeated job runs).
- Reminder is suppressed or updated appropriately if the appointment is rescheduled or cancelled after the reminder window is computed but before it fires.
- Reminder window is configurable per merchant (default 24 hours), and covered by a test for the idempotency and cancellation-suppression behavior.

**Priority:** P1
**Phase:** Phase 2

#### Lost Customer Win-back Campaigns
**Description:** No lapsed-customer detection or win-back logic exists anywhere in the codebase today. This ticket builds the Lost Customer Recovery Engine from the vision: automatically identifying customers who have gone quiet and triggering a win-back offer/message through the campaign engine.
**Acceptance Criteria:**
- Defines a "lapsed" segment (via the Segmentation Engine) as customers with no order/appointment within a configurable lookback window, per merchant.
- New scheduled job in `shared/scheduler.py` evaluates the lapsed segment on a recurring cadence and triggers a win-back WhatsApp campaign via the Broadcast Campaign Engine.
- Win-back message content/template is merchant-configurable (not hardcoded), and a customer who re-engages (places an order/books an appointment) is automatically excluded from future win-back sends until they lapse again.
- Win-back sends are capped in frequency per customer (e.g. no more than once every N days) to avoid spamming a lapsed customer repeatedly.
- Dashboard surfaces basic win-back campaign effectiveness (sent count, re-engaged count) as a foundation for the Phase 4 analytics work.

**Priority:** P1
**Phase:** Phase 2

#### Email Campaign Channel
**Description:** WhatsApp Cloud API is currently the only outbound channel in the platform. This ticket adds email as a second campaign channel, letting merchants reach customers who've opted into email or supplementing WhatsApp reach where template/session-window limits apply.
**Acceptance Criteria:**
- Extends the `campaigns` module's `Campaign` entity with a channel type (WhatsApp/email) rather than introducing a parallel campaign system.
- New adapter for a transactional email provider (e.g. SES/SendGrid — provider choice left to implementation, following the existing adapter pattern under `campaigns/adapters/`), configured per merchant similarly to how WhatsApp/Razorpay credentials are configured today.
- Customer model gains an optional email field and an explicit email-opt-in flag; email sends only go to opted-in customers with an email on file.
- Email sends integrate with the same segment-targeting and scheduling logic already built for WhatsApp campaigns, rather than duplicating targeting logic.
- Delivery/bounce status is tracked per recipient, consistent with the WhatsApp campaign's per-recipient delivery tracking.

**Priority:** P2
**Phase:** Phase 2

### Phase 3 — AI Employee

#### LLM-Backed Conversational AI Assistant (core NLU + routing layer)
**Description:** This is the platform's first LLM integration of any kind (confirmed zero hits today for openai/anthropic/llm/gpt/embedding/chatbot/nlp across `backend/src`). It replaces/augments the deterministic keyword intent-routing in `conversation/domain/intents.py` with an LLM-backed layer capable of understanding free-form customer messages, and is the foundation every other Phase 3-5 AI ticket depends on.
**Acceptance Criteria:**
- New `ai_assistant` module (`domain/adapters/api`) housing the LLM client adapter, prompt/context construction, and a routing layer that sits alongside (not immediately replacing) `conversation/domain/intents.py`, with a feature flag per merchant to control rollout.
- LLM adapter is provider-pluggable behind an interface (not hardcoded to one vendor), with per-merchant or per-tenant API key/config following the existing credential-encryption pattern (Fernet, per `shared/`).
- Falls back gracefully to the existing deterministic intent routing when the LLM call fails, times out, or returns low-confidence output — conversation flow must never dead-end because of an AI failure, consistent with the "best-effort, never raised" convention used for outbound WhatsApp sends.
- Cost and latency are bounded: request timeouts, a per-merchant/day token or spend cap, and logging of every LLM call (prompt, response, latency, cost) for observability and later audit.
- Test coverage includes the fallback path (LLM unavailable/erroring) and at least one realistic multi-turn conversation scenario.

**Priority:** P0
**Phase:** Phase 3

#### AI Customer Support (order status, FAQ answering, basic troubleshooting)
**Description:** Today's `faq` module is a static, merchant-authored keyword/trigger-word table with no reasoning ability. This ticket upgrades customer support to use the new LLM assistant layer to answer order-status questions and FAQs conversationally, and handle basic troubleshooting, directly inside the WhatsApp chat.
**Acceptance Criteria:**
- Builds on the LLM-Backed Conversational AI Assistant's routing layer; does not introduce a second, separate LLM integration.
- Can answer "where is my order" style questions by querying live order state from the `orders` module rather than hallucinating status.
- Existing merchant-authored FAQ entries (`faq` module) are used as grounding context for the LLM (retrieval-style), so merchants' existing FAQ content continues to add value rather than being discarded.
- Gracefully hands off to a human/staff-visible flag on the order (or a "contact us" message) when the assistant cannot confidently answer, rather than guessing.
- Response quality is evaluated against a fixed set of test conversations (order-status query, FAQ query, out-of-scope query) before enabling per merchant.

**Priority:** P1
**Phase:** Phase 3

#### AI Appointment Support (natural-language booking/reschedule/cancel)
**Description:** Appointment booking, reschedule, and cancel currently only work through the structured native WhatsApp Flow or web fallback. This ticket lets customers book, reschedule, or cancel an appointment through free-form conversational messages, using the LLM assistant to extract intent and parameters and drive the existing appointment domain logic.
**Acceptance Criteria:**
- Builds on the LLM-Backed Conversational AI Assistant; extracted booking parameters (service, date/time, customer) are validated against the existing `appointments` domain rules (availability, conflicts) before any booking/reschedule/cancel is committed — the LLM proposes, existing domain logic still enforces validity.
- Ambiguous or incomplete requests (e.g. missing a time) trigger a clarifying follow-up question rather than a failed or incorrect booking.
- Falls back to directing the customer to the existing native WhatsApp Flow or web booking fallback when the conversational path can't confidently resolve the request.
- All AI-driven appointment changes go through the same state machine and events as staff/customer-driven changes today, so downstream notification and dashboard behavior is unchanged.
- Test coverage includes a successful natural-language booking, a reschedule, a cancel, and an ambiguous-input clarification round-trip.

**Priority:** P1
**Phase:** Phase 3

### Phase 4 — AI Business Copilot

#### Natural-Language Business Query Copilot
**Description:** No natural-language interface over business data exists today — merchants can only view the fixed metrics on `DashboardHomePage.tsx`. This ticket lets a merchant ask free-form questions ("how many orders did I get last week", "who are my top customers") and get an answer grounded in their real data.
**Acceptance Criteria:**
- New `copilot` module (`domain/adapters/api`) reusing the LLM adapter built in Phase 3 rather than standing up a second LLM integration.
- Translates natural-language questions into constrained, safe queries against existing read models (orders, customers, appointments, campaigns) — no arbitrary/raw SQL generated or executed from LLM output.
- Scoped strictly per-tenant: a merchant's copilot session can never surface another merchant's data, enforced at the query layer, not just the prompt.
- Answers cite the underlying numbers/time range used (not just prose), so a merchant can verify the answer against the dashboard.
- Handles at minimum: revenue/order-count queries over a date range, top-N customers, and campaign performance queries (once Phase 2 campaigns exist).

**Priority:** P0
**Phase:** Phase 4

#### Revenue & Retention Analytics Dashboard (CLV, repeat-purchase rate, campaign performance)
**Description:** The current dashboard covers only totals and basic lifecycle counts — no customer lifetime value, repeat-purchase rate, or campaign performance, as noted in Part A. This ticket builds the deeper analytics needed both as a merchant-facing dashboard upgrade and as the data foundation the Copilot and later AI Insights tickets query against.
**Acceptance Criteria:**
- Extends the dashboard API/domain with computed metrics: customer lifetime value (per customer and merchant-wide average), repeat-purchase rate, and cohort/segment-level breakdowns (building on the Phase 2 Segmentation Engine).
- Campaign performance metrics (sent, delivered, re-engagement/conversion attributable to a campaign) are computed from the Phase 2 campaign and win-back send records.
- New dashboard page/section in `frontend/src/features/dashboard/` presenting these metrics, following the existing dashboard page conventions (e.g. `DashboardHomePage.tsx`).
- Metrics are computed efficiently (pre-aggregated or cached where needed) rather than recomputed from raw order tables on every dashboard load.
- Covered by tests verifying CLV and repeat-purchase-rate calculations against seeded order fixtures with known expected values.

**Priority:** P1
**Phase:** Phase 4

#### AI-Generated Business Insights & Recommendations
**Description:** Beyond answering direct questions (the Copilot) and showing raw metrics (the analytics dashboard), this ticket has the platform proactively surface insights a merchant wouldn't think to ask for — e.g. "your Tuesday orders dropped 20% this month" or "these 15 customers are about to lapse" — turning data the merchant already generates into a decision they'd otherwise miss.
**Acceptance Criteria:**
- New scheduled job (`shared/scheduler.py`) runs periodically (e.g. weekly) per merchant, using the analytics from the Revenue & Retention Analytics Dashboard as input to the LLM adapter to generate a small set of natural-language insights/recommendations.
- Insights are grounded strictly in computed metrics passed into the prompt (not free-invented by the LLM) and each insight references the underlying number/trend it's based on.
- Surfaced in the dashboard as a dismissible insights feed/panel; a merchant can mark an insight as acted-on or not relevant, and that feedback is stored for future tuning.
- Recommendation types explicitly include at least: a retention risk flag (ties to Phase 2 segments), a revenue trend callout, and a suggested campaign action (ties to Phase 2 campaign engine) as a next step, without automatically executing it.
- Rate-limited and cost-bounded consistent with the LLM cost controls established in Phase 3.

**Priority:** P2
**Phase:** Phase 4

### Phase 5 — AI Action Engine

#### Autonomous Campaign Execution Engine
**Description:** Phase 2 gave merchants a manual campaign engine; Phase 4 gave them AI-generated recommendations for what campaign to run. This ticket closes the loop by letting the platform autonomously create and launch a campaign (e.g. a win-back or reorder-reminder send) based on those recommendations, without a merchant manually configuring it each time.
**Acceptance Criteria:**
- Extends the Phase 2 `campaigns` module rather than introducing a separate execution path — autonomous campaigns are ordinary `Campaign` records with a `created_by=ai` provenance field.
- Every autonomously created campaign is logged to the AI Action Audit & Approval Log before it sends, including the triggering insight/rule and the target segment.
- Per-merchant setting controls autonomy level: fully autonomous (sends without review), or approval-required (drafted, held for merchant approval via dashboard before sending) — approval-required is the safe default for newly enabled merchants.
- Respects all existing campaign guardrails (template approval, session-window rules, send-rate limits) already built in Phase 2 — no bypass path for AI-originated sends.
- A merchant can disable autonomous campaign execution entirely at any time, with immediate effect on any pending/scheduled autonomous sends.

**Priority:** P1
**Phase:** Phase 5

#### Automated Customer Recovery Actions
**Description:** This extends the Phase 2 Lost Customer Win-back Campaigns from a fixed rule-based trigger into an AI-driven, adaptive recovery flow — e.g. varying the offer, timing, or channel based on what's worked for similar customers — rather than sending the same static win-back message to everyone who lapses.
**Acceptance Criteria:**
- Builds on the Phase 2 win-back job and Phase 2 Segmentation Engine's lapsed-customer detection; does not duplicate lapsed-customer identification logic.
- Uses the Copilot/analytics layer (Phase 4) to select a recovery action (message variant, offer, timing) per customer or cohort, with the actual send still going through the existing Campaign Engine send path.
- Every automated recovery action is logged to the AI Action Audit & Approval Log, including which variant/offer was chosen and why (the input signal it acted on).
- Respects the same per-customer frequency caps established in the Phase 2 win-back ticket to avoid over-messaging a given customer.
- Recovery effectiveness (re-engagement rate per variant) feeds back into future action selection and is visible in the dashboard.

**Priority:** P1
**Phase:** Phase 5

#### Automated Order / Appointment Follow-ups
**Description:** No post-transaction follow-up exists today (e.g. asking for feedback after a completed order, or checking in after a completed appointment). This ticket adds automated, AI-drafted follow-up messages tied to the existing order/fulfillment and appointment status events.
**Acceptance Criteria:**
- Hooks into the existing event bus used by `orders/domain/events.py` (and its appointment-module equivalent) so follow-ups trigger off the existing `completed` status transition rather than a new polling job.
- Follow-up message content is AI-drafted (via the Phase 3 LLM adapter) but constrained to merchant-approved templates/tone guidelines, consistent with WhatsApp template-message rules.
- Configurable per merchant: which events trigger a follow-up, delay after completion, and whether follow-ups are enabled at all (default off for new merchants).
- Logged to the AI Action Audit & Approval Log like other autonomous sends in this phase.
- Does not duplicate a follow-up for the same order/appointment if the job or event fires more than once (idempotent).

**Priority:** P2
**Phase:** Phase 5

#### AI Action Audit & Approval Log (safety/guardrail layer for autonomous actions)
**Description:** This is the mandatory safety layer for every autonomous-action ticket in this phase — without it, none of the other Phase 5 tickets should ship. It gives merchants (and the team) a complete, reviewable record of every action the AI took or proposed on the merchant's behalf, and a mechanism to require approval before an action executes.
**Acceptance Criteria:**
- New `ai_actions` module (`domain/adapters/api`) recording every autonomous or AI-proposed action: type, target (customer/segment/order/appointment), the input/insight that triggered it, timestamp, status (proposed/approved/executed/rejected/failed), and outcome.
- Dashboard page listing the action log per merchant, filterable by action type and status, with the ability to approve or reject pending actions when a merchant's autonomy setting requires approval.
- All three other Phase 5 tickets (Campaign Execution, Customer Recovery, Follow-ups) write to this log before executing, not after — a proposed action must exist in the log before it can transition to executed.
- A merchant-level kill switch immediately halts all pending autonomous actions and prevents new ones from being proposed, independent of per-feature autonomy settings.
- Retention policy for the action log is defined (e.g. indefinite or a configurable minimum retention) since this is the primary trust/accountability record for the AI Action Engine.

**Priority:** P0
**Phase:** Phase 5

### Phase 6 — Industry Solutions

#### Cloud Kitchen Vertical Template
**Description:** Cloud kitchens share the existing restaurant ordering flow but typically run multiple virtual brands from one kitchen and have no dine-in/table concerns. This ticket packages the existing commerce core into a cloud-kitchen-specific onboarding and dashboard configuration rather than building new domain logic.
**Acceptance Criteria:**
- Onboarding wizard gains a "Cloud Kitchen" path under the existing `business_category` selection, pre-configuring catalog/menu setup defaults appropriate to a multi-brand kitchen (e.g. support for multiple named virtual-brand catalogs under one merchant, if not already possible).
- Dashboard defaults (order list views, prep-time expectations) are tuned for cloud-kitchen operational patterns (delivery-only, no table/dine-in fields shown).
- No changes to the underlying `orders`/`catalog` domain logic are required beyond configuration — this ticket is a template/config layer, consistent with the vertical-agnostic data model already in place.
- Reuses existing tax/delivery-fee/discount features (tracked separately on Trello) once available, rather than building kitchen-specific pricing logic.
- Documented as a selectable onboarding path with its own README/setup notes for merchant success/support use.

**Priority:** P2
**Phase:** Phase 6

#### Pharmacy Vertical Template
**Description:** Pharmacies need two things the general platform doesn't yet support: recurring refill subscriptions and structured prescription collection during ordering. This ticket adds both on top of the existing ordering and reorder-reminder infrastructure from Phase 2.
**Acceptance Criteria:**
- Extends the Phase 2 Automated Reorder / Refill Reminders job with a pharmacy-specific mode: merchant or customer can set an explicit refill cadence per item (not just inferred from order history).
- Ordering flow (native WhatsApp Flow and web fallback) gains an optional prescription-upload/collection step for items flagged as prescription-required in the catalog, storing the reference against the order for staff review before fulfillment.
- New `business_category=Pharmacy` onboarding path pre-configures refill reminders and prescription-collection settings by default.
- Orders with a pending/unverified prescription are visibly flagged in the dashboard and excluded from auto-progressing fulfillment status until staff clears them.
- Refill reminder cadence and prescription-requirement flags are stored per catalog item, following the existing `Item` model's per-merchant scoping.

**Priority:** P1
**Phase:** Phase 6

#### Clinic Vertical Template
**Description:** Clinics are appointment-based and are especially exposed to no-shows, which directly cost revenue. This ticket layers clinic-specific follow-up reminders and no-show recovery on top of the existing appointment booking and Phase 2/5 reminder and recovery infrastructure.
**Acceptance Criteria:**
- New `business_category=Clinic` onboarding path pre-configures the Automated Appointment Reminders job with clinic-appropriate defaults (e.g. multiple reminder touchpoints: 24h and 2h before).
- Adds no-show detection: an appointment left in a non-completed, non-cancelled state past its scheduled time is flagged, following the existing `appointments` state machine conventions.
- No-show customers are automatically eligible for a follow-up/recovery outreach (reusing the Phase 5 Automated Customer Recovery Actions or Phase 2 campaign engine, whichever is available at build time) offering to rebook.
- Dashboard surfaces a no-show rate metric per clinic, building on the Phase 4 analytics dashboard's metric infrastructure rather than a one-off calculation.
- Post-visit follow-up (e.g. "how did your visit go") reuses the Phase 5 Automated Order/Appointment Follow-ups ticket's infrastructure rather than a separate implementation.

**Priority:** P1
**Phase:** Phase 6

#### Salon & Spa Vertical Template
**Description:** Salons and spas commonly sell memberships/packages that need renewal outreach — a pattern the general platform has no concept of today (appointments are one-off bookings with no recurring-membership model). This ticket adds a lightweight membership concept and renewal reminders on top of the existing appointment and campaign infrastructure.
**Acceptance Criteria:**
- New minimal `membership` concept (in the `appointments` module or a small new module, following the domain/adapters/api pattern) associating a customer with a recurring package and an expiry/renewal date, scoped per merchant.
- New `business_category=Salon & Spa` onboarding path exposes membership setup during onboarding/catalog configuration.
- New scheduled job (or extension of an existing Phase 2 reminder job) sends a renewal reminder via the campaign engine as a membership approaches expiry, configurable lead time per merchant.
- Dashboard shows active/expiring/expired membership counts, reusing the Phase 4 analytics dashboard's presentation conventions.
- Renewal reminders respect the same per-customer send-frequency caps established in Phase 2 to avoid over-messaging.

**Priority:** P2
**Phase:** Phase 6

#### Grocery Vertical Template
**Description:** Grocery ordering is high-frequency and highly predictable, making it the strongest fit for the Phase 2 reorder-reminder infrastructure, but needs a replenishment cadence tuned to grocery buying patterns (e.g. weekly staples) rather than the more general reorder logic built for other verticals.
**Acceptance Criteria:**
- New `business_category=Grocery` onboarding path pre-configures the Automated Reorder / Refill Reminders job with grocery-appropriate defaults (shorter, more frequent cadence than the general default).
- Supports per-item replenishment cadence hints in the catalog (e.g. "milk: weekly," "rice: monthly") that feed into the reorder-reminder job's due-date calculation, extending the same mechanism built for the Pharmacy template's refill cadence rather than duplicating it.
- Catalog/ordering UI defaults are tuned for grocery's larger item counts and quantity-based ordering (no clinic/salon-specific fields shown).
- Reuses existing tax/delivery-fee support (tracked separately on Trello) once available rather than building grocery-specific pricing logic.
- Documented as a selectable onboarding path with its own setup notes, consistent with the other vertical templates in this phase.

**Priority:** P2
**Phase:** Phase 6
