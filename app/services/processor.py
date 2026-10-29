import logging
from typing import Protocol

from pydantic import ValidationError

from domain.models import Notification, NotificationRequest, Status
from services.extractor import ExtractionError
from services.fallback_extractor import complete
from services.guardrails import AIRefusal, MalformedOutput, RefusalKind, parse_ai_output

logger = logging.getLogger(__name__)


class AIExtractor(Protocol):
    async def extract(self, user_input: str) -> str: ...


class Delivery(Protocol):
    def submit(self, notification: Notification, request: NotificationRequest) -> None: ...


class _Retry(Exception):
    """This attempt failed in a way another AI call could fix."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


class _GiveUp(Exception):
    """This request cannot succeed; asking the AI again would only cost another call."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


class RequestProcessor:
    """
    Turns one request into a validated notification (AI extraction, guardrails, deterministic fallback, validation)
    and hands it to delivery, which sends it at the provider's pace and sets the final status.

    The AI is asked at most max_ai_attempts times, and again only when that can help: a refusal, an answer cut
    short, a missing message or a network failure. Dirty JSON is never a reason to ask again; the guardrails fix it.
    """

    def __init__(self, extractor: AIExtractor, delivery: Delivery, max_ai_attempts: int, cache_enabled: bool) -> None:
        self._extractor = extractor
        self._delivery = delivery
        self._max_ai_attempts = max_ai_attempts
        # Off by default; in production it would act as deduplication of identical requests
        self._cache: dict[str, Notification] | None = {} if cache_enabled else None

    async def process(self, request: NotificationRequest) -> None:
        try:
            notification = await self._notification_for(request)
        except _GiveUp as failure:
            self._fail(request, failure.reason)
            return
        # Stays processing until delivery reports the outcome
        self._delivery.submit(notification, request)

    async def _notification_for(self, request: NotificationRequest) -> Notification:
        if self._cache is not None and (cached := self._cache.get(request.user_input)):
            return cached
        reason = "ai_unavailable"
        for _ in range(self._max_ai_attempts):
            request.ai_attempts += 1
            try:
                notification = await self._attempt(request.user_input)
            except _Retry as retry:
                reason = retry.reason
                logger.info("Request %s: AI attempt %d failed (%s)", request.id, request.ai_attempts, reason)
                continue
            if self._cache is not None:
                self._cache[request.user_input] = notification
            return notification
        raise _GiveUp(reason)

    async def _attempt(self, user_input: str) -> Notification:
        try:
            answer = await self._extractor.extract(user_input)
        except ExtractionError as error:
            if error.retryable:
                raise _Retry("ai_unavailable") from error
            raise _GiveUp("ai_unavailable") from error

        try:
            extraction = parse_ai_output(answer)
        except AIRefusal as refusal:
            if refusal.kind == RefusalKind.MISSING_INFORMATION:
                raise _GiveUp("missing_information") from refusal
            raise _Retry("ai_refused") from refusal
        except MalformedOutput as error:
            raise _Retry("ai_output_unreadable") from error

        extraction = complete(extraction, user_input)
        if extraction.message is None:
            raise _Retry("missing_message")
        if extraction.to is None or extraction.type is None:
            raise _GiveUp("missing_information")
        try:
            return Notification(to=extraction.to, message=extraction.message, type=extraction.type)
        except ValidationError as error:
            raise _GiveUp("invalid_notification") from error

    @staticmethod
    def _fail(request: NotificationRequest, reason: str) -> None:
        request.status = Status.FAILED
        request.reason = reason
        logger.warning("Request %s failed: %s (%d AI attempts)", request.id, reason, request.ai_attempts)
