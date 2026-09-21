from asyncio import CancelledError
from email.headerregistry import Address
import json
import logging
from types import MappingProxyType
import uuid

from fastapi.testclient import TestClient
import httpx
from pydantic import ValidationError
import pytest

from apps.api.core.settings import Settings
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.routers import auth as auth_router
from apps.api.services import email
from apps.api.services.email import EmailDeliveryError, ResendEmailService
from apps.api.services.email import resend
from apps.api.services.email.content import render_email
# Reuse Q4.2's isolated database fixture rather than adding a schema bootstrap.
from apps.api.tests.test_phase_q4_2_password_reset import test_session_local  # noqa: F401


KEY = "re_test_NOT_A_REAL_KEY_d068_1"
RECIPIENT = "d068-recipient@example.com"
PROVIDER_BODY = "private-provider-response-d068"
CONTEXT = {"reset_url": "https://example.test/reset-password?token=d068-test-token"}
PASSWORD = "password123"


def _settings(**overrides):
    values = {
        "ENV": "staging",
        "EMAIL_BACKEND": "resend",
        "EMAIL_FROM_ADDRESS": "sender@example.test",
        "EMAIL_FROM_NAME": "Example, Operations",
        "RESEND_API_KEY": KEY,
    }
    values.update(overrides)
    return Settings(**values, _env_file=None)


def _send(service):
    return service.send_email(to=RECIPIENT, template_id="password_reset", context=CONTEXT)


def _assert_delivery_warning(caplog):
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.name == "apps.api.services.email"
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "email.send_failed backend=resend"
    assert record.exc_info is None


def test_registry_returns_distinct_resend_instances():
    config = _settings(RESEND_API_KEY=None)
    assert isinstance(email.EMAIL_SERVICE_FACTORIES, MappingProxyType)
    assert tuple(email.EMAIL_SERVICE_FACTORIES) == ("local_log", "test_capture", "local_smtp", "resend")
    first = email.get_email_service(config)
    second = email.get_email_service(config)
    assert isinstance(first, ResendEmailService)
    assert isinstance(second, ResendEmailService)
    assert first is not second


@pytest.mark.parametrize("backend,environment,allowed", [
    ("resend", "staging", True),
    ("resend", "production", True),
    ("resend", "local", False),
    ("resend", "development", False),
    ("resend", "test", False),
    ("local_log", "staging", False),
    ("local_log", "production", False),
    ("test_capture", "production", False),
    ("local_smtp", "staging", False),
])
def test_explicit_environment_contract(backend, environment, allowed):
    values = dict(ENV=environment, EMAIL_BACKEND=backend, RESEND_API_KEY=None, _env_file=None)
    if allowed:
        config = Settings(**values)
        assert config.EMAIL_BACKEND == backend
        assert config.RESEND_API_KEY is None
    else:
        with pytest.raises(ValidationError, match="Incompatible EMAIL_BACKEND"):
            Settings(**values)


