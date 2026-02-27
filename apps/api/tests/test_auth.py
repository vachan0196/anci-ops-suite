from collections.abc import Generator
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.core.settings import settings


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_auth.db"
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


def test_register_creates_tenant_membership_and_sets_active_tenant(
    client: TestClient,
    test_session_local,
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    body = response.json()

    assert response.status_code == 201
    assert body["email"] == "owner@example.com"
    assert body["active_tenant_id"] is not None

    db = test_session_local()
    try:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert user is not None
        assert user.active_tenant_id is not None

        tenant = db.get(Tenant, user.active_tenant_id)
        assert tenant is not None
        assert tenant.name == "owner@example.com's tenant"

        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == user.active_tenant_id,
                TenantUser.user_id == user.id,
            )
        )
        assert membership is not None
        assert membership.role == "admin"
    finally:
        db.close()


def test_login_returns_access_token(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )
    body = login_response.json()

    assert login_response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_register_rejects_password_over_bcrypt_limit(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "long-pass@example.com", "password": "a" * 73},
    )
    body = response.json()

    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "72 bytes" in body["error"]["message"]
    assert "details" in body["error"]


def test_register_accepts_password_within_bcrypt_limit(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "limit-pass@example.com", "password": "a" * 72},
    )
    body = response.json()

    assert response.status_code == 201
    assert body["email"] == "limit-pass@example.com"


def test_me_returns_active_tenant_id(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "me@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = me_response.json()

    assert me_response.status_code == 200
    assert body["email"] == "me@example.com"
    assert body["active_tenant_id"] is not None


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED,
    reason="Rate limiting disabled for test run",
)
def test_login_rate_limit(client: TestClient) -> None:
    email = f"rate-login-{uuid.uuid4()}@example.com"
    password = "password123"
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201

    first_login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert first_login_response.status_code == 200

    saw_success = True
    hit_rate_limit = False

    for _ in range(30):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        if response.status_code == 200:
            saw_success = True
        if response.status_code == 429:
            hit_rate_limit = True
            break

    assert saw_success is True
    assert hit_rate_limit is True
