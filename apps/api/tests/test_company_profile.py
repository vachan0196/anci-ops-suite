from collections.abc import Generator
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.tenant import Tenant


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_company_profile.db"
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


def _register_and_login(client: TestClient, email: str, password: str = "password123") -> dict:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201
    register_body = register_response.json()

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200

    return {
        "id": uuid.UUID(register_body["id"]),
        "active_tenant_id": uuid.UUID(register_body["active_tenant_id"]),
        "token": login_response.json()["access_token"],
    }


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _complete_payload(**overrides) -> dict:
    payload = {
        "company_name": "Anci Group Limited",
        "owner_name": "Vachan Sardar",
        "business_email": "owner@example.com",
        "phone_number": "07123456789",
        "registered_address": "Test Address, UK",
    }
    payload.update(overrides)
    return payload


def test_unauthenticated_get_company_profile_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/company/profile")

    assert response.status_code == 401


def test_unauthenticated_patch_company_profile_is_rejected(client: TestClient) -> None:
    response = client.patch("/api/v1/company/profile", json=_complete_payload())

    assert response.status_code == 401


def test_authenticated_get_returns_active_tenant_profile(client: TestClient) -> None:
    user = _register_and_login(client, f"company-get-{uuid.uuid4()}@example.com")

    response = client.get(
        "/api/v1/company/profile",
        headers=_auth_headers(user["token"]),
    )
    body = response.json()

    assert response.status_code == 200
    assert uuid.UUID(body["tenant_id"]) == user["active_tenant_id"]
    assert body["company_name"] is None
    assert body["company_setup_completed"] is False
    assert body["company_setup_completed_at"] is None


def test_authenticated_patch_updates_company_profile(client: TestClient, test_session_local) -> None:
    user = _register_and_login(client, f"company-patch-{uuid.uuid4()}@example.com")

    response = client.patch(
        "/api/v1/company/profile",
        json=_complete_payload(company_name="  ForecourtOS Ltd  "),
        headers=_auth_headers(user["token"]),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["company_name"] == "ForecourtOS Ltd"
    assert body["owner_name"] == "Vachan Sardar"
    assert body["business_email"] == "owner@example.com"
    assert body["phone_number"] == "07123456789"
    assert body["registered_address"] == "Test Address, UK"
    assert body["company_setup_completed"] is True
    assert body["company_setup_completed_at"] is not None

    db = test_session_local()
    try:
        tenant = db.get(Tenant, user["active_tenant_id"])
        assert tenant is not None
        assert tenant.company_name == "ForecourtOS Ltd"
        assert tenant.company_setup_completed is True
    finally:
        db.close()


def test_patch_response_returns_updated_profile(client: TestClient) -> None:
    user = _register_and_login(client, f"company-response-{uuid.uuid4()}@example.com")

    response = client.patch(
        "/api/v1/company/profile",
        json=_complete_payload(owner_name="New Owner"),
        headers=_auth_headers(user["token"]),
    )
    body = response.json()

    assert response.status_code == 200
    assert uuid.UUID(body["tenant_id"]) == user["active_tenant_id"]
    assert body["owner_name"] == "New Owner"


def test_patch_rejects_tenant_id_override(client: TestClient, test_session_local) -> None:
    user = _register_and_login(client, f"company-override-{uuid.uuid4()}@example.com")
    other = _register_and_login(client, f"company-other-{uuid.uuid4()}@example.com")

    response = client.patch(
        "/api/v1/company/profile",
        json=_complete_payload(tenant_id=str(other["active_tenant_id"])),
        headers=_auth_headers(user["token"]),
    )

    assert response.status_code == 422

    db = test_session_local()
    try:
        user_tenant = db.get(Tenant, user["active_tenant_id"])
        other_tenant = db.get(Tenant, other["active_tenant_id"])
        assert user_tenant is not None
        assert other_tenant is not None
        assert user_tenant.company_name is None
        assert other_tenant.company_name is None
    finally:
        db.close()


def test_audit_log_created_on_successful_update(client: TestClient, test_session_local) -> None:
    user = _register_and_login(client, f"company-audit-{uuid.uuid4()}@example.com")

    response = client.patch(
        "/api/v1/company/profile",
        json=_complete_payload(),
        headers=_auth_headers(user["token"]),
    )

    assert response.status_code == 200

    db = test_session_local()
    try:
        audit_log = db.scalar(
            select(AuditLog).where(
                AuditLog.tenant_id == user["active_tenant_id"],
                AuditLog.user_id == user["id"],
                AuditLog.action == "company_profile.updated",
                AuditLog.entity_type == "tenant/company_profile",
                AuditLog.entity_id == str(user["active_tenant_id"]),
            )
        )
        assert audit_log is not None
    finally:
        db.close()


def test_tenant_a_cannot_update_tenant_b_profile(client: TestClient, test_session_local) -> None:
    tenant_a = _register_and_login(client, f"company-tenant-a-{uuid.uuid4()}@example.com")
    tenant_b = _register_and_login(client, f"company-tenant-b-{uuid.uuid4()}@example.com")

    response = client.patch(
        "/api/v1/company/profile",
        json=_complete_payload(tenant_id=str(tenant_b["active_tenant_id"])),
        headers=_auth_headers(tenant_a["token"]),
    )

    assert response.status_code == 422

    response = client.patch(
        "/api/v1/company/profile",
        json=_complete_payload(company_name="Tenant A Only"),
        headers=_auth_headers(tenant_a["token"]),
    )

    assert response.status_code == 200

    db = test_session_local()
    try:
        tenant_a_record = db.get(Tenant, tenant_a["active_tenant_id"])
        tenant_b_record = db.get(Tenant, tenant_b["active_tenant_id"])
        assert tenant_a_record is not None
        assert tenant_b_record is not None
        assert tenant_a_record.company_name == "Tenant A Only"
        assert tenant_b_record.company_name is None
    finally:
        db.close()
