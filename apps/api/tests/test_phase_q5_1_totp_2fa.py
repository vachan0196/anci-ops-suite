from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import base64
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token
from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.admin_user_2fa import AdminUser2FA
from apps.api.models.auth_2fa_challenge import Auth2FAChallenge
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.auth_token import AuthToken
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers import auth as auth_router
from apps.api.services.totp_crypto import (
    decode_totp_encryption_key,
    decrypt_totp_secret,
    encrypt_totp_secret,
)

PASSWORD = "password123"
TEST_KEY_BYTES = b"0123456789abcdef0123456789abcdef"
TEST_KEY = base64.b64encode(TEST_KEY_BYTES).decode("ascii")


@pytest.fixture(autouse=True)
def totp_key(monkeypatch):
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", TEST_KEY)


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q5_1_totp_2fa.db"
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


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, email: str) -> dict:
    _register(client, email)
    login = _login(client, email)
    return {"email": email, "access_token": login["access_token"]}


def _begin_enrol(client: TestClient, access_token: str) -> dict:
    response = client.post(
        "/api/v1/auth/2fa/totp/enrol/begin",
        headers=_auth(access_token),
    )
    assert response.status_code == 200
    return response.json()


def _confirm_enrol(client: TestClient, access_token: str, secret: str) -> dict:
    response = client.post(
        "/api/v1/auth/2fa/totp/enrol/confirm",
        headers=_auth(access_token),
        json={"code": _totp_code(secret)},
    )
    assert response.status_code == 200
    return response.json()


def _enable_2fa(client: TestClient, email: str) -> dict:
    admin = _register_and_login(client, email)
    begin = _begin_enrol(client, admin["access_token"])
    confirm = _confirm_enrol(client, admin["access_token"], begin["manual_secret"])
    return {**admin, "manual_secret": begin["manual_secret"], "recovery_codes": confirm["recovery_codes"]}


def _login_requires_2fa(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["requires_2fa"] is True
    assert body["token_type"] == "2fa_pending"
    assert body["two_factor_challenge_token"]
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert settings.AUTH_REFRESH_COOKIE_NAME not in response.cookies
    return body


def _totp_code(secret: str) -> str:
    return pyotp.TOTP(secret).at(int(auth_router._now().timestamp()))


def _unused_recovery_code_count(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(AuthToken.id)).where(
                AuthToken.user_id == user_id,
                AuthToken.token_type == "recovery_code",
                AuthToken.used_at.is_(None),
            )
        )
        or 0
    )


def _used_recovery_code_count(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(AuthToken.id)).where(
                AuthToken.user_id == user_id,
                AuthToken.token_type == "recovery_code",
                AuthToken.used_at.is_not(None),
            )
        )
        or 0
    )


def test_totp_encryption_key_validation_and_aes_gcm(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", None)
    with pytest.raises(ValueError, match="required"):
        decode_totp_encryption_key()

    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", base64.b64encode(b"short").decode("ascii"))
    with pytest.raises(ValueError, match="32 bytes"):
        decode_totp_encryption_key()

    monkeypatch.setattr(settings, "TOTP_ENCRYPTION_KEY", TEST_KEY)
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", TEST_KEY)
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        decode_totp_encryption_key()

    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "not-the-totp-key")
    first = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
    second = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
    assert first.ciphertext != second.ciphertext
    assert first.nonce != second.nonce
    assert decrypt_totp_secret(
        ciphertext=first.ciphertext,
        nonce=first.nonce,
        key_version=first.key_version,
    ) == "JBSWY3DPEHPK3PXP"

    tampered = first.ciphertext[:-2] + "AA"
    with pytest.raises(ValueError, match="decrypt"):
        decrypt_totp_secret(
            ciphertext=tampered,
            nonce=first.nonce,
            key_version=first.key_version,
        )


