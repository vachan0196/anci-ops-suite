from apps.api.core.settings import Settings, settings
from apps.api.services.email.base import EmailService
from apps.api.services.email.capture import CapturedEmail, TestCaptureEmailService
from apps.api.services.email.local import LocalLogEmailService


def get_email_service(config: Settings | None = None) -> EmailService:
    selected_settings = config or settings
    if selected_settings.EMAIL_BACKEND == "local_log":
        return LocalLogEmailService()
    if selected_settings.EMAIL_BACKEND == "test_capture":
        return TestCaptureEmailService()
    raise ValueError(f"Unknown EMAIL_BACKEND: {selected_settings.EMAIL_BACKEND}")


__all__ = [
    "CapturedEmail",
    "EmailService",
    "LocalLogEmailService",
    "TestCaptureEmailService",
    "get_email_service",
]
