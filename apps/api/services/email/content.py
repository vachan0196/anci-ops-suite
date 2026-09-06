from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text_body: str


def _required_url(context: Mapping[str, Any], key: str) -> str:
    value = context.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required email context key: {key}")
    return value


def _password_reset(context: Mapping[str, Any]) -> RenderedEmail:
    url = _required_url(context, "reset_url")
    return RenderedEmail(
        subject="Reset your ForecourtOS password",
        text_body=(
            "Use this link to reset your ForecourtOS password:\n\n"
            f"{url}\n\n"
            "This link expires in 1 hour.\n\n"
            "If you did not request a password reset, you can ignore this email.\n"
        ),
    )


def _email_verification(context: Mapping[str, Any]) -> RenderedEmail:
    url = _required_url(context, "verification_url")
    return RenderedEmail(
        subject="Verify your ForecourtOS email address",
        text_body=(
            "Use this link to verify your ForecourtOS email address:\n\n"
            f"{url}\n\n"
            "This link expires in 24 hours.\n\n"
            "If you did not request email verification, you can ignore this email.\n"
        ),
    )


EMAIL_TEMPLATES: Mapping[str, Callable[[Mapping[str, Any]], RenderedEmail]] = MappingProxyType({
    "password_reset": _password_reset,
    "email_verification": _email_verification,
})


def render_email(template_id: str, context: Mapping[str, Any] | None = None) -> RenderedEmail:
    renderer = EMAIL_TEMPLATES.get(template_id)
    if renderer is None:
        raise ValueError("Unknown email template identifier")
    return renderer(context or {})
