from datetime import date, datetime, time, timezone
import inspect
import json
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect as sqlalchemy_inspect, select

from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.routers import auth
from apps.api.tests.auth_session_support import current_refresh_token, use_refresh_cookie
from apps.api.tests.test_phase_q5_3a_1_local_email import migrated_sessions


PASSWORD = "h069-cookie-only-password"
EMPLOYEE_PASSWORD = "h069-employee-password"


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


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _register_and_login(client: TestClient) -> tuple[dict, object]:
    email = f"h069-{uuid.uuid4().hex}@example.com"
    registered = client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registered.status_code == 201, registered.text
    response = client.post(
        "/api/v1/auth/login", data={"username": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {
        **registered.json(),
        "access_token": response.json()["access_token"],
        "refresh_token": current_refresh_token(client),
    }, response


def _employee_login(client: TestClient) -> tuple[dict, object]:
    admin, _ = _register_and_login(client)
    employee_username = f"h069-{uuid.uuid4().hex}"
    store = client.post(
        "/api/v1/stores",
        headers=_auth(admin["access_token"]),
        json={"name": f"H069 store {uuid.uuid4().hex}"},
    )
    assert store.status_code == 201, store.text
    staff = client.post(
        "/api/v1/staff",
        headers=_auth(admin["access_token"]),
        json={
            "user_id": admin["id"],
            "store_id": store.json()["id"],
            "display_name": "H069 employee",
            "employee_username": employee_username,
            "employee_password": EMPLOYEE_PASSWORD,
            "is_active": True,
        },
    )
    assert staff.status_code == 201, staff.text
    response = client.post(
        "/api/v1/auth/employee/login",
        json={
            "site_id": store.json()["id"],
            "username": employee_username,
            "password": EMPLOYEE_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return {
        "access_token": response.json()["access_token"],
        "refresh_token": current_refresh_token(client),
    }, response


def _session_snapshot(migrated_sessions) -> list[dict]:
    columns = [attribute.key for attribute in sqlalchemy_inspect(AuthSession).column_attrs]
    with migrated_sessions() as db:
        rows = db.scalars(select(AuthSession).order_by(AuthSession.id)).all()
        return [
            {
                key: (
                    value.isoformat()
                    if isinstance(value, (date, datetime, time))
                    else str(value)
                    if isinstance(value, uuid.UUID)
                    else value
                )
                for key in columns
                for value in [getattr(row, key)]
            }
            for row in rows
        ]


def _stored_payloads(migrated_sessions) -> str:
    with migrated_sessions() as db:
        rows = [
            *db.scalars(select(AuditLog)).all(),
            *db.scalars(select(AuthSecurityEvent)).all(),
        ]
        payloads = []
        for row in rows:
            columns = sqlalchemy_inspect(type(row)).column_attrs
            payloads.append({column.key: str(getattr(row, column.key)) for column in columns})
        return json.dumps(payloads, sort_keys=True)


@pytest.mark.parametrize("portal", ["admin", "employee"])
def test_cookie_lifecycle_works_without_response_body_credentials(
    portal, client, migrated_sessions, caplog
) -> None:
    caplog.set_level(1)
    principal, login_response = (
        _register_and_login(client) if portal == "admin" else _employee_login(client)
    )
    original_refresh = principal["refresh_token"]
    assert "refresh_token" not in login_response.json()
    assert original_refresh not in login_response.text

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"portal": portal},
        headers=use_refresh_cookie(client, original_refresh),
    )
    assert refresh_response.status_code == 200, refresh_response.text
    rotated_refresh = current_refresh_token(client)
    assert rotated_refresh != original_refresh
    assert "refresh_token" not in refresh_response.json()
    assert original_refresh not in refresh_response.text
    assert rotated_refresh not in refresh_response.text

    with migrated_sessions() as db:
        original = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == auth.hash_refresh_token(original_refresh))
        )
        rotated = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == auth.hash_refresh_token(rotated_refresh))
        )
        assert original is not None and original.is_revoked is True
        assert rotated is not None and rotated.is_revoked is False
        assert rotated.parent_session_id == original.id
        assert rotated.session_family_id == original.session_family_id

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={},
        headers=use_refresh_cookie(client, rotated_refresh),
    )
    assert logout_response.status_code == 200, logout_response.text
    assert logout_response.json() == {"revoked": True}
    with migrated_sessions() as db:
        rotated = db.scalar(
            select(AuthSession).where(AuthSession.token_hash == auth.hash_refresh_token(rotated_refresh))
        )
        assert rotated is not None and rotated.is_revoked is True

    combined_logs = "\n".join(record.getMessage() for record in caplog.records)
    stored = _stored_payloads(migrated_sessions)
    for token in (original_refresh, rotated_refresh):
        assert token not in combined_logs
        assert token not in stored


