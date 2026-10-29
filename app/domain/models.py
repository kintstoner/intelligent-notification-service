import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class Status(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class NotificationRequest:
    user_input: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: Status = Status.QUEUED
    # Why a request failed, or why it is still waiting; shown in the status response
    reason: str | None = None
    # Set once the request is in the processing queue, so processing it again does not enqueue it twice
    enqueued: bool = False
