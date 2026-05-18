from collections.abc import Generator, Iterable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from urllib.parse import parse_qs, urlparse
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.auth_token import AuthToken
from apps.api.models.user import User
from apps.api.routers import auth as auth_router
from apps.api.services.email import TestCaptureEmailService


PASSWORD = "password123"
GENERIC_MESSAGE = "If email verification is required, instructions have been sent."
ALREADY_VERIFIED_MESSAGE = "Your email is already verified."


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q4_3_email_verification.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=test_engine)
    try:
        yield session_local
    finally:
        test_engine.dispose()


@pytest.fixture
def email_service(monkeypatch: pytest.MonkeyPatch) -> TestCaptureEmailService:
    service = TestCaptureEmailService()
    monkeypatch.setattr(auth_router, "get_email_service", lambda: service)
    return service


@pytest.fixture
def client(test_session_local) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _request_verification(client: TestClient, access_token: str):
    return client.post(
        "/api/v1/auth/email-verification/request",
        headers=_auth_headers(access_token),
    )


def _confirm_verification(client: TestClient, token: str):
    return client.post(
        "/api/v1/auth/email-verification/confirm",
        json={"token": token},
    )


def _raw_token_from_email(email_service: TestCaptureEmailService, index: int = 0) -> str:
    verification_url = email_service.sent_emails[index].context["verification_url"]
    parsed = urlparse(verification_url)
    token_values = parse_qs(parsed.query)["token"]
    assert len(token_values) == 1
    return token_values[0]


def _events(
    db: Session,
    *,
    event_type: str | None = None,
    rejection_reason: str | None = None,
) -> list[AuthSecurityEvent]:
    statement = select(AuthSecurityEvent).order_by(AuthSecurityEvent.created_at, AuthSecurityEvent.id)
    if event_type is not None:
        statement = statement.where(AuthSecurityEvent.event_type == event_type)
    if rejection_reason is not None:
        statement = statement.where(AuthSecurityEvent.rejection_reason == rejection_reason)
    return list(db.scalars(statement).all())


def _event_payload(event: AuthSecurityEvent) -> str:
    values = {
        "event_type": event.event_type,
        "rejection_reason": event.rejection_reason,
        "portal": event.portal,
        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
        "user_id": str(event.user_id) if event.user_id else None,
        "auth_session_id": str(event.auth_session_id) if event.auth_session_id else None,
        "request_id": event.request_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "metadata_json": event.metadata_json,
    }
    return json.dumps(values, sort_keys=True, default=str)


def _assert_no_auth_event_leakage(
    db: Session,
    events: Iterable[AuthSecurityEvent],
    *,
    forbidden_values: Iterable[str],
) -> None:
    token_hashes = db.scalars(select(AuthToken.token_hash)).all()
    session_hashes = db.scalars(select(AuthSession.token_hash)).all()
    for event in events:
        payload = _event_payload(event)
        for value in [*forbidden_values, *token_hashes, *session_hashes, "Bearer "]:
            if value:
                assert value not in payload


def test_authenticated_unverified_admin_can_request_verification(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-request-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])

    response = _request_verification(client, login["access_token"])

    assert response.status_code == 202
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert len(email_service.sent_emails) == 1
    captured = email_service.sent_emails[0]
    assert captured.to == user["email"]
    assert captured.template_id == "email_verification"
    assert captured.context["user_id"] == user["id"]
    assert "verification_url" in captured.context
    assert "expires_at" in captured.context
    raw_token = _raw_token_from_email(email_service)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with test_session_local() as db:
        auth_token = db.scalar(select(AuthToken).where(AuthToken.token_type == "email_verification"))
        assert auth_token is not None
        assert str(auth_token.user_id) == user["id"]
        assert auth_token.used_at is None
        assert auth_token.token_hash == token_hash
        assert auth_token.token_hash != raw_token
        assert auth_router._as_aware(auth_token.expires_at) > auth_router._now() + timedelta(hours=23)
        requested = _events(db, event_type="auth.email_verification.requested")
        assert len(requested) == 1
        assert str(requested[0].user_id) == user["id"]
        assert requested[0].metadata_json == {"already_verified": False}
        _assert_no_auth_event_leakage(
            db,
            requested,
            forbidden_values=[raw_token, captured.context["verification_url"], user["email"]],
        )


