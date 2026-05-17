from typing import Any, Protocol


class EmailService(Protocol):
    def send_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        ...
