import asyncio
import logging
from collections.abc import Awaitable, Callable

from domain.models import NotificationRequest, Status

logger = logging.getLogger(__name__)

Handler = Callable[[NotificationRequest], Awaitable[None]]


class Pipeline:
    """
    Bounded queue drained by a fixed number of asyncio workers. The HTTP request only enqueues; the AI and the
    notification provider are always called from a worker, so /process answers in milliseconds whatever they do.
    """

    def __init__(self, handler: Handler, workers: int, max_size: int) -> None:
        self.handler = handler
        self._workers = workers
        self._queue: asyncio.Queue[NotificationRequest] = asyncio.Queue(maxsize=max_size)
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        self._tasks = [asyncio.create_task(self._work(), name=f"pipeline-worker-{i}") for i in range(self._workers)]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    def submit(self, request: NotificationRequest) -> bool:
        """Enqueues the request; False if the queue is full."""
        try:
            self._queue.put_nowait(request)
        except asyncio.QueueFull:
            return False
        return True

    async def _work(self) -> None:
        while True:
            request = await self._queue.get()
            try:
                request.status = Status.PROCESSING
                await self.handler(request)
            except Exception:
                # A bug in one request must not take the worker down with it
                logger.exception("Unexpected error processing request %s", request.id)
                request.status = Status.FAILED
                request.reason = "internal_error"
            finally:
                self._queue.task_done()
