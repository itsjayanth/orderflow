"""The fixed 6-row billing_plans pricing table (3 tiers x 2 billing
intervals), seeded by the Alembic migration that creates billing_plans and
reused verbatim by the test suite's schema-reset fixture (tests recreate
schema via Base.metadata.create_all, not by running migrations, so this
seed data needs its own explicit insertion point in tests too -- see
tests/conftest.py's _reset_db). Single source of truth so the two never
drift apart.

razorpay_plan_id is intentionally absent from each row here -- every seeded
plan starts in dummy-gateway mode (NULL) until a real platform Razorpay
account exists and these get backfilled via the Razorpay dashboard/API."""

SEED_PLANS: list[dict[str, object]] = [
    {
        "tier": "starter",
        "billing_interval": "monthly",
        "display_name": "Starter",
        "price_inr": "999.00",
        "order_cap": 150,
        "whatsapp_flow_enabled": False,
        "branding_required": True,
    },
    {
        "tier": "starter",
        "billing_interval": "annual",
        "display_name": "Starter (Annual)",
        "price_inr": "9990.00",
        "order_cap": 150,
        "whatsapp_flow_enabled": False,
        "branding_required": True,
    },
    {
        "tier": "growth",
        "billing_interval": "monthly",
        "display_name": "Growth",
        "price_inr": "2499.00",
        "order_cap": 750,
        "whatsapp_flow_enabled": True,
        "branding_required": False,
    },
    {
        "tier": "growth",
        "billing_interval": "annual",
        "display_name": "Growth (Annual)",
        "price_inr": "24990.00",
        "order_cap": 750,
        "whatsapp_flow_enabled": True,
        "branding_required": False,
    },
    {
        "tier": "pro",
        "billing_interval": "monthly",
        "display_name": "Pro",
        "price_inr": "4999.00",
        "order_cap": None,
        "whatsapp_flow_enabled": True,
        "branding_required": False,
    },
    {
        "tier": "pro",
        "billing_interval": "annual",
        "display_name": "Pro (Annual)",
        "price_inr": "49990.00",
        "order_cap": None,
        "whatsapp_flow_enabled": True,
        "branding_required": False,
    },
]