def test_status_begin_confirm_and_recovery_code_storage(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "q5-status@example.com")

    initial = client.get("/api/v1/auth/2fa/status", headers=_auth(admin["access_token"]))
    assert initial.status_code == 200
    assert initial.json() == {
        "totp_enrolled": False,
        "totp_enrolled_at": None,
        "pending_enrolment": False,
        "pending_expires_at": None,
        "recovery_codes_remaining": 0,
    }

    begin = _begin_enrol(client, admin["access_token"])
    assert begin["status"] == "pending"
    assert begin["manual_secret"]
    assert begin["otpauth_url"].startswith("otpauth://totp/")

    pending_status = client.get("/api/v1/auth/2fa/status", headers=_auth(admin["access_token"]))
    assert pending_status.status_code == 200
    assert pending_status.json()["pending_enrolment"] is True
    assert pending_status.json()["totp_enrolled"] is False

    bad_confirm = client.post(
        "/api/v1/auth/2fa/totp/enrol/confirm",
        headers=_auth(admin["access_token"]),
        json={"code": "000000"},
    )
    assert bad_confirm.status_code == 400

    confirm = _confirm_enrol(client, admin["access_token"], begin["manual_secret"])
    assert confirm["status"] == "enabled"
    assert len(confirm["recovery_codes"]) == 10

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == admin["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        assert two_factor is not None
        assert two_factor.totp_enrolled_at is not None
        assert two_factor.pending_secret_ciphertext is None
        assert two_factor.totp_secret_ciphertext != begin["manual_secret"]

        recovery_tokens = list(
            db.scalars(
                select(AuthToken).where(
                    AuthToken.user_id == user.id,
                    AuthToken.token_type == "recovery_code",
                )
            ).all()
        )
        assert len(recovery_tokens) == 10
        assert {token.expires_at for token in recovery_tokens} == {None}
        assert all(token.token_hash not in confirm["recovery_codes"] for token in recovery_tokens)
    finally:
        db.close()

    enabled_status = client.get("/api/v1/auth/2fa/status", headers=_auth(admin["access_token"]))
    assert enabled_status.status_code == 200
    assert enabled_status.json()["totp_enrolled"] is True
    assert enabled_status.json()["recovery_codes_remaining"] == 10


def test_employee_token_is_blocked_from_admin_2fa_endpoints(client: TestClient) -> None:
    employee_token = create_access_token(f"employee:{uuid.uuid4()}")
    for method, path in (
        ("get", "/api/v1/auth/2fa/status"),
        ("post", "/api/v1/auth/2fa/totp/enrol/begin"),
        ("post", "/api/v1/auth/2fa/totp/enrol/confirm"),
    ):
        request = getattr(client, method)
        if method == "post":
            response = request(path, headers=_auth(employee_token), json={"code": "123456"})
        else:
            response = request(path, headers=_auth(employee_token))
        assert response.status_code == 401


def test_login_without_active_2fa_remains_compatible(client: TestClient) -> None:
    _register(client, "q5-no-2fa@example.com")
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "q5-no-2fa@example.com", "password": PASSWORD},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert "requires_2fa" not in body


def test_pending_secret_does_not_trigger_login_challenge(client: TestClient) -> None:
    admin = _register_and_login(client, "q5-pending-login@example.com")
    _begin_enrol(client, admin["access_token"])

    login = _login(client, admin["email"])
    assert login["access_token"]
    assert login["token_type"] == "bearer"


def test_login_with_active_2fa_challenge_has_no_api_authority(client: TestClient) -> None:
    enabled = _enable_2fa(client, "q5-challenge@example.com")
    challenge = _login_requires_2fa(client, enabled["email"])

    me_response = client.get(
        "/api/v1/auth/me",
        headers=_auth(challenge["two_factor_challenge_token"]),
    )
    assert me_response.status_code == 401


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED,
    reason="Rate limiting disabled for test run",
)
def test_2fa_verify_rate_limit_when_enabled(client: TestClient) -> None:
    enabled = _enable_2fa(client, f"q5-rate-limit-{uuid.uuid4()}@example.com")
    challenge = _login_requires_2fa(client, enabled["email"])
    payload = {
        "two_factor_challenge_token": challenge["two_factor_challenge_token"],
        "code": "000000",
        "recovery_code": "not-a-valid-recovery-code",
    }

    hit_rate_limit = False
    for attempt in range(6):
        response = client.post("/api/v1/auth/2fa/verify", json=payload)
        if attempt < 5:
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        if response.status_code == 429:
            assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            hit_rate_limit = True
            break

    assert hit_rate_limit is True


