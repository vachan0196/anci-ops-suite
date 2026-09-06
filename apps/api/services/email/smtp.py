from email.headerregistry import Address
from email.message import EmailMessage
import logging
import smtplib
from typing import Any

from apps.api.core.settings import Settings
from apps.api.services.email.base import EmailDeliveryError
from apps.api.services.email.content import render_email


logger = logging.getLogger("apps.api.services.email")


class LocalSmtpEmailService:
    def __init__(self, config: Settings) -> None:
        self.config = config

    def send_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        rendered = render_email(template_id, context)
        try:
            message = EmailMessage()
            message["From"] = Address(
                display_name=self.config.EMAIL_FROM_NAME,
                addr_spec=self.config.EMAIL_FROM_ADDRESS,
            )
            message["To"] = to
            message["Subject"] = rendered.subject
            message.set_content(rendered.text_body)

            # Connect inside the close boundary, including failed SMTP greetings.
            client = smtplib.SMTP(timeout=self.config.SMTP_TIMEOUT_SECONDS)
            try:
                client.connect(self.config.SMTP_HOST, self.config.SMTP_PORT)
                client.send_message(message)
            finally:
                client.close()
        except (smtplib.SMTPException, OSError, ValueError):
            logger.warning("email.send_failed backend=local_smtp")
            raise EmailDeliveryError() from None
