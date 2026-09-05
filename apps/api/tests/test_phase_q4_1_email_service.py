import hashlib
import logging

import pytest

from apps.api.core.settings import Settings
from apps.api.services.email import (
    LocalLogEmailService,
    TestCaptureEmailService,
    get_email_service,
)


def test_local_log_email_service_completes_without_real_send(caplog: pytest.LogCaptureFixture) -> None:
    service = LocalLogEmailService()

    with caplog.at_level(logging.INFO, logger="apps.api.services.email"):
        service.send_email(
            to="owner@example.com",
            template_id="email_verification",
            context={"status": "requested"},
        )

    assert "email.send backend=local_log" in caplog.text
    assert "template_id=email_verification" in caplog.text
    assert "status=requested" in caplog.text


def test_local_log_email_service_redacts_sensitive_context_and_recipient(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = LocalLogEmailService()

    with caplog.at_level(logging.INFO, logger="apps.api.services.email"):
        service.send_email(
            to="vachan@example.com",
            template_id="password_reset",
            context={
                "token": "secret_token_value_xyz",
                "password": "P@ssw0rd123",
                "raw_token": "tok_abc123",
                "verification_code": "999999",
            },
        )

    log_output = caplog.text
    local_part_hash = hashlib.sha256("vachan".encode("utf-8")).hexdigest()[:4]

    for forbidden_value in (
        "secret_token_value_xyz",
        "P@ssw0rd123",
        "tok_abc123",
        "999999",
        "vachan@example.com",
        "vachan",
    ):
        assert forbidden_value not in log_output

    assert "***@example.com" in log_output
    assert f"lp:{local_part_hash}" in log_output
    assert "token=<REDACTED" in log_output
    assert "password=<REDACTED" in log_output
    assert "raw_token=<REDACTED" in log_output
    assert "verification_code=<REDACTED" in log_output
    assert "forbidden_key=true" in log_output


def test_local_log_email_service_uses_context_allowlist_and_redacts_unknown_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = LocalLogEmailService()

    with caplog.at_level(logging.INFO, logger="apps.api.services.email"):
        service.send_email(
            to="admin@example.com",
            template_id="email_verification",
            context={
                "tenant_id": "tenant-123",
                "count": 2,
                "unknown_customer_hint": "Jane Doe private note",
            },
        )

    log_output = caplog.text
    assert "tenant_id=tenant-123" in log_output
    assert "count=2" in log_output
    assert "unknown_customer_hint=<REDACTED:length=21>" in log_output
    assert "Jane Doe private note" not in log_output
    assert "admin@example.com" not in log_output


def test_test_capture_email_service_captures_payloads_deterministically() -> None:
    service = TestCaptureEmailService()

    service.send_email(
        to="recipient@example.com",
        template_id="password_reset",
        context={"user_id": "user-123"},
    )

    assert len(service.sent_emails) == 1
    captured = service.sent_emails[0]
    assert captured.to == "recipient@example.com"
    assert captured.template_id == "password_reset"
    assert captured.context == {"user_id": "user-123"}


def test_test_capture_email_service_copies_context() -> None:
    service = TestCaptureEmailService()
    context = {"status": "requested"}

    service.send_email(
        to="recipient@example.com",
        template_id="email_verification",
        context=context,
    )
    context["status"] = "mutated"

    assert service.sent_emails[0].context == {"status": "requested"}


def test_email_service_factory_returns_allowed_backends() -> None:
    local_service = get_email_service(Settings(EMAIL_BACKEND="local_log"))
    capture_service = get_email_service(Settings(EMAIL_BACKEND="test_capture"))

    assert isinstance(local_service, LocalLogEmailService)
    assert isinstance(capture_service, TestCaptureEmailService)


def test_email_service_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unknown EMAIL_BACKEND"):
        get_email_service(Settings.model_construct(ENV="test", EMAIL_BACKEND="smtp"))
