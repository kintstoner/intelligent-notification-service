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


class AnswerRejected(Exception):
    """The AI answer gives no notification that can be sent. Retryable when asking the AI again could fix it."""

    def __init__(self, reason: str, *, retryable: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


def interpret_answer(answer: str, user_input: str) -> Notification:
    """
    Guardrails, deterministic fallback and validation applied to one AI answer. Pure: the processor and the offline
    prompt evaluation (evals/) judge an answer with exactly the same rules.
    """
    try:
        extraction = parse_ai_output(answer)
    except AIRefusal as refusal:
        if refusal.kind == RefusalKind.MISSING_INFORMATION:
            raise AnswerRejected("missing_information", retryable=False) from refusal
        raise AnswerRejected("ai_refused", retryable=True) from refusal
    except MalformedOutput as error:
        raise AnswerRejected("ai_output_unreadable", retryable=True) from error

    extraction = complete(extraction, user_input)
    if extraction.message is None:
        raise AnswerRejected("missing_message", retryable=True)
    if extraction.to is None or extraction.type is None:
        raise AnswerRejected("missing_information", retryable=False)
    try:
        return Notification(to=extraction.to, message=extraction.message, type=extraction.type)
    except ValidationError as error:
        raise AnswerRejected("invalid_notification", retryable=False) from error


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
                logger.info(
                    "Request %s: AI attempt %d failed (%s)",
                    request.id,
                    request.ai_attempts,
                    reason,
                    extra={"request_id": request.id, "reason": reason, "ai_attempts": request.ai_attempts},
                )
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
            return interpret_answer(answer, user_input)
        except AnswerRejected as rejection:
            if rejection.retryable:
                raise _Retry(rejection.reason) from rejection
            raise _GiveUp(rejection.reason) from rejection

    @staticmethod
    def _fail(request: NotificationRequest, reason: str) -> None:
        request.status = Status.FAILED
        request.reason = reason
        logger.warning(
            "Request %s failed: %s",
            request.id,
            reason,
            extra={"request_id": request.id, "reason": reason, "ai_attempts": request.ai_attempts},
        )