def test_unauthenticated_request_creates_no_token_or_email(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    response = client.post("/api/v1/auth/email-verification/request")

    assert response.status_code == 401
    assert email_service.sent_emails == []
    with test_session_local() as db:
        assert db.scalars(select(AuthToken)).all() == []


def test_employee_token_cannot_request_admin_email_verification(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    employee_token = create_access_token(f"employee:{uuid.uuid4()}")

    response = _request_verification(client, employee_token)

    assert response.status_code == 401
    assert email_service.sent_emails == []
    with test_session_local() as db:
        assert db.scalars(select(AuthToken)).all() == []


def test_already_verified_request_returns_safe_message_without_email_or_token(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-already-{uuid.uuid4()}@example.com")
    verified_at = datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        db_user.email_verified_at = verified_at
        db.commit()
    login = _login(client, user["email"])

    response = _request_verification(client, login["access_token"])

    assert response.status_code == 200
    assert response.json() == {"message": ALREADY_VERIFIED_MESSAGE}
    assert email_service.sent_emails == []
    with test_session_local() as db:
        assert db.scalars(select(AuthToken)).all() == []
        events = _events(db, event_type="auth.email_verification.already_verified")
        assert len(events) == 1
        assert str(events[0].user_id) == user["id"]
        _assert_no_auth_event_leakage(db, events, forbidden_values=[user["email"]])


def test_multiple_valid_verification_tokens_can_coexist(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-multiple-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])

    assert _request_verification(client, login["access_token"]).status_code == 202
    assert _request_verification(client, login["access_token"]).status_code == 202

    assert len(email_service.sent_emails) == 2
    with test_session_local() as db:
        tokens = db.scalars(select(AuthToken).order_by(AuthToken.created_at)).all()
        assert len(tokens) == 2
        assert all(token.token_type == "email_verification" for token in tokens)
        assert all(token.used_at is None for token in tokens)
        assert tokens[0].token_hash != tokens[1].token_hash


def test_valid_token_sets_email_verified_at_and_marks_token_used(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-confirm-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)

    response = _confirm_verification(client, token)

    assert response.status_code == 200
    assert response.json() == {"success": True}
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        assert db_user.email_verified_at is not None
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        assert auth_token.used_at is not None
        assert auth_token.consumed_ip is not None
        completed = _events(db, event_type="auth.email_verification.completed")
        assert len(completed) == 1
        assert completed[0].metadata_json == {"already_verified": False}


def test_used_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-used-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)
    assert _confirm_verification(client, token).status_code == 200

    second = _confirm_verification(client, token)

    assert second.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.email_verification.token_rejected",
            rejection_reason="used",
        )
        assert len(rejected) == 1


def test_expired_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-expired-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)
    with test_session_local() as db:
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        auth_token.expires_at = auth_router._now() - timedelta(minutes=1)
        db.commit()

    response = _confirm_verification(client, token)

    assert response.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.email_verification.token_rejected",
            rejection_reason="expired",
        )
        assert len(rejected) == 1


def test_invalid_random_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
) -> None:
    raw_token = f"missing-token-{uuid.uuid4()}"

    response = _confirm_verification(client, raw_token)

    assert response.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.email_verification.token_rejected",
            rejection_reason="invalid",
        )
        assert len(rejected) == 1
        _assert_no_auth_event_leakage(db, _events(db), forbidden_values=[raw_token])


def test_password_reset_token_is_rejected_as_wrong_type(
    client: TestClient,
    test_session_local,
) -> None:
    user = _register(client, f"q43-wrong-type-{uuid.uuid4()}@example.com")
    raw_token = f"password-reset-{uuid.uuid4()}"
    with test_session_local() as db:
        db.add(
            AuthToken(
                token_type="password_reset",
                user_id=uuid.UUID(user["id"]),
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                expires_at=auth_router._now() + timedelta(hours=1),
            )
        )
        db.commit()

    response = _confirm_verification(client, raw_token)

    assert response.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.email_verification.token_rejected",
            rejection_reason="wrong_type",
        )
        assert len(rejected) == 1


