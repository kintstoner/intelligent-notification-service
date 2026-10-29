import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx
from tenacity import AsyncRetrying, RetryCallState, retry_if_exception_type, stop_after_attempt

from domain.models import Notification, NotificationRequest, Status

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]


class NotificationFailed(Exception):
    """The provider did not take the notification; the reason is shown to the caller."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class RateLimiter:
    """
    Mirrors the provider's own rule: at most max_calls in any sliding window of window_s seconds. A burst goes out at
    once while the window has room, so an idle service sends without delay; once it is full, the next call waits for
    the oldest one to leave the window. max_calls stays below the provider's 50 to absorb the variation between a
    call leaving here and reaching the provider.
    """

    def __init__(
        self,
        max_calls: int,
        window_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._max_calls = max_calls
        self._window_s = window_s
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            while self._calls and self._calls[0] + self._window_s <= now:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                await self._sleep(self._calls[0] + self._window_s - now)
                # The wait was for exactly this call to leave the window; comparing times again could miss it by a
                # rounding error and wait forever
                self._calls.popleft()
            self._calls.append(self._clock())


class Limiter(Protocol):
    async def acquire(self) -> None: ...


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class Notifier:
    """
    Sends one notification to the provider. Rate limits (429), server errors and timeouts are retried with
    exponential backoff and jitter, up to max_attempts; every attempt waits for its turn in the rate limiter.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        limiter: Limiter,
        timeout_s: float,
        max_attempts: int,
        backoff_s: float,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._client = client
        self._limiter = limiter
        self._timeout_s = timeout_s
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._sleep = sleep

    async def deliver(self, notification: Notification, request: NotificationRequest) -> None:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=self._wait,
            retry=retry_if_exception_type(_Retryable),
            sleep=self._sleep,
            reraise=True,
        )
        try:
            async for attempt in retrying:
                with attempt:
                    await self._attempt(notification, request)
        except _Retryable as error:
            raise NotificationFailed(error.reason) from error

    async def _attempt(self, notification: Notification, request: NotificationRequest) -> None:
        await self._limiter.acquire()
        request.notify_attempts += 1
        try:
            response = await self._client.post("/v1/notify", json=notification.model_dump(), timeout=self._timeout_s)
        except httpx.TransportError as error:
            raise _Retryable("provider_error") from error
        if response.status_code == 429:
            raise _Retryable("rate_limited", _retry_after(response))
        if response.status_code >= 500:
            raise _Retryable("provider_error", _retry_after(response))
        if response.status_code >= 400:
            raise NotificationFailed("provider_rejected")

    def _wait(self, state: RetryCallState) -> float:
        error = state.outcome.exception() if state.outcome else None
        if isinstance(error, _Retryable) and error.retry_after is not None:
            return error.retry_after
        # Full jitter within [base, 2 * base], base doubling per attempt: retries do not arrive in lockstep
        base = self._backoff_s * 2 ** (state.attempt_number - 1)
        return random.uniform(base, 2 * base)


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None


class Deliverer(Protocol):
    async def deliver(self, notification: Notification, request: NotificationRequest) -> None: ...


class DeliveryQueue:
    """
    Second stage of the pipeline: notifications wait here for the provider's pace, so the AI workers never sit
    idle behind the rate limit. Delivery sets each request's final status.
    """

    def __init__(self, notifier: Deliverer, concurrency: int, max_size: int) -> None:
        self._notifier = notifier
        self._concurrency = concurrency
        self._queue: asyncio.Queue[tuple[Notification, NotificationRequest]] = asyncio.Queue(maxsize=max_size)
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._work(), name=f"delivery-{i}") for i in range(self._concurrency)]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    @property
    def backlog(self) -> int:
        return self._queue.qsize()

    def submit(self, notification: Notification, request: NotificationRequest) -> None:
        try:
            self._queue.put_nowait((notification, request))
        except asyncio.QueueFull:
            _fail(request, "delivery_backlog_full")

    async def _work(self) -> None:
        while True:
            notification, request = await self._queue.get()
            try:
                await self._notifier.deliver(notification, request)
            except NotificationFailed as failure:
                _fail(request, failure.reason)
            except Exception:
                logger.exception("Unexpected error delivering request %s", request.id, extra={"request_id": request.id})
                _fail(request, "internal_error")
            else:
                request.status = Status.SENT
                request.reason = None
                logger.info(
                    "Request %s sent by %s",
                    request.id,
                    notification.type,
                    extra={
                        "request_id": request.id,
                        "type": notification.type,
                        "ai_attempts": request.ai_attempts,
                        "notify_attempts": request.notify_attempts,
                    },
                )
            finally:
                self._queue.task_done()


def _fail(request: NotificationRequest, reason: str) -> None:
    request.status = Status.FAILED
    request.reason = reason
    logger.warning(
        "Request %s failed: %s",
        request.id,
        reason,
        extra={"request_id": request.id, "reason": reason, "notify_attempts": request.notify_attempts},
    )
