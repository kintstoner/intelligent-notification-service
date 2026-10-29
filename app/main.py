from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from api.routes_requests import router as requests_router
from config import settings
from infra.json_logging import configure_logging
from infra.repository import InMemoryRequestRepository
from services.extractor import Extractor
from services.notifier import DeliveryQueue, Notifier, RateLimiter
from services.pipeline import Pipeline
from services.processor import RequestProcessor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    # One connection pool for both provider endpoints, shared by every worker
    client = httpx.AsyncClient(
        base_url=settings.provider_base_url,
        headers={"X-API-Key": settings.provider_api_key},
        limits=httpx.Limits(max_connections=settings.workers + settings.notify_concurrency),
    )
    notifier = Notifier(
        client,
        RateLimiter(settings.notify_window_max_calls, settings.notify_window_s),
        timeout_s=settings.notify_timeout_s,
        max_attempts=settings.notify_max_attempts,
        backoff_s=settings.notify_backoff_s,
        max_retry_after_s=settings.notify_max_retry_after_s,
    )
    delivery = DeliveryQueue(notifier, concurrency=settings.notify_concurrency, max_size=settings.queue_max_size)
    processor = RequestProcessor(
        Extractor(client, timeout_s=settings.ai_timeout_s),
        delivery,
        max_ai_attempts=1 + settings.ai_max_retries,
        cache_enabled=settings.extraction_cache_enabled,
    )
    pipeline = Pipeline(processor.process, workers=settings.workers, max_size=settings.queue_max_size)

    app.state.repository = InMemoryRequestRepository()
    app.state.pipeline = pipeline
    app.state.delivery = delivery
    delivery.start()
    pipeline.start()
    yield
    await pipeline.stop()
    await delivery.stop()
    await client.aclose()


app = FastAPI(title="Notification Service (Technical Test)", lifespan=lifespan)
app.include_router(requests_router)


@app.get("/health", tags=["operations"])
async def health() -> dict:
    """Liveness plus the backlog of each stage: how many requests wait for the AI and how many for the provider."""
    return {
        "status": "ok",
        "awaiting_ai": app.state.pipeline.backlog,
        "awaiting_delivery": app.state.delivery.backlog,
    }
