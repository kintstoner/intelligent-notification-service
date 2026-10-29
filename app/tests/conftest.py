import pytest
from fastapi.testclient import TestClient

from domain.models import Status
from main import app


@pytest.fixture
def client():
    # The context manager runs the lifespan, as uvicorn does
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def handler_calls(client):
    """Replaces the real processing with one that records the request and marks it sent."""
    calls = []

    async def handler(request):
        calls.append(request.id)
        request.status = Status.SENT

    app.state.pipeline.handler = handler
    return calls


@pytest.fixture
def full_queue(client, monkeypatch):
    monkeypatch.setattr(app.state.pipeline, "submit", lambda request: False)
