from typing import Protocol

from domain.models import Notification, NotificationRequest


class NotificationFailed(Exception):
    """The provider did not take the notification; the message is the failure reason shown to the caller."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Notifier(Protocol):
    async def send(self, notification: Notification, request: NotificationRequest) -> None: ...
