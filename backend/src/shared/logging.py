import contextvars
import json
import logging
import sys

from shared.config import get_settings

# Set by app.py's log_requests middleware for the lifetime of one request,
# so every log record emitted while handling it -- however deep the call
# stack, no explicit threading required -- can be correlated back to that
# request (and, from there, to a specific order/payment/webhook delivery)
# without grepping timestamps across log lines.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    """One JSON object per line -- easy to grep/parse/ship to a log
    aggregator, unlike the previous plain-text format. request_id is
    omitted (not null) outside a request context (startup logs, the
    scheduler's background jobs)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    settings = get_settings()
    level = logging.DEBUG if settings.env == "development" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
