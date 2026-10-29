from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes_requests import router as requests_router
from infra.repository import InMemoryRequestRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.repository = InMemoryRequestRepository()
    yield


app = FastAPI(title="Notification Service (Technical Test)", lifespan=lifespan)
app.include_router(requests_router)
