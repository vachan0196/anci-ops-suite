from collections.abc import Generator, Iterable
from datetime import timedelta
import hashlib
import json
import logging
from urllib.parse import parse_qs, urlparse
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import verify_password
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
NEW_PASSWORD = "new-password-456"
GENERIC_MESSAGE = "If an account exists for that email, instructions have been sent."


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q4_2_password_reset.db"
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


def _request_reset(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )
    assert response.status_code == 202
    return response.json()


def _raw_token_from_email(email_service: TestCaptureEmailService, index: int = 0) -> str:
    reset_url = email_service.sent_emails[index].context["reset_url"]
    parsed = urlparse(reset_url)
    token_values = parse_qs(parsed.query)["token"]
    assert len(token_values) == 1
    return token_values[0]


def _confirm_reset(
    client: TestClient,
    token: str,
    *,
    new_password: str = NEW_PASSWORD,
    confirm_password: str | None = None,
):
    return client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": token,
            "new_password": new_password,
            "confirm_password": confirm_password if confirm_password is not None else new_password,
        },
    )


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


def test_unknown_email_returns_generic_and_logs_safe_event(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    body = _request_reset(client, "missing@example.com")

    assert body == {"message": GENERIC_MESSAGE}
    assert email_service.sent_emails == []
    with test_session_local() as db:
        assert db.scalars(select(AuthToken)).all() == []
        events = _events(db, event_type="auth.password_reset.requested")
        assert len(events) == 1
        assert events[0].user_id is None
        assert events[0].metadata_json == {"resolved_user": False}
        assert "missing@example.com" not in _event_payload(events[0])


def test_known_active_user_returns_generic_creates_token_and_sends_email(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-active-{uuid.uuid4()}@example.com")

    body = _request_reset(client, user["email"])

    assert body == {"message": GENERIC_MESSAGE}
    assert len(email_service.sent_emails) == 1
    captured = email_service.sent_emails[0]
    assert captured.to == user["email"]
    assert captured.template_id == "password_reset"
    assert captured.context["user_id"] == user["id"]
    assert "reset_url" in captured.context
    assert "expires_at" in captured.context
    with test_session_local() as db:
        tokens = db.scalars(select(AuthToken)).all()
        assert len(tokens) == 1
        assert tokens[0].token_type == "password_reset"
        assert str(tokens[0].user_id) == user["id"]
        assert tokens[0].used_at is None
        assert tokens[0].token_hash != _raw_token_from_email(email_service)
        requested = _events(db, event_type="auth.password_reset.requested")
        assert len(requested) == 1
        assert str(requested[0].user_id) == user["id"]
        assert requested[0].metadata_json == {"resolved_user": True}


def test_disabled_user_returns_generic_without_email_or_token(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-disabled-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        db_user.is_active = False
        db.commit()

    body = _request_reset(client, user["email"])

    assert body == {"message": GENERIC_MESSAGE}
    assert email_service.sent_emails == []
    with test_session_local() as db:
        assert db.scalars(select(AuthToken)).all() == []
        event = _events(db, event_type="auth.password_reset.requested")[0]
        assert event.user_id is None
        assert event.metadata_json == {"resolved_user": False}
        assert user["email"] not in _event_payload(event)


def test_request_response_does_not_reveal_account_state(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    active = _register(client, f"q42-state-active-{uuid.uuid4()}@example.com")
    disabled = _register(client, f"q42-state-disabled-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(disabled["id"]))
        assert db_user is not None
        db_user.is_active = False
        db.commit()

    active_response = client.post("/api/v1/auth/password-reset/request", json={"email": active["email"]})
    disabled_response = client.post("/api/v1/auth/password-reset/request", json={"email": disabled["email"]})
    unknown_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown-state@example.com"},
    )

    assert active_response.status_code == disabled_response.status_code == unknown_response.status_code == 202
    assert active_response.json() == disabled_response.json() == unknown_response.json()
    assert len(email_service.sent_emails) == 1


def test_multiple_valid_password_reset_tokens_can_coexist(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-multiple-{uuid.uuid4()}@example.com")

    _request_reset(client, user["email"])
    _request_reset(client, user["email"])

    assert len(email_service.sent_emails) == 2
    with test_session_local() as db:
        tokens = db.scalars(select(AuthToken).order_by(AuthToken.created_at)).all()
        assert len(tokens) == 2
        assert tokens[0].used_at is None
        assert tokens[1].used_at is None
        assert tokens[0].token_hash != tokens[1].token_hash


def test_valid_token_changes_password_marks_used_and_revokes_sessions(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-confirm-{uuid.uuid4()}@example.com")
    first_login = _login(client, user["email"])
    second_login = _login(client, user["email"])
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)

    response = _confirm_reset(client, token)

    assert response.status_code == 200
    assert response.json() == {"success": True}
    with test_session_local() as db:
        db_user = db.get(User, uuid.UUID(user["id"]))
        assert db_user is not None
        assert verify_password(NEW_PASSWORD, db_user.hashed_password)
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        assert auth_token.used_at is not None
        assert auth_token.consumed_ip is not None
        sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == uuid.UUID(user["id"]))).all()
        assert len(sessions) == 2
        assert all(session.is_revoked for session in sessions)
        revoked_events = _events(db, event_type="auth.password_reset.session_revoked")
        assert len(revoked_events) == 2
        completed = _events(db, event_type="auth.password_reset.completed")
        assert len(completed) == 1
        _assert_no_auth_event_leakage(
            db,
            _events(db),
            forbidden_values=[token, first_login["refresh_token"], second_login["refresh_token"], NEW_PASSWORD],
        )


def test_new_password_works_and_old_password_fails_after_reset(
    client: TestClient,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-login-after-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)

    assert _confirm_reset(client, token).status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        data={"username": user["email"], "password": PASSWORD},
    )
    new_login = client.post(
        "/api/v1/auth/login",
        data={"username": user["email"], "password": NEW_PASSWORD},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_invalid_password_does_not_mark_token_used(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-invalid-password-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)

    response = _confirm_reset(client, token, new_password="x" * 73)

    assert response.status_code == 422
    with test_session_local() as db:
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        assert auth_token.used_at is None


def test_password_confirmation_mismatch_does_not_mark_token_used(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-mismatch-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)

    response = _confirm_reset(client, token, new_password=NEW_PASSWORD, confirm_password="different")

    assert response.status_code == 422
    with test_session_local() as db:
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        assert auth_token.used_at is None


def test_used_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-used-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)
    assert _confirm_reset(client, token).status_code == 200

    second = _confirm_reset(client, token, new_password="another-password-789")

    assert second.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.password_reset.token_rejected",
            rejection_reason="used",
        )
        assert len(rejected) == 1


def test_expired_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-expired-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)
    with test_session_local() as db:
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        auth_token.expires_at = auth_router._now() - timedelta(minutes=1)
        db.commit()

    response = _confirm_reset(client, token)

    assert response.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.password_reset.token_rejected",
            rejection_reason="expired",
        )
        assert len(rejected) == 1


