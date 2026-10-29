from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from api.routes_requests import router as requests_router
from config import settings
from infra.repository import InMemoryRequestRepository
from services.extractor import Extractor
from services.notifier import DeliveryQueue, Notifier, RateLimiter
from services.pipeline import Pipeline
from services.processor import RequestProcessor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One connection pool for both provider endpoints, shared by every worker
    client = httpx.AsyncClient(
        base_url=settings.provider_base_url,
        headers={"X-API-Key": settings.provider_api_key},
        limits=httpx.Limits(max_connections=settings.workers + settings.notify_concurrency),
    )
    notifier = Notifier(
        client,
        RateLimiter(settings.notify_rate_per_s),
        timeout_s=settings.notify_timeout_s,
        max_attempts=settings.notify_max_attempts,
        backoff_s=settings.notify_backoff_s,
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
    delivery.start()
    pipeline.start()
    yield
    await pipeline.stop()
    await delivery.stop()
    await client.aclose()


app = FastAPI(title="Notification Service (Technical Test)", lifespan=lifespan)
app.include_router(requests_router)
