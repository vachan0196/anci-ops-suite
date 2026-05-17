from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import hashlib
import logging


logger = logging.getLogger("apps.api.services.email")

SAFE_CONTEXT_KEYS = {
    "template_id",
    "tenant_id",
    "user_id",
    "site_id",
    "company_name",
    "site_name",
    "created_at",
    "updated_at",
    "expires_at",
    "count",
    "total",
    "status",
    "event_type",
    "portal",
}

FORBIDDEN_CONTEXT_KEYS = {
    "token",
    "raw_token",
    "token_hash",
    "password",
    "new_password",
    "confirm_password",
    "cookie",
    "authorization",
    "auth_header",
    "refresh_token",
    "access_token",
    "secret",
    "api_key",
    "verification_code",
    "reset_url",
    "verification_url",
}


def redact_recipient_email(email: str) -> str:
    local_part, separator, domain = email.partition("@")
    if not separator or not domain:
        return "***@<invalid> (lp:0000)"

    local_hash_prefix = hashlib.sha256(local_part.encode("utf-8")).hexdigest()[:4]
    return f"***@{domain.lower()} (lp:{local_hash_prefix})"


def _redacted_value(value: Any) -> str:
    return f"<REDACTED:length={len(str(value))}>"


def safe_context_for_logging(context: Mapping[str, Any] | None) -> str:
    if not context:
        return ""

    parts: list[str] = []
    for key in sorted(context):
        value = context[key]
        normalized_key = key.lower()
        if normalized_key in FORBIDDEN_CONTEXT_KEYS:
            parts.append(f"{key}={_redacted_value(value)} forbidden_key=true")
        elif key in SAFE_CONTEXT_KEYS:
            parts.append(f"{key}={value}")
        else:
            parts.append(f"{key}={_redacted_value(value)}")
    return " ".join(parts)


class LocalLogEmailService:
    """Local/dev email backend that never sends real email.

    The raw recipient email is deliberately not logged. Local logs include only
    the domain plus a short SHA-256 local-part prefix. TestCaptureEmailService
    may keep raw recipients in memory for assertions, but captured payloads
    must not be logged or persisted.
    """

    def send_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        logger.info(
            "email.send backend=local_log to=%s template_id=%s context=%s",
            redact_recipient_email(to),
            template_id,
            safe_context_for_logging(context),
        )
