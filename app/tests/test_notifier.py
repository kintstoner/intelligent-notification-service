import asyncio
import json

import httpx
import pytest
import respx

from domain.models import Notification, NotificationRequest, Status
from services.notifier import DeliveryQueue, NotificationFailed, Notifier, RateLimiter

BASE_URL = "http://provider.test"
NOTIFICATION = Notification(to="juan@example.com", message="Tu paquete está en camino", type="email")


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


async def test_a_burst_within_the_window_limit_goes_out_without_waiting():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=45, window_s=10, clock=clock, sleep=clock.sleep)

    for _ in range(45):
        await limiter.acquire()

    assert clock.sleeps == []


async def test_the_call_over_the_limit_waits_until_the_oldest_one_leaves_the_window():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=45, window_s=10, clock=clock, sleep=clock.sleep)
    for _ in range(45):
        await limiter.acquire()
        clock.now += 0.1

    await limiter.acquire()

    # The first call was at t=0; the 46th may go at t=10
    assert clock.now == pytest.approx(10)


async def test_never_more_calls_than_the_limit_in_any_window():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=45, window_s=10, clock=clock, sleep=clock.sleep)
    times = []

    for _ in range(300):
        await limiter.acquire()
        times.append(clock.now)
        clock.now += 0.01

    busiest = max(sum(1 for t in times if start <= t < start + 10) for start in times)
    assert busiest == 45
    # Never faster than the limit allows: after the first window, at most 45 calls per 10 s
    assert times[-1] - times[0] >= (300 - 45) / 45 * 10


async def test_the_rate_limiter_does_not_wait_after_an_idle_period():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=45, window_s=10, clock=clock, sleep=clock.sleep)
    for _ in range(45):
        await limiter.acquire()
    clock.now += 60

    await limiter.acquire()

    assert clock.sleeps == []


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, headers={"X-API-Key": "key"}) as http_client:
        yield http_client


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def notifier(client, sleeps):
    async def record_sleep(seconds):
        sleeps.append(seconds)

    async def no_wait():
        return None

    limiter = type("NoLimit", (), {"acquire": staticmethod(no_wait)})()
    return Notifier(client, limiter, timeout_s=1.0, max_attempts=3, backoff_s=0.5, sleep=record_sleep)


def delivered():
    return httpx.Response(200, json={"status": "delivered", "provider_id": "p-1"})


@respx.mock
async def test_delivers_the_notification_with_the_api_key(notifier):
    route = respx.post(f"{BASE_URL}/v1/notify").mock(return_value=delivered())
    request = NotificationRequest(user_input="x")

    await notifier.deliver(NOTIFICATION, request)

    sent = route.calls.last.request
    assert sent.headers["X-API-Key"] == "key"
    assert json.loads(sent.content) == {
        "to": "juan@example.com",
        "message": "Tu paquete está en camino",
        "type": "email",
    }
    assert request.notify_attempts == 1


@respx.mock
@pytest.mark.parametrize(
    "first_failure",
    [httpx.Response(429, json={"error": "Rate limit exceeded"}), httpx.Response(500), httpx.ReadTimeout("slow")],
)
async def test_retries_rate_limits_server_errors_and_timeouts(notifier, first_failure):
    respx.post(f"{BASE_URL}/v1/notify").mock(side_effect=[first_failure, delivered()])
    request = NotificationRequest(user_input="x")

    await notifier.deliver(NOTIFICATION, request)

    assert request.notify_attempts == 2


@respx.mock
@pytest.mark.parametrize(("status", "reason"), [(429, "rate_limited"), (503, "provider_error")])
async def test_gives_up_after_the_configured_attempts(notifier, status, reason):
    route = respx.post(f"{BASE_URL}/v1/notify").respond(status)
    request = NotificationRequest(user_input="x")

    with pytest.raises(NotificationFailed) as failure:
        await notifier.deliver(NOTIFICATION, request)

    assert failure.value.reason == reason
    assert route.call_count == 3


@respx.mock
async def test_a_rejected_notification_is_not_retried(notifier):
    route = respx.post(f"{BASE_URL}/v1/notify").respond(422)

    with pytest.raises(NotificationFailed) as failure:
        await notifier.deliver(NOTIFICATION, NotificationRequest(user_input="x"))

    assert failure.value.reason == "provider_rejected"
    assert route.call_count == 1


@respx.mock
async def test_backs_off_exponentially_between_attempts(notifier, sleeps):
    respx.post(f"{BASE_URL}/v1/notify").respond(500)

    with pytest.raises(NotificationFailed):
        await notifier.deliver(NOTIFICATION, NotificationRequest(user_input="x"))

    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] <= 1.0
    assert 1.0 <= sleeps[1] <= 2.0


@respx.mock
async def test_honours_retry_after_when_the_provider_sends_it(notifier, sleeps):
    respx.post(f"{BASE_URL}/v1/notify").mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), delivered()]
    )

    await notifier.deliver(NOTIFICATION, NotificationRequest(user_input="x"))

    assert sleeps == [7.0]


class ScriptedNotifier:
    def __init__(self, outcome=None):
        self.outcome = outcome

    async def deliver(self, notification, request):
        if self.outcome:
            raise self.outcome


async def run_delivery(outcome):
    queue = DeliveryQueue(ScriptedNotifier(outcome), concurrency=2, max_size=10)
    queue.start()
    request = NotificationRequest(user_input="x", status=Status.PROCESSING)
    queue.submit(NOTIFICATION, request)
    async with asyncio.timeout(1):
        while request.status == Status.PROCESSING:
            await asyncio.sleep(0.01)
    await queue.stop()
    return request


async def test_a_delivered_notification_marks_the_request_sent():
    request = await run_delivery(None)

    assert (request.status, request.reason) == (Status.SENT, None)


async def test_a_notification_the_provider_did_not_take_marks_the_request_failed():
    request = await run_delivery(NotificationFailed("rate_limited"))

    assert (request.status, request.reason) == (Status.FAILED, "rate_limited")


async def test_an_unexpected_error_in_delivery_fails_the_request():
    request = await run_delivery(RuntimeError("bug"))

    assert (request.status, request.reason) == (Status.FAILED, "internal_error")


async def test_a_full_delivery_backlog_fails_the_request_instead_of_growing_without_bound():
    queue = DeliveryQueue(ScriptedNotifier(), concurrency=1, max_size=1)
    first, second = NotificationRequest(user_input="a"), NotificationRequest(user_input="b")

    queue.submit(NOTIFICATION, first)
    queue.submit(NOTIFICATION, second)

    assert (second.status, second.reason) == (Status.FAILED, "delivery_backlog_full")