def test_valid_totp_verify_issues_normal_session_and_cookie(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-verify@example.com")
    challenge = _login_requires_2fa(client, enabled["email"])

    verify = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": challenge["two_factor_challenge_token"],
            "code": pyotp.TOTP(enabled["manual_secret"]).now(),
        },
    )
    body = verify.json()
    assert verify.status_code == 200
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert settings.AUTH_REFRESH_COOKIE_NAME in verify.cookies

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        session_count = db.scalar(select(func.count(AuthSession.id)).where(AuthSession.user_id == user.id))
        assert session_count == 2
        assert client.post(
            "/api/v1/auth/2fa/verify",
            json={
                "two_factor_challenge_token": challenge["two_factor_challenge_token"],
                "code": pyotp.TOTP(enabled["manual_secret"]).now(),
            },
        ).status_code == 400
    finally:
        db.close()


def test_challenge_expiry_lock_and_inactive_user_behaviour(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-challenge-rules@example.com")
    challenge = _login_requires_2fa(client, enabled["email"])

    for expected_status in (400, 400, 400, 400, 429):
        response = client.post(
            "/api/v1/auth/2fa/verify",
            json={
                "two_factor_challenge_token": challenge["two_factor_challenge_token"],
                "code": "000000",
            },
        )
        assert response.status_code == expected_status

    db = test_session_local()
    try:
        locked = db.scalar(select(Auth2FAChallenge).where(Auth2FAChallenge.locked_at.is_not(None)))
        assert locked is not None
        assert locked.failed_attempts == 5
    finally:
        db.close()

    expired = _login_requires_2fa(client, enabled["email"])
    db = test_session_local()
    try:
        row = db.scalar(
            select(Auth2FAChallenge).where(
                Auth2FAChallenge.challenge_hash == auth_router._hash_auth_token(
                    expired["two_factor_challenge_token"]
                )
            )
        )
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": expired["two_factor_challenge_token"],
            "code": pyotp.TOTP(enabled["manual_secret"]).now(),
        },
    ).status_code == 400

    inactive = _login_requires_2fa(client, enabled["email"])
    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        user.is_active = False
        db.commit()
    finally:
        db.close()
    assert client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": inactive["two_factor_challenge_token"],
            "code": pyotp.TOTP(enabled["manual_secret"]).now(),
        },
    ).status_code == 400


def test_totp_window_and_replay(monkeypatch, client: TestClient) -> None:
    fixed_now = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(auth_router, "_now", lambda: fixed_now)
    enabled = _enable_2fa(client, "q5-window@example.com")

    previous_window_challenge = _login_requires_2fa(client, enabled["email"])
    previous_window_code = pyotp.TOTP(enabled["manual_secret"]).at(
        int((fixed_now - timedelta(seconds=30)).timestamp())
    )
    previous_verify = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": previous_window_challenge["two_factor_challenge_token"],
            "code": previous_window_code,
        },
    )
    assert previous_verify.status_code == 200

    replay_challenge = _login_requires_2fa(client, enabled["email"])
    replay = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": replay_challenge["two_factor_challenge_token"],
            "code": previous_window_code,
        },
    )
    assert replay.status_code == 400

    outside_window_challenge = _login_requires_2fa(client, enabled["email"])
    outside_code = pyotp.TOTP(enabled["manual_secret"]).at(
        int((fixed_now + timedelta(seconds=90)).timestamp())
    )
    outside = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": outside_window_challenge["two_factor_challenge_token"],
            "code": outside_code,
        },
    )
    assert outside.status_code == 400


def test_recovery_code_verification_consumes_single_use_code(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-recovery@example.com")
    recovery_code = enabled["recovery_codes"][0]
    challenge = _login_requires_2fa(client, enabled["email"])

    verify = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": challenge["two_factor_challenge_token"],
            "recovery_code": recovery_code,
        },
    )
    assert verify.status_code == 200
    assert verify.json()["access_token"]

    second_challenge = _login_requires_2fa(client, enabled["email"])
    reuse = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": second_challenge["two_factor_challenge_token"],
            "recovery_code": recovery_code,
        },
    )
    assert reuse.status_code == 400

    db = test_session_local()
    try:
        used_count = db.scalar(
            select(func.count(AuthToken.id)).where(
                AuthToken.token_type == "recovery_code",
                AuthToken.used_at.is_not(None),
            )
        )
        assert used_count == 1
    finally:
        db.close()


