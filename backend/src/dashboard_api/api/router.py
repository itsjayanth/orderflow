from fastapi import APIRouter

from catalog.api.router import router as catalog_router
from customers.api.router import router as customers_router
from faq.api.router import router as faq_router
from identity.api.router import router as identity_router
from notifications.api.router import router as notifications_router
from onboarding.api.router import router as onboarding_router
from orders.api.router import router as orders_router
from payments.api.dashboard_router import router as payments_dashboard_router

router = APIRouter()
router.include_router(identity_router)
router.include_router(onboarding_router)
router.include_router(catalog_router)
router.include_router(faq_router)
router.include_router(customers_router)
router.include_router(orders_router)
router.include_router(payments_dashboard_router)
router.include_router(notifications_router)
