from email.headerregistry import Address
import logging
from typing import Any

import httpx

from apps.api.core.settings import Settings
from apps.api.services.email.base import EmailDeliveryError
from apps.api.services.email.content import render_email


logger = logging.getLogger("apps.api.services.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 10.0


class _DeliveryFailure(Exception):
    pass


class ResendEmailService:
    def __init__(self, config: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        self._transport = transport

    def send_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        rendered = render_email(template_id, context)
        try:
            sender_address = self.config.EMAIL_FROM_ADDRESS
            # Deliberate send-time guard: fail locally instead of relying on provider
            # rejection of an empty Address. Startup validation remains H181's scope.
            if not sender_address or not sender_address.strip():
                raise _DeliveryFailure()
            sender = str(Address(display_name=self.config.EMAIL_FROM_NAME, addr_spec=sender_address))
            payload = {
                "from": sender,
                "to": [to],
                "subject": rendered.subject,
                "text": rendered.text_body,
            }
            with httpx.Client(timeout=RESEND_TIMEOUT_SECONDS, transport=self._transport) as client:
                response = client.post(
                    RESEND_ENDPOINT,
                    headers={"Authorization": f"Bearer {self.config.RESEND_API_KEY}"},
                    json=payload,
                )
                if not 200 <= response.status_code < 300:
                    raise _DeliveryFailure()
        except Exception:
            # D068 rule 2: the router catches only EmailDeliveryError; any other
            # delivery exception would break password-reset response invariance.
            logger.warning("email.send_failed backend=resend")
            raise EmailDeliveryError() from None