@pytest.mark.parametrize("path", ["/api/v1/auth/refresh", "/api/v1/auth/logout"])
@pytest.mark.parametrize("cookie_state", ["absent", "invalid"])
def test_body_token_cannot_authenticate_or_select_a_session_for_revocation(
    path, cookie_state, client, migrated_sessions
) -> None:
    admin, _ = _register_and_login(client)
    before = _session_snapshot(migrated_sessions)
    client.cookies.clear()
    if cookie_state == "invalid":
        use_refresh_cookie(client, f"invalid-cookie-{uuid.uuid4().hex}")
    body = {"refresh_token": admin["refresh_token"]}
    if path.endswith("/refresh"):
        body["portal"] = "admin"

    response = client.post(path, json=body, headers={"X-Requested-With": "ForecourtOS"})

    assert response.status_code == 422, response.text
    assert admin["refresh_token"] not in response.text
    assert _session_snapshot(migrated_sessions) == before


@pytest.mark.parametrize("path", ["/api/v1/auth/refresh", "/api/v1/auth/logout"])
@pytest.mark.parametrize("body_value", [None, "", "valid"])
def test_body_input_cannot_bypass_csrf_or_change_session_state(
    path, body_value, client, migrated_sessions
) -> None:
    admin, _ = _register_and_login(client)
    before = _session_snapshot(migrated_sessions)
    body = {
        "refresh_token": (
            admin["refresh_token"] if body_value == "valid" else body_value
        )
    }
    if path.endswith("/refresh"):
        body["portal"] = "admin"

    response = client.post(path, json=body)

    assert response.status_code == 422, response.text
    assert _session_snapshot(migrated_sessions) == before


@pytest.mark.parametrize("path", ["/api/v1/auth/refresh", "/api/v1/auth/logout"])
def test_missing_csrf_header_without_body_credential_has_no_side_effect(
    path, client, migrated_sessions
) -> None:
    _register_and_login(client)
    before = _session_snapshot(migrated_sessions)
    body = {"portal": "admin"} if path.endswith("/refresh") else {}

    response = client.post(path, json=body)

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTH_CSRF_REQUIRED"
    assert _session_snapshot(migrated_sessions) == before


def test_refresh_selector_has_only_the_cookie_request_input() -> None:
    assert tuple(inspect.signature(auth._get_refresh_token_from_request).parameters) == (
        "request",
    )
    source = inspect.getsource(auth._get_refresh_token_from_request)
    assert "request.cookies.get" in source
    assert "payload" not in source


@pytest.mark.parametrize("path", ["/api/v1/auth/refresh", "/api/v1/auth/logout"])
def test_refresh_marker_is_absent_from_every_response_log_and_storage_sink(
    path, client, migrated_sessions, caplog
) -> None:
    caplog.set_level(1)
    marker = f"h069-distinctive-marker-{uuid.uuid4().hex}"
    client.cookies.clear()

    body = {"refresh_token": marker}
    if path.endswith("/refresh"):
        body["portal"] = "admin"
    response = client.post(path, json=body)

    assert response.status_code == 422
    assert marker not in json.dumps(response.json(), sort_keys=True)
    assert marker not in "\n".join(record.getMessage() for record in caplog.records)
    assert marker not in _stored_payloads(migrated_sessions)


def test_ordinary_validation_responses_match_the_e9716b1_baseline(client) -> None:
    expected = [
        (
            "/api/v1/public/sites/lookup",
            {},
            {
                "loc": ["query", "code"],
                "msg": "Field required",
                "type": "missing",
                "input": None,
            },
        ),
        (
            "/api/v1/hot-food/forecast",
            {"store_id": "unused", "horizon_days": "invalid"},
            {
                "loc": ["query", "horizon_days"],
                "msg": "Input should be a valid integer, unable to parse string as an integer",
                "type": "int_parsing",
                "input": "invalid",
            },
        ),
    ]
    for path, params, detail in expected:
        response = client.get(path, params=params)
        assert response.status_code == 422
        body = response.json()["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["details"] == [detail]
        assert detail["msg"] in body["message"]
        assert repr(detail["input"]) in body["message"]
        assert repr(tuple(detail["loc"])) in body["message"]