def test_construction_does_not_require_key():
    service = ResendEmailService(
        _settings(RESEND_API_KEY=None), transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    assert isinstance(service, ResendEmailService)


@pytest.mark.parametrize("status", [200, 202, 204, 299])
def test_success_payload_and_timeout(status):
    config = _settings()
    requests = []

    def handler(request):
        requests.append(request)
        # Success depends only on the status, even with a non-JSON response body.
        return httpx.Response(status, text="not JSON")

    service = ResendEmailService(config, transport=httpx.MockTransport(handler))
    assert _send(service) is None
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == resend.RESEND_ENDPOINT == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert request.headers["Content-Type"] == "application/json"
    rendered = render_email("password_reset", CONTEXT)
    payload = json.loads(request.content)
    assert set(payload) == {"from", "to", "subject", "text"}
    assert payload == {
        "from": str(Address(display_name=config.EMAIL_FROM_NAME, addr_spec=config.EMAIL_FROM_ADDRESS)),
        "to": [RECIPIENT],
        "subject": rendered.subject,
        "text": rendered.text_body,
    }
    assert "html" not in payload
    assert resend.RESEND_TIMEOUT_SECONDS == 10.0
    assert request.extensions["timeout"] == {
        "connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0,
    }


@pytest.mark.parametrize("failure", [
    httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout,
    httpx.ConnectError, RuntimeError,
    199, 300, 302, 400, 401, 403, 404, 422, 429, 500, 502, 503, 504,
])
def test_delivery_failures_are_normalised_without_retry(failure):
    calls = []

    def handler(request):
        calls.append(request)
        if isinstance(failure, int):
            return httpx.Response(failure)
        raise failure(PROVIDER_BODY)

    service = ResendEmailService(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(EmailDeliveryError):
        _send(service)
    assert len(calls) == 1


@pytest.mark.parametrize("transport_failure", [True, False])
def test_delivery_failure_details_are_contained(transport_failure, caplog):
    private_detail = f"{KEY} {RECIPIENT} {PROVIDER_BODY}"

    def handler(request):
        if transport_failure:
            raise httpx.ConnectError(private_detail)
        return httpx.Response(422, text=private_detail)

    service = ResendEmailService(_settings(), transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING), pytest.raises(EmailDeliveryError) as caught:
        _send(service)
    assert str(caught.value) == "Email delivery is temporarily unavailable."
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    _assert_delivery_warning(caplog)
    captured = repr([record.__dict__ for record in caplog.records])
    for forbidden in (KEY, RECIPIENT, PROVIDER_BODY):
        assert forbidden not in captured
        assert forbidden not in str(caught.value)
        assert forbidden not in repr(caught.value)


@pytest.mark.parametrize("sender_address", [None, "   "])
def test_sender_guard_fails_locally_without_provider_call(sender_address, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200)

    service = ResendEmailService(
        _settings(EMAIL_FROM_ADDRESS=sender_address), transport=httpx.MockTransport(handler),
    )
    with caplog.at_level(logging.WARNING), pytest.raises(EmailDeliveryError):
        _send(service)
    assert len(calls) == 0
    _assert_delivery_warning(caplog)


@pytest.fixture
def client(test_session_local):
    def override_get_db():
        with test_session_local() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def failing_email_service(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError(PROVIDER_BODY)

    service = ResendEmailService(_settings(), transport=httpx.MockTransport(handler))
    monkeypatch.setattr(auth_router, "get_email_service", lambda: service)
    return calls


def _register(client):
    address = f"d068-{uuid.uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/register", json={"email": address, "password": PASSWORD})
    assert response.status_code == 201
    return address


def test_password_reset_failure_preserves_full_response(client, failing_email_service):
    address = _register(client)
    # The middleware echoes this valid inbound UUID, allowing full header equality.
    request_id = str(uuid.uuid4())
    headers = {"X-Request-ID": request_id}
    known = client.post(
        "/api/v1/auth/password-reset/request", json={"email": address}, headers=headers,
    )
    assert len(failing_email_service) == 1
    unknown = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": f"missing-{uuid.uuid4().hex}@example.com"}, headers=headers,
    )
    assert len(failing_email_service) == 1
    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content
    assert known.json() == {"message": "If an account exists for that email, instructions have been sent."}
    assert known.headers["X-Request-ID"] == unknown.headers["X-Request-ID"] == request_id
    assert dict(known.headers) == dict(unknown.headers)


def test_email_verification_failure_returns_safe_503(client, failing_email_service):
    address = _register(client)
    login = client.post("/api/v1/auth/login", data={"username": address, "password": PASSWORD})
    assert login.status_code == 200
    response = client.post(
        "/api/v1/auth/email-verification/request",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert len(failing_email_service) == 1
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EMAIL_DELIVERY_UNAVAILABLE"
    assert PROVIDER_BODY not in response.text


def test_empty_permitted_backend_fallback(monkeypatch):
    monkeypatch.setattr(Settings, "EMAIL_BACKEND_ENVIRONMENTS", {"local_log": frozenset({"local"})})
    with pytest.raises(ValidationError, match="permitted values: <none implemented>"):
        Settings(ENV="staging", EMAIL_BACKEND="local_log", _env_file=None)


def test_rendering_failure_propagates_without_delivery_warning(monkeypatch, caplog):
    sentinel = RuntimeError("rendering-programming-error")
    calls = []

    def fail_render(template_id, context):
        raise sentinel

    def handler(request):
        calls.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(resend, "render_email", fail_render)
    service = ResendEmailService(_settings(), transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError) as caught:
        _send(service)
    assert caught.value is sentinel
    assert caplog.records == []
    assert calls == []


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, CancelledError])
def test_process_control_exceptions_propagate(exception_type, caplog):
    def handler(request):
        raise exception_type()

    service = ResendEmailService(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(exception_type):
        _send(service)
    assert caplog.records == []
