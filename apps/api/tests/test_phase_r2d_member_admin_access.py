from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import secrets
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.security import create_access_token, hash_refresh_token
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_2fa_challenge import Auth2FAChallenge
from apps.api.models.auth_session import AuthSession
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers import auth as auth_router

PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_r2d_member_admin_access.db"
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_owner(client: TestClient, email: str) -> dict:
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    body = register.json()
    body["email"] = email
    body["access_token"] = login.json()["access_token"]
    body["refresh_token"] = login.json()["refresh_token"]
    return body


def _create_tenant_user(
    client: TestClient,
    owner: dict,
    *,
    email: str,
    role: str,
) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": f"Phase R2d {role}",
            "role": role,
        },
        headers=_auth(owner["access_token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_store(client: TestClient, owner: dict) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"R2D-{uuid.uuid4()}",
            "name": "Phase R2d Store",
            "timezone": "Europe/London",
        },
        headers=_auth(owner["access_token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _get_user(test_session_local, user_id: str) -> User:
    db = test_session_local()
    try:
        user = db.get(User, uuid.UUID(user_id))
        assert user is not None
        db.expunge(user)
        return user
    finally:
        db.close()


def _create_legacy_admin_session(test_session_local, user: User) -> tuple[str, str]:
    raw_refresh_token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    db = test_session_local()
    try:
        session = AuthSession(
            tenant_id=user.active_tenant_id,
            user_id=user.id,
            portal="admin",
            token_hash=hash_refresh_token(raw_refresh_token),
            session_family_id=uuid.uuid4(),
            is_revoked=False,
            expires_at=now + timedelta(days=14),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        access_token = create_access_token(str(user.id), auth_session_id=str(session.id))
        return raw_refresh_token, access_token
    finally:
        db.close()


def _create_legacy_2fa_challenge(test_session_local, user: User) -> str:
    raw_challenge = secrets.token_urlsafe(48)
    db = test_session_local()
    try:
        db.add(
            Auth2FAChallenge(
                user_id=user.id,
                tenant_id=user.active_tenant_id,
                challenge_hash=auth_router._hash_auth_token(raw_challenge),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        db.commit()
        return raw_challenge
    finally:
        db.close()


def _complete_company_payload(**overrides) -> dict:
    payload = {
        "company_name": "R2d Forecourt Ltd",
        "owner_name": "Owner User",
        "business_email": "owner@example.com",
        "phone_number": "07123456789",
        "registered_address": "1 Test Road",
    }
    payload.update(overrides)
    return payload


def test_member_cannot_obtain_admin_token_but_owner_and_admin_can_login(client: TestClient) -> None:
    owner = _register_owner(client, f"r2d-owner-{uuid.uuid4()}@example.com")
    member_email = f"r2d-member-{uuid.uuid4()}@example.com"
    admin_email = f"r2d-admin-{uuid.uuid4()}@example.com"
    _create_tenant_user(client, owner, email=member_email, role="member")
    _create_tenant_user(client, owner, email=admin_email, role="admin")

    member_login = client.post(
        "/api/v1/auth/login",
        data={"username": member_email, "password": PASSWORD},
    )
    assert member_login.status_code == 403
    assert member_login.json()["error"]["code"] == "AUTH_ADMIN_PORTAL_ROLE_REQUIRED"
    assert "access_token" not in member_login.text
    assert "refresh_token" not in member_login.text

    owner_login = client.post(
        "/api/v1/auth/login",
        data={"username": owner["email"], "password": PASSWORD},
    )
    assert owner_login.status_code == 200, owner_login.text
    assert owner_login.json()["access_token"]

    admin_login = client.post(
        "/api/v1/auth/login",
        data={"username": admin_email, "password": PASSWORD},
    )
    assert admin_login.status_code == 200, admin_login.text
    assert admin_login.json()["access_token"]


def test_member_admin_refresh_is_rejected_even_for_legacy_session(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, f"r2d-refresh-owner-{uuid.uuid4()}@example.com")
    member = _create_tenant_user(
        client,
        owner,
        email=f"r2d-refresh-member-{uuid.uuid4()}@example.com",
        role="member",
    )
    member_user = _get_user(test_session_local, member["id"])
    raw_refresh_token, _access_token = _create_legacy_admin_session(test_session_local, member_user)

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh_token, "portal": "admin"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_ADMIN_PORTAL_ROLE_REQUIRED"
    assert raw_refresh_token not in response.text


def test_member_cannot_mint_admin_tokens_through_2fa_verify_legacy_challenge(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, f"r2d-2fa-owner-{uuid.uuid4()}@example.com")
    member = _create_tenant_user(
        client,
        owner,
        email=f"r2d-2fa-member-{uuid.uuid4()}@example.com",
        role="member",
    )
    member_user = _get_user(test_session_local, member["id"])
    raw_challenge = _create_legacy_2fa_challenge(test_session_local, member_user)

    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"two_factor_challenge_token": raw_challenge, "code": "123456"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AUTH_2FA_INVALID"
    assert "access_token" not in response.text
    assert "refresh_token" not in response.text


def test_member_cannot_use_step_up_with_legacy_admin_session(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, f"r2d-stepup-owner-{uuid.uuid4()}@example.com")
    member = _create_tenant_user(
        client,
        owner,
        email=f"r2d-stepup-member-{uuid.uuid4()}@example.com",
        role="member",
    )
    member_user = _get_user(test_session_local, member["id"])
    _raw_refresh_token, access_token = _create_legacy_admin_session(test_session_local, member_user)

    response = client.post(
        "/api/v1/auth/2fa/step-up",
        json={"code": "123456"},
        headers=_auth(access_token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_ADMIN_PORTAL_ROLE_REQUIRED"


def test_employee_login_and_current_staff_creation_flow_still_work(
    client: TestClient,
) -> None:
    owner = _register_owner(client, f"r2d-staff-owner-{uuid.uuid4()}@example.com")
    store = _create_store(client, owner)
    member = _create_tenant_user(
        client,
        owner,
        email=f"r2d-staff-member-{uuid.uuid4()}@example.com",
        role="member",
    )

    staff_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": member["id"],
            "store_id": store["id"],
            "employee_username": "r2d-employee",
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": "R2d Employee",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(owner["access_token"]),
    )
    assert staff_response.status_code == 201, staff_response.text
    assert staff_response.json()["employee_account_id"]

    employee_login = client.post(
        "/api/v1/auth/employee/login",
        json={
            "site_id": store["id"],
            "username": "r2d-employee",
            "password": EMPLOYEE_PASSWORD,
        },
    )
    assert employee_login.status_code == 200, employee_login.text
    assert employee_login.json()["access_token"]
    assert employee_login.json()["employee_account"]["site_id"] == store["id"]


def test_company_profile_is_owner_only_defense_in_depth(
    client: TestClient,
    test_session_local,
) -> None:
    owner = _register_owner(client, f"r2d-company-owner-{uuid.uuid4()}@example.com")
    member = _create_tenant_user(
        client,
        owner,
        email=f"r2d-company-member-{uuid.uuid4()}@example.com",
        role="member",
    )
    member_user = _get_user(test_session_local, member["id"])
    _raw_refresh_token, member_access_token = _create_legacy_admin_session(test_session_local, member_user)

    member_get = client.get(
        "/api/v1/company/profile",
        headers=_auth(member_access_token),
    )
    assert member_get.status_code == 403
    assert member_get.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    member_patch = client.patch(
        "/api/v1/company/profile",
        json=_complete_company_payload(company_name="Member Mutation"),
        headers=_auth(member_access_token),
    )
    assert member_patch.status_code == 403
    assert member_patch.json()["error"]["code"] == "TENANT_ROLE_REQUIRED"

    owner_get = client.get(
        "/api/v1/company/profile",
        headers=_auth(owner["access_token"]),
    )
    assert owner_get.status_code == 200, owner_get.text

    owner_patch = client.patch(
        "/api/v1/company/profile",
        json=_complete_company_payload(company_name="Owner Mutation"),
        headers=_auth(owner["access_token"]),
    )
    assert owner_patch.status_code == 200, owner_patch.text
    assert owner_patch.json()["company_name"] == "Owner Mutation"
