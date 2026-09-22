import hashlib
import json
import logging
import math
import os
from pathlib import Path
import smtplib
import subprocess
import sys
import traceback
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse
import uuid

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from apps.api.core.settings import Settings
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_token import AuthToken
from apps.api.models.user import User
from apps.api.services import email
from apps.api.services.email import smtp
from apps.api.services.email.content import EMAIL_TEMPLATES, render_email
from apps.api.tests._deployed_settings import deployed_settings


TRANSPORT_SECRET = "transport-detail-must-never-escape"
RECIPIENT = "q531-recipient@example.com"
RAW_TOKEN = "q531-token-with-credential-material"
PASSWORD = "q531-password-for-tests"
MESSAGES = (
    ("password_reset", "reset_url", "/admin/reset-password", "1 hour", "Reset your ForecourtOS password"),
    ("email_verification", "verification_url", "/admin/verify-email", "24 hours", "Verify your ForecourtOS email address"),
)


def _smtp_settings(**overrides) -> Settings:
    values = {
        "ENV": "development", "EMAIL_BACKEND": "local_smtp",
        "SMTP_HOST": "mailpit", "SMTP_PORT": 1025, "SMTP_TIMEOUT_SECONDS": 4.0,
        "EMAIL_FROM_ADDRESS": "no-reply@forecourtos.test", "EMAIL_FROM_NAME": "ForecourtOS",
    }
    values.update(overrides)
    return Settings(**values, _env_file=None)


def _url(path: str) -> str:
    return f"http://localhost:3000{path}?token={RAW_TOKEN}"


@pytest.mark.parametrize("template_id,url_key,path,expiry,subject", MESSAGES)
def test_rendering_uses_closed_content_and_preserves_exact_url(template_id, url_key, path, expiry, subject):
    assert set(EMAIL_TEMPLATES) == {"password_reset", "email_verification"}
    rendered = render_email(template_id, {
        url_key: _url(path), "subject": "caller subject", "body": "caller body",
    })

    assert rendered.subject == subject
    assert _url(path) in rendered.text_body.splitlines()
    assert expiry in rendered.text_body
    assert "did not request" in rendered.text_body
    assert "ignore this email" in rendered.text_body
    assert "caller subject" not in rendered.subject
    assert "caller body" not in rendered.text_body
    assert "<html" not in rendered.text_body


def test_renderer_rejects_unknown_identifier():
    with pytest.raises(ValueError, match="Unknown email template identifier"):
        render_email("unknown", {"reset_url": _url("/admin/reset-password")})


@pytest.mark.parametrize("template_id,url_key,path,expiry,subject", MESSAGES)
@pytest.mark.parametrize("context", [None, {}, {"wrong_url": "unused"}])
def test_renderer_rejects_missing_url(template_id, url_key, path, expiry, subject, context):
    with pytest.raises(ValueError, match=url_key):
        render_email(template_id, context)


@pytest.mark.parametrize("template_id,url_key,path,expiry,subject", MESSAGES)
def test_logging_redacts_urls_that_smtp_delivers_verbatim(
    template_id, url_key, path, expiry, subject, monkeypatch, caplog,
):
    expected_url = _url(path)
    with caplog.at_level(logging.INFO, logger="apps.api.services.email"):
        email.LocalLogEmailService().send_email(
            to=RECIPIENT, template_id=template_id, context={url_key: expected_url},
        )
    assert expected_url not in caplog.text
    assert RAW_TOKEN not in caplog.text
    assert f"{url_key}=<REDACTED:length={len(expected_url)}> forbidden_key=true" in caplog.text

    client = Mock()
    constructor = Mock(return_value=client)
    monkeypatch.setattr(smtp.smtplib, "SMTP", constructor)
    config = _smtp_settings()
    email.get_email_service(config).send_email(
        to=RECIPIENT, template_id=template_id, context={url_key: expected_url},
    )

    constructor.assert_called_once_with(timeout=config.SMTP_TIMEOUT_SECONDS)
    assert math.isfinite(config.SMTP_TIMEOUT_SECONDS) and config.SMTP_TIMEOUT_SECONDS > 0
    client.connect.assert_called_once_with("mailpit", 1025)
    client.send_message.assert_called_once()
    client.close.assert_called_once()
    message = client.send_message.call_args.args[0]
    assert message["Subject"] == subject
    assert message["From"].addresses[0].addr_spec == config.EMAIL_FROM_ADDRESS
    assert message["From"].addresses[0].display_name == config.EMAIL_FROM_NAME
    assert str(message["To"]) == RECIPIENT
    assert not message.is_multipart()
    assert message.get_content_type() == "text/plain"
    assert expected_url in message.get_content().splitlines()
    assert expected_url not in caplog.text


