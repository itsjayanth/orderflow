from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from conversation.api.router import router as whatsapp_webhook_router
from dashboard_api.api.router import router as dashboard_api_router
from ordering_flow.api.router import router as ordering_flow_router
from payments.api.router import router as payments_webhook_router
from shared.config import get_settings
from shared.scheduler import create_scheduler

settings = get_settings()


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
app.include_router(ordering_flow_router)
app.include_router(payments_webhook_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
