import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from appointment_flow.api.router import router as appointment_flow_router
from conversation.api.router import router as whatsapp_webhook_router
from dashboard_api.api.router import router as dashboard_api_router
from flows.api.router import router as whatsapp_flows_router
from notifications.wiring import register_notification_handlers
from ordering_flow.api.router import router as ordering_flow_router
from payments.api.router import router as payments_webhook_router
from shared.config import get_settings
from shared.logging import configure_logging
from shared.scheduler import create_scheduler

configure_logging()
settings = get_settings()
request_logger = logging.getLogger("orderflow.request")

# Module level, not inside lifespan -- lifespan doesn't run under the
# ASGITransport tests use, so subscriptions registered there would never
# actually fire in tests.
register_notification_handlers()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    scheduler = create_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="Orderflow API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_api_router)
app.include_router(whatsapp_webhook_router)
app.include_router(whatsapp_flows_router)
app.include_router(ordering_flow_router)
app.include_router(appointment_flow_router)
app.include_router(payments_webhook_router)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    request_logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
