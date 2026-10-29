import asyncio

from domain.models import NotificationRequest, Status
from services.pipeline import Pipeline


async def wait_until(condition, seconds=1.0):
    async with asyncio.timeout(seconds):
        while not condition():
            await asyncio.sleep(0.01)


async def test_a_worker_marks_the_request_processing_while_its_handler_runs():
    seen = []

    async def handler(request):
        seen.append(request.status)
        request.status = Status.SENT

    pipeline = Pipeline(handler, workers=1, max_size=10)
    pipeline.start()
    request = NotificationRequest(user_input="hola")

    assert pipeline.submit(request) is True
    await wait_until(lambda: request.status == Status.SENT)
    await pipeline.stop()

    assert seen == [Status.PROCESSING]


async def test_an_unexpected_error_fails_the_request_and_the_worker_keeps_going():
    async def handler(request):
        if request.user_input == "boom":
            raise RuntimeError("bug")
        request.status = Status.SENT

    pipeline = Pipeline(handler, workers=1, max_size=10)
    pipeline.start()
    broken, healthy = NotificationRequest(user_input="boom"), NotificationRequest(user_input="ok")

    pipeline.submit(broken)
    pipeline.submit(healthy)
    await wait_until(lambda: healthy.status == Status.SENT)
    await pipeline.stop()

    assert broken.status == Status.FAILED
    assert broken.reason == "internal_error"


async def test_submit_refuses_when_the_queue_is_full():
    async def handler(request):
        await asyncio.sleep(10)

    pipeline = Pipeline(handler, workers=1, max_size=1)

    assert pipeline.submit(NotificationRequest(user_input="a")) is True
    assert pipeline.submit(NotificationRequest(user_input="b")) is False


async def test_workers_run_requests_concurrently():
    running = 0
    peak = 0

    async def handler(request):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        request.status = Status.SENT

    pipeline = Pipeline(handler, workers=3, max_size=10)
    pipeline.start()
    requests = [NotificationRequest(user_input=str(i)) for i in range(3)]
    for request in requests:
        pipeline.submit(request)
    await wait_until(lambda: all(r.status == Status.SENT for r in requests))
    await pipeline.stop()

    assert peak == 3