@pytest.mark.parametrize("newline", ["\r", "\n", "\r\n"])
def test_smtp_rejects_header_injection_before_connecting(newline, monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(smtp.smtplib, "SMTP", constructor)

    with pytest.raises(email.EmailDeliveryError):
        email.get_email_service(_smtp_settings()).send_email(
            to=f"{RECIPIENT}{newline}Bcc: unwanted@example.com",
            template_id="password_reset", context={"reset_url": _url("/admin/reset-password")},
        )
    constructor.assert_not_called()


@pytest.mark.parametrize("stage", ["constructor", "connect", "send_message", "close"])
@pytest.mark.parametrize("error_type", [smtplib.SMTPException, TimeoutError, OSError])
def test_transport_failures_are_closed_and_sanitised(stage, error_type, monkeypatch, caplog):
    expected_url = _url("/admin/reset-password")
    transport_error = error_type(f"{TRANSPORT_SECRET} {RECIPIENT} {expected_url}")
    client = Mock()
    constructor = Mock(return_value=client)
    if stage == "constructor":
        constructor.side_effect = transport_error
    else:
        getattr(client, stage).side_effect = transport_error
    monkeypatch.setattr(smtp.smtplib, "SMTP", constructor)

    with caplog.at_level(logging.WARNING, logger="apps.api.services.email"):
        with pytest.raises(email.EmailDeliveryError) as caught:
            email.get_email_service(_smtp_settings()).send_email(
                to=RECIPIENT, template_id="password_reset", context={"reset_url": expected_url},
            )

    formatted = "".join(traceback.format_exception(caught.value))
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert "email.send_failed backend=local_smtp" in caplog.text
    for value in (TRANSPORT_SECRET, RECIPIENT, expected_url, RAW_TOKEN):
        assert value not in str(caught.value)
        assert value not in formatted
        assert value not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    if stage == "constructor":
        client.close.assert_not_called()
    else:
        client.close.assert_called_once()


@pytest.mark.parametrize("environment", ["local", "development"])
def test_local_smtp_settings_construct_normally(environment):
    assert _smtp_settings(ENV=environment).ENV == environment


@pytest.mark.parametrize("environment", ["test", "staging", "production"])
def test_local_smtp_is_forbidden_outside_development(environment):
    with pytest.raises(ValidationError, match="Incompatible EMAIL_BACKEND"):
        _smtp_settings(ENV=environment)


@pytest.mark.parametrize("field", ["SMTP_HOST", "EMAIL_FROM_ADDRESS"])
@pytest.mark.parametrize("missing", [None, "", " "])
def test_selected_smtp_requires_configuration_at_construction(field, missing):
    with pytest.raises(ValidationError, match=field):
        _smtp_settings(**{field: missing})


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_smtp_timeout_is_positive_and_finite(timeout):
    with pytest.raises(ValidationError, match="SMTP_TIMEOUT_SECONDS"):
        _smtp_settings(SMTP_TIMEOUT_SECONDS=timeout)


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_smtp_port_is_valid(port):
    with pytest.raises(ValidationError, match="SMTP_PORT"):
        _smtp_settings(SMTP_PORT=port)


@pytest.mark.parametrize("field", ["EMAIL_FROM_ADDRESS", "EMAIL_FROM_NAME"])
def test_configured_sender_rejects_newlines(field):
    with pytest.raises(ValidationError):
        _smtp_settings(**{field: "sender\r\nBcc: unwanted@example.com"})


def test_unselected_smtp_does_not_require_smtp_fields():
    for backend in ("local_log", "test_capture"):
        config = Settings(
            ENV="test", EMAIL_BACKEND=backend, SMTP_HOST=None, EMAIL_FROM_ADDRESS=None, _env_file=None,
        )
        assert config.EMAIL_BACKEND == backend


def test_settings_and_factory_backend_registries_agree():
    assert set(email.EMAIL_SERVICE_FACTORIES) == set(Settings.EMAIL_BACKEND_ENVIRONMENTS)
    expected = {
        "local_log": (email.LocalLogEmailService, "local"),
        "test_capture": (email.TestCaptureEmailService, "local"),
        "local_smtp": (email.LocalSmtpEmailService, "local"),
        # resend is permitted in staging and production only.
        "resend": (email.ResendEmailService, "staging"),
    }
    assert set(expected) == set(email.EMAIL_SERVICE_FACTORIES)
    for backend, (service_type, environment) in expected.items():
        # Only the resend/staging entry needs H154's explicit deployed configuration.
        security_values = deployed_settings() if backend == "resend" else {}
        config = _smtp_settings(ENV=environment, EMAIL_BACKEND=backend, **security_values)
        assert isinstance(email.get_email_service(config), service_type)
        assert email.get_email_service(config) is not email.get_email_service(config)


@pytest.fixture(scope="module")
def migrated_sessions():
    database_url = make_url(os.environ["DATABASE_URL"])
    assert database_url.get_backend_name() == "postgresql", "Run these integration tests with Compose"
    schema = "q531_" + uuid.uuid4().hex
    admin_engine = create_engine(database_url, poolclass=NullPool)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        database_url, poolclass=NullPool, connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        root = Path(__file__).resolve().parents[3]
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
            cwd=root,
            env={**os.environ, "PGOPTIONS": f"-csearch_path={schema}"},
            capture_output=True, text=True, timeout=90,
        )
        assert migrated.returncode == 0, migrated.stderr
        yield sessionmaker(bind=engine, class_=Session, autoflush=False)
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.fixture
def client(migrated_sessions):
    def override_get_db():
        with migrated_sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _register(client, *, disabled=False, sessions=None):
    address = f"q531-{uuid.uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/register", json={"email": address, "password": PASSWORD})
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    if disabled:
        with sessions() as db:
            db.get(User, user_id).is_active = False
            db.commit()
    return user_id, address


