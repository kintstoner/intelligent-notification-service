import pytest

from domain.models import Notification, NotificationRequest, Status
from services.extractor import ExtractionError
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


class RecordingDelivery:
    def __init__(self):
        self.submitted = []

    def submit(self, notification, request):
        self.submitted.append(notification)


async def process(*answers, cache=False, user_input=USER_INPUT):
    extractor = ScriptedExtractor(*answers)
    delivery = RecordingDelivery()
    request = NotificationRequest(user_input=user_input, status=Status.PROCESSING)
    await RequestProcessor(extractor, delivery, max_ai_attempts=2, cache_enabled=cache).process(request)
    return request, extractor, delivery


async def test_a_clean_answer_is_handed_to_delivery_after_one_ai_call():
    request, extractor, delivery = await process(CLEAN)

    assert request.status == Status.PROCESSING
    assert delivery.submitted == [EXPECTED]
    assert extractor.calls == 1


async def test_dirty_json_is_repaired_without_asking_the_ai_again():
    _, extractor, delivery = await process(FENCED)

    assert delivery.submitted == [EXPECTED]
    assert extractor.calls == 1


async def test_a_missing_type_is_recovered_without_asking_the_ai_again():
    _, extractor, delivery = await process(NO_TYPE)

    assert delivery.submitted == [EXPECTED]
    assert extractor.calls == 1


@pytest.mark.parametrize(
    "first",
    [POLICY_REFUSAL, NO_MESSAGE, '{"to": "juan@example.com", "message": "Tu paq', ExtractionError("t", retryable=True)],
)
async def test_one_retry_recovers_from_a_refusal_a_missing_message_a_cut_answer_or_a_timeout(first):
    _, extractor, delivery = await process(first, CLEAN)

    assert delivery.submitted == [EXPECTED]
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
    request, extractor, delivery = await process(first, second, CLEAN)

    assert (request.status, request.reason) == (Status.FAILED, reason)
    assert extractor.calls == 2
    assert delivery.submitted == []


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


async def test_counts_the_ai_attempts_of_each_request():
    request, _, _ = await process(POLICY_REFUSAL, CLEAN)

    assert request.ai_attempts == 2


async def test_with_the_cache_enabled_an_identical_request_reuses_the_extraction():
    extractor, delivery = ScriptedExtractor(CLEAN), RecordingDelivery()
    processor = RequestProcessor(extractor, delivery, max_ai_attempts=2, cache_enabled=True)

    for _ in range(2):
        await processor.process(NotificationRequest(user_input=USER_INPUT))

    assert delivery.submitted == [EXPECTED, EXPECTED]
    assert extractor.calls == 1


async def test_without_the_cache_every_request_asks_the_ai():
    extractor = ScriptedExtractor(CLEAN, CLEAN)
    processor = RequestProcessor(extractor, RecordingDelivery(), max_ai_attempts=2, cache_enabled=False)

    for _ in range(2):
        await processor.process(NotificationRequest(user_input=USER_INPUT))

    assert extractor.calls == 2