def test_disable_2fa_with_password_and_totp_clears_state_and_allows_reenrol(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-disable-totp@example.com")

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        two_factor.pending_secret_ciphertext = "pending-ciphertext"
        two_factor.pending_secret_nonce = "pending-nonce"
        two_factor.pending_secret_key_version = 1
        two_factor.pending_started_at = datetime.now(timezone.utc)
        two_factor.pending_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        two_factor.totp_last_used_time_step = 1
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(enabled["access_token"]),
        json={"current_password": PASSWORD, "code": _totp_code(enabled["manual_secret"])},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        assert two_factor.totp_secret_ciphertext is None
        assert two_factor.totp_secret_nonce is None
        assert two_factor.totp_secret_key_version is None
        assert two_factor.totp_enrolled_at is None
        assert two_factor.totp_last_used_time_step is None
        assert two_factor.pending_secret_ciphertext is None
        assert two_factor.pending_secret_nonce is None
        assert two_factor.pending_secret_key_version is None
        assert two_factor.pending_started_at is None
        assert two_factor.pending_expires_at is None
        assert two_factor.disabled_at is not None
        assert _unused_recovery_code_count(db, user.id) == 0
        assert _used_recovery_code_count(db, user.id) == 10
    finally:
        db.close()

    begin = _begin_enrol(client, enabled["access_token"])
    assert begin["status"] == "pending"


def test_disable_2fa_with_password_and_recovery_code_consumes_code(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-disable-recovery@example.com")
    response = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(enabled["access_token"]),
        json={"current_password": PASSWORD, "recovery_code": enabled["recovery_codes"][0]},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        assert two_factor.disabled_at is not None
        assert _unused_recovery_code_count(db, user.id) == 0
        assert _used_recovery_code_count(db, user.id) == 10
    finally:
        db.close()


def test_disable_2fa_state_guards_and_auth_boundaries(client: TestClient) -> None:
    admin = _register_and_login(client, "q5-disable-guard@example.com")
    not_enabled = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(admin["access_token"]),
        json={"current_password": PASSWORD, "code": "123456"},
    )
    assert not_enabled.status_code == 409
    assert not_enabled.json()["error"]["code"] == "AUTH_2FA_NOT_ENABLED"

    enabled = _enable_2fa(client, "q5-disable-failures@example.com")
    wrong_password = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(enabled["access_token"]),
        json={"current_password": "wrong-password", "code": _totp_code(enabled["manual_secret"])},
    )
    assert wrong_password.status_code == 400
    assert wrong_password.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"

    wrong_factor = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(enabled["access_token"]),
        json={"current_password": PASSWORD, "code": "000000"},
    )
    assert wrong_factor.status_code == 400
    assert wrong_factor.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"

    employee_token = create_access_token(f"employee:{uuid.uuid4()}")
    employee_response = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(employee_token),
        json={"current_password": PASSWORD, "code": "123456"},
    )
    assert employee_response.status_code == 401


def test_regenerate_recovery_codes_with_totp_invalidates_old_codes_and_keeps_totp(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-regenerate-totp@example.com")
    old_recovery_code = enabled["recovery_codes"][0]

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        active_ciphertext = two_factor.totp_secret_ciphertext
    finally:
        db.close()

    response = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(enabled["access_token"]),
        json={"code": _totp_code(enabled["manual_secret"])},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "regenerated"
    assert len(body["recovery_codes"]) == 10
    assert old_recovery_code not in body["recovery_codes"]

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        assert two_factor.totp_secret_ciphertext == active_ciphertext
        assert two_factor.totp_enrolled_at is not None
        assert _unused_recovery_code_count(db, user.id) == 10
        assert _used_recovery_code_count(db, user.id) == 10
        token_hashes = list(
            db.scalars(
                select(AuthToken.token_hash).where(
                    AuthToken.user_id == user.id,
                    AuthToken.token_type == "recovery_code",
                    AuthToken.used_at.is_(None),
                )
            ).all()
        )
        assert all(code not in token_hashes for code in body["recovery_codes"])
    finally:
        db.close()

    old_code_challenge = _login_requires_2fa(client, enabled["email"])
    old_code_response = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": old_code_challenge["two_factor_challenge_token"],
            "recovery_code": old_recovery_code,
        },
    )
    assert old_code_response.status_code == 400

    new_code = body["recovery_codes"][0]
    new_code_response = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": old_code_challenge["two_factor_challenge_token"],
            "recovery_code": new_code,
        },
    )
    assert new_code_response.status_code == 200

    reuse_challenge = _login_requires_2fa(client, enabled["email"])
    reuse_response = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": reuse_challenge["two_factor_challenge_token"],
            "recovery_code": new_code,
        },
    )
    assert reuse_response.status_code == 400


