from typing import Any

import sentry_sdk

from apps.api.core.settings import settings

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}
SENSITIVE_REQUEST_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
}


def _redact_request_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_REQUEST_KEYS:
                redacted[key] = "[Filtered]"
            else:
                redacted[key] = _redact_request_payload(item)
        return redacted
    if isinstance(value, list):
        return [_redact_request_payload(item) for item in value]
    return value


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: "[Filtered]" if str(key).lower() in SENSITIVE_HEADER_NAMES else value
                for key, value in headers.items()
            }
        if "cookies" in request:
            request["cookies"] = "[Filtered]"
        if "data" in request:
            request["data"] = _redact_request_payload(request["data"])
    return event


def init_observability() -> None:
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENV,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        before_send=_before_send,
    )
