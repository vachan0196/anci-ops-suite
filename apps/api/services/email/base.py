from typing import Any, Protocol


class EmailDeliveryError(Exception):
    def __init__(self) -> None:
        super().__init__("Email delivery is temporarily unavailable.")


class EmailService(Protocol):
    def send_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        ...