def test_regenerate_recovery_codes_with_recovery_code_consumes_and_replaces_codes(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-regenerate-recovery@example.com")
    response = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(enabled["access_token"]),
        json={"recovery_code": enabled["recovery_codes"][0]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "regenerated"
    assert len(body["recovery_codes"]) == 10
    assert all(code not in body["recovery_codes"] for code in enabled["recovery_codes"])

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        assert _unused_recovery_code_count(db, user.id) == 10
        assert _used_recovery_code_count(db, user.id) == 10
    finally:
        db.close()


def test_regenerate_recovery_codes_state_guards_and_auth_boundaries(client: TestClient) -> None:
    admin = _register_and_login(client, "q5-regenerate-guard@example.com")
    not_enabled = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(admin["access_token"]),
        json={"code": "123456"},
    )
    assert not_enabled.status_code == 409
    assert not_enabled.json()["error"]["code"] == "AUTH_2FA_NOT_ENABLED"

    enabled = _enable_2fa(client, "q5-regenerate-failures@example.com")
    wrong_factor = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(enabled["access_token"]),
        json={"code": "000000"},
    )
    assert wrong_factor.status_code == 400
    assert wrong_factor.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"

    employee_token = create_access_token(f"employee:{uuid.uuid4()}")
    employee_response = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(employee_token),
        json={"code": "123456"},
    )
    assert employee_response.status_code == 401


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED,
    reason="Rate limiting disabled for test run",
)
def test_2fa_disable_rate_limit_when_enabled(client: TestClient) -> None:
    enabled = _enable_2fa(client, f"q5-disable-rate-limit-{uuid.uuid4()}@example.com")
    payload = {"current_password": "wrong-password", "code": "000000"}

    hit_rate_limit = False
    for attempt in range(6):
        response = client.post(
            "/api/v1/auth/2fa/disable",
            headers=_auth(enabled["access_token"]),
            json=payload,
        )
        if attempt < 5:
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"
        if response.status_code == 429:
            assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            hit_rate_limit = True
            break

    assert hit_rate_limit is True


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED,
    reason="Rate limiting disabled for test run",
)
def test_2fa_recovery_regenerate_rate_limit_when_enabled(client: TestClient) -> None:
    enabled = _enable_2fa(client, f"q5-regenerate-rate-limit-{uuid.uuid4()}@example.com")
    payload = {"code": "000000"}

    hit_rate_limit = False
    for attempt in range(6):
        response = client.post(
            "/api/v1/auth/2fa/recovery-codes/regenerate",
            headers=_auth(enabled["access_token"]),
            json=payload,
        )
        if attempt < 5:
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "AUTH_2FA_VERIFICATION_FAILED"
        if response.status_code == 429:
            assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            hit_rate_limit = True
            break

    assert hit_rate_limit is True


