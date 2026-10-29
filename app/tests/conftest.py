import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    # The context manager runs the lifespan, as uvicorn does
    with TestClient(app) as test_client:
        yield test_client
