from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes_requests import router as requests_router
from config import settings
from domain.models import NotificationRequest
from infra.repository import InMemoryRequestRepository
from services.pipeline import Pipeline


async def _not_wired_yet(request: NotificationRequest) -> None:
    raise NotImplementedError("extraction and notification are wired in the next milestones")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.repository = InMemoryRequestRepository()
    app.state.pipeline = Pipeline(_not_wired_yet, workers=settings.workers, max_size=settings.queue_max_size)
    app.state.pipeline.start()
    yield
    await app.state.pipeline.stop()


app = FastAPI(title="Notification Service (Technical Test)", lifespan=lifespan)
app.include_router(requests_router)
