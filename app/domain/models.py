import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, field_validator, model_validator

from domain.contacts import is_email, is_phone, normalise_phone


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
    ai_attempts: int = 0
    notify_attempts: int = 0


class Notification(BaseModel):
    """What is sent to the provider. Built only from a validated extraction."""

    to: str
    message: str
    type: Literal["email", "sms"]

    @field_validator("to", "message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def recipient_matches_type(self) -> Self:
        if self.type == "email" and not is_email(self.to):
            raise ValueError("an email notification needs an email address")
        if self.type == "sms":
            if not is_phone(self.to):
                raise ValueError("an sms notification needs a phone number")
            self.to = normalise_phone(self.to)
        return self