def test_repeated_confirm_only_succeeds_once(
    client: TestClient,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-repeat-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)

    first = _confirm_verification(client, token)
    second = _confirm_verification(client, token)

    assert first.status_code == 200
    assert second.status_code == 400


def test_sessions_are_not_revoked_on_successful_verification(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-sessions-{uuid.uuid4()}@example.com")
    first_login = _login(client, user["email"])
    second_login = _login(client, user["email"])
    assert _request_verification(client, first_login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)

    assert _confirm_verification(client, token).status_code == 200

    with test_session_local() as db:
        sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == uuid.UUID(user["id"]))).all()
        assert len(sessions) == 2
        assert all(not session.is_revoked for session in sessions)
        _assert_no_auth_event_leakage(
            db,
            _events(db),
            forbidden_values=[first_login["refresh_token"], second_login["refresh_token"]],
        )


def test_auth_security_events_do_not_store_token_hash_url_or_email(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-leakage-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    verification_url = email_service.sent_emails[0].context["verification_url"]

    assert _confirm_verification(client, token).status_code == 200

    with test_session_local() as db:
        _assert_no_auth_event_leakage(
            db,
            _events(db),
            forbidden_values=[token, token_hash, verification_url, user["email"]],
        )


def test_confirm_does_not_leak_secrets_to_captured_logs(
    client: TestClient,
    email_service: TestCaptureEmailService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = _register(client, f"q43-caplog-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    verification_url = email_service.sent_emails[0].context["verification_url"]

    caplog.clear()
    with caplog.at_level(logging.INFO):
        response = _confirm_verification(client, token)

    assert response.status_code == 200
    captured_logs = caplog.text
    for forbidden_value in [token, token_hash, verification_url, user["email"]]:
        assert forbidden_value not in captured_logs


def test_valid_token_for_already_verified_user_consumes_without_overwrite(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-token-already-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    token = _raw_token_from_email(email_service)
    original_verified_at = datetime(2026, 5, 18, 10, 30, tzinfo=timezone.utc)
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        db_user.email_verified_at = original_verified_at
        db.commit()

    response = _confirm_verification(client, token)

    assert response.status_code == 200
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        assert auth_router._as_aware(db_user.email_verified_at) == original_verified_at
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        assert auth_token.used_at is not None
        completed = _events(db, event_type="auth.email_verification.completed")
        assert len(completed) == 1
        assert completed[0].metadata_json == {"already_verified": True}


def test_stale_second_verification_token_succeeds_without_overwriting_timestamp_or_revoking_sessions(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q43-stale-{uuid.uuid4()}@example.com")
    login = _login(client, user["email"])
    assert _request_verification(client, login["access_token"]).status_code == 202
    assert _request_verification(client, login["access_token"]).status_code == 202
    token_a = _raw_token_from_email(email_service, 0)
    token_b = _raw_token_from_email(email_service, 1)

    assert _confirm_verification(client, token_a).status_code == 200
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        original_verified_at = auth_router._as_aware(db_user.email_verified_at)

    assert _confirm_verification(client, token_b).status_code == 200

    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        assert auth_router._as_aware(db_user.email_verified_at) == original_verified_at
        tokens = db.scalars(select(AuthToken).order_by(AuthToken.created_at)).all()
        assert len(tokens) == 2
        assert all(token.used_at is not None for token in tokens)
        sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == uuid.UUID(user["id"]))).all()
        assert sessions
        assert all(not session.is_revoked for session in sessions)


def test_unverified_admin_user_can_still_login_and_access_me(
    client: TestClient,
    test_session_local,
) -> None:
    user = _register(client, f"q43-unverified-login-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        assert db_user.email_verified_at is None

    login = _login(client, user["email"])
    me = client.get("/api/v1/auth/me", headers=_auth_headers(login["access_token"]))

    assert me.status_code == 200
    assert me.json()["email"] == user["email"]


def test_verified_admin_user_can_still_login(
    client: TestClient,
    test_session_local,
) -> None:
    user = _register(client, f"q43-verified-login-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        db_user.email_verified_at = auth_router._now()
        db.commit()

    login = _login(client, user["email"])

    assert login["access_token"]