def test_invalid_random_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
) -> None:
    raw_token = f"missing-token-{uuid.uuid4()}"

    response = _confirm_reset(client, raw_token)

    assert response.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.password_reset.token_rejected",
            rejection_reason="invalid",
        )
        assert len(rejected) == 1
        _assert_no_auth_event_leakage(db, _events(db), forbidden_values=[raw_token, NEW_PASSWORD])


def test_wrong_type_token_is_rejected_and_logged(
    client: TestClient,
    test_session_local,
) -> None:
    user = _register(client, f"q42-wrong-type-{uuid.uuid4()}@example.com")
    raw_token = f"email-verification-{uuid.uuid4()}"
    with test_session_local() as db:
        db.add(
            AuthToken(
                token_type="email_verification",
                user_id=uuid.UUID(user["id"]),
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                expires_at=auth_router._now() + timedelta(hours=1),
            )
        )
        db.commit()

    response = _confirm_reset(client, raw_token)

    assert response.status_code == 400
    with test_session_local() as db:
        rejected = _events(
            db,
            event_type="auth.password_reset.token_rejected",
            rejection_reason="wrong_type",
        )
        assert len(rejected) == 1


def test_same_password_reset_succeeds_and_revokes_sessions(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-same-password-{uuid.uuid4()}@example.com")
    _login(client, user["email"])
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)

    response = _confirm_reset(client, token, new_password=PASSWORD)

    assert response.status_code == 200
    with test_session_local() as db:
        sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == uuid.UUID(user["id"]))).all()
        assert sessions
        assert all(session.is_revoked for session in sessions)
        auth_token = db.scalar(select(AuthToken))
        assert auth_token is not None
        assert auth_token.used_at is not None


def test_repeated_confirm_only_succeeds_once(
    client: TestClient,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-repeat-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)

    first = _confirm_reset(client, token)
    second = _confirm_reset(client, token, new_password="another-password-789")

    assert first.status_code == 200
    assert second.status_code == 400


def test_raw_token_and_hash_are_not_stored_in_auth_security_events(
    client: TestClient,
    test_session_local,
    email_service: TestCaptureEmailService,
) -> None:
    user = _register(client, f"q42-leakage-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    assert _confirm_reset(client, token).status_code == 200

    with test_session_local() as db:
        _assert_no_auth_event_leakage(
            db,
            _events(db),
            forbidden_values=[
                token,
                token_hash,
                NEW_PASSWORD,
                email_service.sent_emails[0].context["reset_url"],
                user["email"],
            ],
        )


def test_password_reset_confirm_does_not_leak_secrets_to_captured_logs(
    client: TestClient,
    email_service: TestCaptureEmailService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    user = _register(client, f"q42-caplog-{uuid.uuid4()}@example.com")
    _request_reset(client, user["email"])
    token = _raw_token_from_email(email_service)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    reset_url = email_service.sent_emails[0].context["reset_url"]

    caplog.clear()
    with caplog.at_level(logging.INFO):
        response = _confirm_reset(client, token)

    assert response.status_code == 200
    captured_logs = caplog.text
    for forbidden_value in [token, token_hash, reset_url, NEW_PASSWORD, user["email"]]:
        assert forbidden_value not in captured_logs
