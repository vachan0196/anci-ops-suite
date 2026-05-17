from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapturedEmail:
    to: str
    template_id: str
    context: dict[str, Any] = field(default_factory=dict)


class TestCaptureEmailService:
    """In-memory test email backend.

    This backend may keep raw recipient addresses in memory so tests can assert
    exact sends. It must not be used as the production default and must not log
    or persist captured emails.
    """

    __test__ = False

    def __init__(self) -> None:
        self.sent_emails: list[CapturedEmail] = []

    def send_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.sent_emails.append(
            CapturedEmail(
                to=to,
                template_id=template_id,
                context=dict(context or {}),
            )
        )
