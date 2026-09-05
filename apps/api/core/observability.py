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
    "new_password",
    "confirm_password",
    "token",
    "raw_token",
    "token_hash",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "reset_url",
    "verification_url",
}
MAX_REDACTION_DEPTH = 32


def _redact_request_payload(
    value: Any, *, depth: int = 0, ancestors: set[int] | None = None
) -> Any:
    if not isinstance(value, (dict, list)):
        return value
    if ancestors is None:
        ancestors = set()
    if depth >= MAX_REDACTION_DEPTH or id(value) in ancestors:
        return "[Filtered]"

    ancestors.add(id(value))
    try:
        if isinstance(value, dict):
            return {
                key: "[Filtered]"
                if str(key).lower() in SENSITIVE_REQUEST_KEYS
                else _redact_request_payload(item, depth=depth + 1, ancestors=ancestors)
                for key, item in value.items()
            }
        return [
            _redact_request_payload(item, depth=depth + 1, ancestors=ancestors)
            for item in value
        ]
    finally:
        ancestors.remove(id(value))


def _strip_stacktrace_vars(stacktrace: Any) -> None:
    if not isinstance(stacktrace, dict):
        return
    frames = stacktrace.get("frames")
    if not isinstance(frames, list):
        return
    for frame in frames:
        if isinstance(frame, dict):
            frame.pop("vars", None)


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None

    _strip_stacktrace_vars(event.get("stacktrace"))
    for interface in ("exception", "threads"):
        container = event.get(interface)
        if not isinstance(container, dict):
            continue
        values = container.get("values")
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                _strip_stacktrace_vars(value.get("stacktrace"))
                _strip_stacktrace_vars(value.get("raw_stacktrace"))

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
    for interface in ("request", "contexts", "extra"):
        if interface in event:
            event[interface] = _redact_request_payload(event[interface])
    return event


def init_observability() -> None:
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENV,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        include_local_variables=False,
        before_send=_before_send,
    )
