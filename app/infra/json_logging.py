import json
import logging
import sys
from datetime import UTC, datetime

# Context fields passed through `extra=` that are worth a column of their own
_CONTEXT = ("request_id", "reason", "ai_attempts", "notify_attempts", "type")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so the logs can be filtered by request_id or reason without parsing text."""

    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        line.update({key: getattr(record, key) for key in _CONTEXT if hasattr(record, key)})
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
