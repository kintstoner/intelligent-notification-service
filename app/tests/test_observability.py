import json
import logging

from domain.models import NotificationRequest
from infra.json_logging import JsonFormatter
from services.processor import RequestProcessor


def test_health_reports_ok_and_the_backlog_of_each_stage(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "awaiting_ai": 0, "awaiting_delivery": 0}


def test_log_lines_are_json_with_the_request_context():
    record = logging.LogRecord("svc", logging.WARNING, __file__, 1, "Request %s failed", ("r1",), None)
    record.request_id = "r1"
    record.reason = "ai_refused"

    line = json.loads(JsonFormatter().format(record))

    assert line["level"] == "WARNING"
    assert line["message"] == "Request r1 failed"
    assert line["request_id"] == "r1"
    assert line["reason"] == "ai_refused"
    assert "time" in line


async def test_a_failed_request_is_logged_with_its_id_reason_and_attempts(caplog):
    class Refusing:
        async def extract(self, user_input):
            return "Refused: Content analysis flagged sensitive information."

    request = NotificationRequest(user_input="hola")
    processor = RequestProcessor(Refusing(), delivery=None, max_ai_attempts=2, cache_enabled=False)

    with caplog.at_level(logging.INFO):
        await processor.process(request)

    failure = next(r for r in caplog.records if r.levelno == logging.WARNING)
    assert (failure.request_id, failure.reason, failure.ai_attempts) == (request.id, "ai_refused", 2)
