import contextvars
import json
import logging
import re
import uuid

request_id_var = contextvars.ContextVar("request_id", default=None)

_REDACTIONS = [
    re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)(?:bearer\s+)?[^\s\"',;]+"),
    re.compile(
        r"(?i)([\"']?(?:password|passwd|secret|token|refresh|access|api[_-]?key|"
        r"fernet[_-]?key|private[_-]?key|client[_-]?secret)[\"']?\s*[:=]\s*[\"']?)"
        r"[^\s\"',;&]+"
    ),
]


def redact(text: str) -> str:
    for pattern in _REDACTIONS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


_access_logger = logging.getLogger("request")

_HEALTH_PATHS = ("/healthz", "/readyz")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (request.headers.get("X-Request-ID") or "").strip()[:64] or uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
            if request.path not in _HEALTH_PATHS:
                _access_logger.info(
                    "%s %s -> %s", request.method, request.path, response.status_code
                )

            response.headers.setdefault("X-Request-ID", request_id)
            return response
        finally:
            request_id_var.reset(token)
