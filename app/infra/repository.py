from typing import Protocol

from domain.models import NotificationRequest


class RequestRepository(Protocol):
    def add(self, request: NotificationRequest) -> None: ...

    def get(self, request_id: str) -> NotificationRequest | None: ...


class InMemoryRequestRepository:
    """
    Keeps requests in a dict. Safe without a lock: every access runs on the single event loop and none of them awaits.
    With several uvicorn processes each one would have its own dict; a shared store (Redis, Postgres) would implement
    the same protocol.
    """

    def __init__(self) -> None:
        self._requests: dict[str, NotificationRequest] = {}

    def add(self, request: NotificationRequest) -> None:
        self._requests[request.id] = request

    def get(self, request_id: str) -> NotificationRequest | None:
        return self._requests.get(request_id)