def _assert_committed(sessions, user_id, token_type, expected_url):
    raw_token = parse_qs(urlparse(expected_url).query)["token"][0]
    with sessions() as db:
        token = db.scalar(select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.token_hash == hashlib.sha256(raw_token.encode()).hexdigest(),
        ))
        assert token is not None
        assert token.token_type == token_type
        assert token.used_at is None
        event = db.scalar(select(AuthSecurityEvent).where(
            AuthSecurityEvent.user_id == user_id,
            AuthSecurityEvent.event_type == f"auth.{token_type}.requested",
        ))
        assert event is not None
        assert raw_token not in json.dumps(event.metadata_json)
        return token.id, event.id


def _install_transport(monkeypatch, sessions, user_id, token_type, fail):
    config = _smtp_settings()
    monkeypatch.setattr(email, "settings", config)
    messages = []
    persisted_ids = []
    client = Mock()

    def send_message(message):
        messages.append(message)
        expected_path = "/admin/reset-password" if token_type == "password_reset" else "/admin/verify-email"
        urls = [line for line in message.get_content().splitlines() if line.startswith("http://")]
        assert len(urls) == 1
        parsed = urlparse(urls[0])
        assert parsed.path == expected_path
        assert set(parse_qs(parsed.query)) == {"token"}
        persisted_ids.append(_assert_committed(sessions, user_id, token_type, urls[0]))
        if fail:
            raise smtplib.SMTPDataError(451, f"{TRANSPORT_SECRET} {message}".encode())

    client.send_message.side_effect = send_message
    monkeypatch.setattr(smtp.smtplib, "SMTP", Mock(return_value=client))
    return client, messages, persisted_ids


