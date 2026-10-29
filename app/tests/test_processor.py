import pytest

from domain.models import Notification, NotificationRequest, Status
from services.extractor import ExtractionError
from services.notifier import NotificationFailed
from services.processor import RequestProcessor

CLEAN = '{"to": "juan@example.com", "message": "Tu paquete está en camino", "type": "email"}'
FENCED = f"He extraído la información:\n```json\n{CLEAN}\n```"
POLICY_REFUSAL = "Refused: Content analysis flagged sensitive information."
MISSING_INFO = "I cannot process the request. I was unable to identify the destination (email/phone) in your prompt."
NO_MESSAGE = '{"to": "juan@example.com", "type": "email"}'
NO_TYPE = '{"to": "juan@example.com", "message": "Tu paquete está en camino"}'
USER_INPUT = "Enviar email a juan@example.com diciendo que su paquete está en camino."
EXPECTED = Notification(to="juan@example.com", message="Tu paquete está en camino", type="email")


class ScriptedExtractor:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    async def extract(self, user_input):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class RecordingNotifier:
    def __init__(self, error=None):
        self.sent = []
        self.error = error

    async def send(self, notification, request):
        if self.error:
            raise self.error
        self.sent.append(notification)


async def process(*answers, notifier=None, cache=False, user_input=USER_INPUT):
    extractor = ScriptedExtractor(*answers)
    notifier = notifier or RecordingNotifier()
    request = NotificationRequest(user_input=user_input)
    await RequestProcessor(extractor, notifier, max_ai_attempts=2, cache_enabled=cache).process(request)
    return request, extractor, notifier


async def test_a_clean_answer_is_sent_with_one_ai_call():
    request, extractor, notifier = await process(CLEAN)

    assert request.status == Status.SENT
    assert notifier.sent == [EXPECTED]
    assert extractor.calls == 1


async def test_dirty_json_is_repaired_without_asking_the_ai_again():
    request, extractor, _ = await process(FENCED)

    assert request.status == Status.SENT
    assert extractor.calls == 1


async def test_a_missing_type_is_recovered_without_asking_the_ai_again():
    request, extractor, notifier = await process(NO_TYPE)

    assert request.status == Status.SENT
    assert notifier.sent == [EXPECTED]
    assert extractor.calls == 1


@pytest.mark.parametrize(
    "first",
    [POLICY_REFUSAL, NO_MESSAGE, '{"to": "juan@example.com", "message": "Tu paq', ExtractionError("t", retryable=True)],
)
async def test_one_retry_recovers_from_a_refusal_a_missing_message_a_cut_answer_or_a_timeout(first):
    request, extractor, _ = await process(first, CLEAN)

    assert request.status == Status.SENT
    assert extractor.calls == 2


@pytest.mark.parametrize(
    ("first", "second", "reason"),
    [
        (POLICY_REFUSAL, POLICY_REFUSAL, "ai_refused"),
        (NO_MESSAGE, NO_MESSAGE, "missing_message"),
        (ExtractionError("t", retryable=True), ExtractionError("t", retryable=True), "ai_unavailable"),
    ],
)
async def test_never_more_than_one_retry(first, second, reason):
    request, extractor, notifier = await process(first, second, CLEAN)

    assert (request.status, request.reason) == (Status.FAILED, reason)
    assert extractor.calls == 2
    assert notifier.sent == []


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (MISSING_INFO, "missing_information"),
        (ExtractionError("403", retryable=False), "ai_unavailable"),
        ('{"to": "600111222", "message": "hola", "type": "email"}', "invalid_notification"),
    ],
)
async def test_failures_that_a_retry_cannot_fix_are_not_retried(answer, reason):
    request, extractor, _ = await process(answer, CLEAN, user_input="manda un mensaje diciendo hola")

    assert (request.status, request.reason) == (Status.FAILED, reason)
    assert extractor.calls == 1


async def test_a_notification_the_provider_could_not_take_fails_with_its_reason():
    request, _, _ = await process(CLEAN, notifier=RecordingNotifier(NotificationFailed("rate_limited")))

    assert (request.status, request.reason) == (Status.FAILED, "rate_limited")


async def test_counts_the_ai_attempts_of_each_request():
    request, _, _ = await process(POLICY_REFUSAL, CLEAN)

    assert request.ai_attempts == 2


async def test_with_the_cache_enabled_an_identical_request_reuses_the_extraction():
    extractor = ScriptedExtractor(CLEAN)
    processor = RequestProcessor(extractor, RecordingNotifier(), max_ai_attempts=2, cache_enabled=True)

    for _ in range(2):
        request = NotificationRequest(user_input=USER_INPUT)
        await processor.process(request)
        assert request.status == Status.SENT

    assert extractor.calls == 1


async def test_without_the_cache_every_request_asks_the_ai():
    extractor = ScriptedExtractor(CLEAN, CLEAN)
    processor = RequestProcessor(extractor, RecordingNotifier(), max_ai_attempts=2, cache_enabled=False)

    for _ in range(2):
        await processor.process(NotificationRequest(user_input=USER_INPUT))

    assert extractor.calls == 2
