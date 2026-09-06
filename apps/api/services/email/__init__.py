from collections.abc import Callable, Mapping
from types import MappingProxyType

from apps.api.core.settings import Settings, settings
from apps.api.services.email.base import EmailDeliveryError, EmailService
from apps.api.services.email.capture import CapturedEmail, TestCaptureEmailService
from apps.api.services.email.local import LocalLogEmailService
from apps.api.services.email.smtp import LocalSmtpEmailService


EMAIL_SERVICE_FACTORIES: Mapping[str, Callable[[Settings], EmailService]] = MappingProxyType({
    "local_log": lambda config: LocalLogEmailService(),
    "test_capture": lambda config: TestCaptureEmailService(),
    "local_smtp": LocalSmtpEmailService,
})


def get_email_service(config: Settings | None = None) -> EmailService:
    selected_settings = config or settings
    factory = EMAIL_SERVICE_FACTORIES.get(selected_settings.EMAIL_BACKEND)
    if factory is None:
        raise ValueError(f"Unknown EMAIL_BACKEND: {selected_settings.EMAIL_BACKEND}")
    return factory(selected_settings)


__all__ = [
    "CapturedEmail",
    "EmailService",
    "EmailDeliveryError",
    "LocalLogEmailService",
    "LocalSmtpEmailService",
    "TestCaptureEmailService",
    "get_email_service",
]