@pytest.mark.parametrize("fail", [False, True])
def test_reset_response_is_identical_across_account_states_and_delivery_outcomes(
    client, migrated_sessions, monkeypatch, caplog, fail,
):
    user_id, active = _register(client)
    disabled_id, disabled = _register(client, disabled=True, sessions=migrated_sessions)
    transport, messages, persisted_ids = _install_transport(
        monkeypatch, migrated_sessions, user_id, "password_reset", fail,
    )
    responses = []
    for address in (active, disabled, f"absent-{uuid.uuid4().hex}@example.com"):
        request_id = str(uuid.uuid4())
        response = client.post(
            "/api/v1/auth/password-reset/request", json={"email": address},
            headers={"X-Request-ID": request_id},
        )
        responses.append(response)
        assert response.status_code == 202
        assert response.json() == {"message": "If an account exists for that email, instructions have been sent."}
        with migrated_sessions() as db:
            event = db.scalar(select(AuthSecurityEvent).where(AuthSecurityEvent.request_id == request_id))
            assert event is not None
            assert event.user_id == (user_id if address == active else None)
    assert len(messages) == len(persisted_ids) == 1
    transport.close.assert_called_once()
    with migrated_sessions() as db:
        assert db.get(AuthToken, persisted_ids[0][0]) is not None
        assert db.get(AuthSecurityEvent, persisted_ids[0][1]) is not None
        assert db.scalar(select(AuthToken).where(AuthToken.user_id == disabled_id)) is None
    delivered_url = next(line for line in messages[0].get_content().splitlines() if line.startswith("http://"))
    raw_token = parse_qs(urlparse(delivered_url).query)["token"][0]
    for value in (TRANSPORT_SECRET, active, disabled, delivered_url, raw_token):
        assert value not in caplog.text
        assert all(value not in response.text for response in responses)


@pytest.mark.parametrize("fail", [False, True])
def test_verification_commits_before_send_and_reports_safe_retryable_failure(
    client, migrated_sessions, monkeypatch, caplog, fail,
):
    user_id, address = _register(client)
    login = client.post("/api/v1/auth/login", data={"username": address, "password": PASSWORD})
    assert login.status_code == 200
    transport, messages, persisted_ids = _install_transport(
        monkeypatch, migrated_sessions, user_id, "email_verification", fail,
    )

    response = client.post(
        "/api/v1/auth/email-verification/request",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    if fail:
        assert response.status_code == 503
        assert response.json() == {"error": {
            "code": "EMAIL_DELIVERY_UNAVAILABLE",
            "message": "Unable to send verification email. Please try again.", "details": None,
        }}
    else:
        assert response.status_code == 202
        assert response.json() == {"message": "If email verification is required, instructions have been sent."}
    assert len(messages) == len(persisted_ids) == 1
    transport.close.assert_called_once()
    with migrated_sessions() as db:
        assert db.get(AuthToken, persisted_ids[0][0]) is not None
        assert db.get(AuthSecurityEvent, persisted_ids[0][1]) is not None
    delivered_url = next(line for line in messages[0].get_content().splitlines() if line.startswith("http://"))
    raw_token = parse_qs(urlparse(delivered_url).query)["token"][0]
    for value in (TRANSPORT_SECRET, address, delivered_url, raw_token):
        assert value not in response.text
        assert value not in caplog.text


@pytest.mark.parametrize("token_type", ["password_reset", "email_verification"])
def test_rejected_recipient_header_preserves_delivery_failure_contract(
    client, migrated_sessions, monkeypatch, caplog, token_type,
):
    address = f"q531-{uuid.uuid4().hex}@example.com\nbcc: unwanted@example.com"
    registered = client.post("/api/v1/auth/register", json={"email": address, "password": PASSWORD})
    assert registered.status_code == 201
    user_id = uuid.UUID(registered.json()["id"])
    monkeypatch.setattr(email, "settings", _smtp_settings())
    constructor = Mock()
    monkeypatch.setattr(smtp.smtplib, "SMTP", constructor)

    if token_type == "password_reset":
        response = client.post("/api/v1/auth/password-reset/request", json={"email": address})
        assert response.status_code == 202
        assert response.json() == {"message": "If an account exists for that email, instructions have been sent."}
    else:
        login = client.post("/api/v1/auth/login", data={"username": address, "password": PASSWORD})
        assert login.status_code == 200
        response = client.post(
            "/api/v1/auth/email-verification/request",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "EMAIL_DELIVERY_UNAVAILABLE"
    constructor.assert_not_called()
    with migrated_sessions() as db:
        assert db.scalar(select(AuthToken).where(AuthToken.user_id == user_id)) is not None
        assert db.scalar(select(AuthSecurityEvent).where(
            AuthSecurityEvent.user_id == user_id,
            AuthSecurityEvent.event_type == f"auth.{token_type}.requested",
        )) is not None
    assert address not in response.text + caplog.text