def test_role_compatibility_for_owner_admin_and_member_self_enrolment(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_and_login(client, "q5-owner-role@example.com")

    db = test_session_local()
    try:
        owner_user = db.scalar(select(User).where(User.email == owner["email"]))
        tenant_id = owner_user.active_tenant_id
        for role in ("admin", "member"):
            user = User(
                email=f"q5-{role}-role@example.com",
                hashed_password=owner_user.hashed_password,
                is_active=True,
                active_tenant_id=tenant_id,
            )
            db.add(user)
            db.flush()
            db.add(TenantUser(tenant_id=tenant_id, user_id=user.id, role=role))
        db.commit()
    finally:
        db.close()

    for email in (
        "q5-owner-role@example.com",
        "q5-admin-role@example.com",
        "q5-member-role@example.com",
    ):
        login = _login(client, email)
        begin = _begin_enrol(client, login["access_token"])
        assert begin["manual_secret"]


def test_enrol_begin_is_blocked_when_2fa_is_already_active(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-reenrol@example.com")
    first_secret = enabled["manual_secret"]
    login = _login_requires_2fa(client, enabled["email"])
    verify = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": login["two_factor_challenge_token"],
            "code": pyotp.TOTP(first_secret).now(),
        },
    )
    access_token = verify.json()["access_token"]

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        active_ciphertext = two_factor.totp_secret_ciphertext
        recovery_count = db.scalar(
            select(func.count(AuthToken.id)).where(
                AuthToken.user_id == user.id,
                AuthToken.token_type == "recovery_code",
                AuthToken.used_at.is_(None),
            )
        )
        assert recovery_count == 10
    finally:
        db.close()

    blocked = client.post(
        "/api/v1/auth/2fa/totp/enrol/begin",
        headers=_auth(access_token),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "AUTH_2FA_ALREADY_ENABLED"
    assert blocked.json()["error"]["message"] == "Two-factor authentication is already enabled"

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == enabled["email"]))
        two_factor = db.scalar(select(AdminUser2FA).where(AdminUser2FA.user_id == user.id))
        assert two_factor.totp_secret_ciphertext == active_ciphertext
        assert two_factor.pending_secret_ciphertext is None
        recovery_count = db.scalar(
            select(func.count(AuthToken.id)).where(
                AuthToken.user_id == user.id,
                AuthToken.token_type == "recovery_code",
                AuthToken.used_at.is_(None),
            )
        )
        assert recovery_count == 10
    finally:
        db.close()


def test_auth_security_events_do_not_store_sensitive_2fa_values(
    client: TestClient,
    test_session_local,
) -> None:
    enabled = _enable_2fa(client, "q5-events@example.com")
    failed_regeneration = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(enabled["access_token"]),
        json={"code": "000000"},
    )
    assert failed_regeneration.status_code == 400

    regenerated = client.post(
        "/api/v1/auth/2fa/recovery-codes/regenerate",
        headers=_auth(enabled["access_token"]),
        json={"recovery_code": enabled["recovery_codes"][0]},
    )
    assert regenerated.status_code == 200
    regenerated_codes = regenerated.json()["recovery_codes"]

    challenge = _login_requires_2fa(client, enabled["email"])
    recovery_code = regenerated_codes[0]
    verify = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "two_factor_challenge_token": challenge["two_factor_challenge_token"],
            "recovery_code": recovery_code,
        },
    )
    assert verify.status_code == 200
    disable = client.post(
        "/api/v1/auth/2fa/disable",
        headers=_auth(verify.json()["access_token"]),
        json={"current_password": PASSWORD, "code": _totp_code(enabled["manual_secret"])},
    )
    assert disable.status_code == 200

    db = test_session_local()
    try:
        events = list(db.scalars(select(AuthSecurityEvent)).all())
        event_types = {event.event_type for event in events}
        assert "auth.2fa.enrolment_started" in event_types
        assert "auth.2fa.enrolment_completed" in event_types
        assert "auth.2fa.verification_failed" in event_types
        assert "auth.2fa.recovery_code_used" in event_types
        assert "auth.2fa.recovery_codes_regenerated" in event_types
        assert "auth.2fa.verification_succeeded" in event_types
        assert "auth.2fa.disabled" in event_types

        forbidden_values = {
            enabled["manual_secret"],
            recovery_code,
            challenge["two_factor_challenge_token"],
            *enabled["recovery_codes"],
            *regenerated_codes,
        }
        for event in events:
            metadata_text = str(event.metadata_json or {})
            assert all(value not in metadata_text for value in forbidden_values)
            assert "otpauth" not in metadata_text
            assert "manual_secret" not in metadata_text
            assert "recovery_code" not in metadata_text
            assert "challenge" not in metadata_text
            assert "token_hash" not in metadata_text
            assert "password" not in metadata_text
            assert "secret_ciphertext" not in metadata_text
    finally:
        db.close()
