from collections.abc import Generator, Iterable
from datetime import timedelta
import importlib
import json
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from apps.api.core.security import hash_refresh_token
from apps.api.core.settings import settings
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.auth_security_event import AuthSecurityEvent
from apps.api.models.auth_session import AuthSession
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.user import User
from apps.api.routers import auth as auth_router
from apps.api.routers.auth import _create_auth_session, _now


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"
CSRF_HEADERS = {"X-Requested-With": "ForecourtOS"}


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase_q3_3_session_family_reuse.db"
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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


def _register_and_login(client: TestClient, email: str) -> dict:
    registered = _register(client, email)
    logged_in = _login(client, email)
    return {
        "id": registered["id"],
        "active_tenant_id": registered["active_tenant_id"],
        "token": logged_in["access_token"],
        "refresh_token": logged_in["refresh_token"],
    }


def _create_store(client: TestClient, admin: dict, code: str) -> dict:
    response = client.post(
        "/api/v1/stores",
        json={"code": code, "name": f"Store {code}", "timezone": "Europe/London"},
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _create_tenant_member(client: TestClient, admin: dict, email: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Phase Q3.3 Staff",
            "role": "member",
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _create_staff_with_employee_account(
    client: TestClient,
    admin: dict,
    *,
    store_id: str,
    username: str,
) -> dict:
    user = _create_tenant_member(
        client,
        admin,
        f"phase-q3-3-{username}-{uuid.uuid4()}@example.com",
    )
    response = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"],
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": f"Phase Q3.3 {username}",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201
    return response.json()


def _create_employee_login(client: TestClient, *, site_id: str, username: str) -> dict:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={"site_id": site_id, "username": username, "password": EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()


def _create_admin_employee_context(client: TestClient) -> tuple[dict, dict, dict, dict]:
    admin = _register_and_login(client, f"phase-q3-3-admin-{uuid.uuid4()}@example.com")
    store = _create_store(client, admin, f"Q33-{uuid.uuid4()}")
    profile = _create_staff_with_employee_account(
        client,
        admin,
        store_id=store["id"],
        username="alex",
    )
    employee_login = _create_employee_login(client, site_id=store["id"], username="alex")
    return admin, store, profile, employee_login


def _session_by_token(db: Session, refresh_token: str) -> AuthSession:
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_refresh_token(refresh_token))
    )
    assert session is not None
    return session


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
        "employee_account_id": str(event.employee_account_id) if event.employee_account_id else None,
        "auth_session_id": str(event.auth_session_id) if event.auth_session_id else None,
        "request_id": event.request_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "metadata_json": event.metadata_json,
    }
    return json.dumps(values, sort_keys=True, default=str)


def _assert_no_secret_leakage(
    db: Session,
    events: Iterable[AuthSecurityEvent],
    *,
    raw_refresh_tokens: Iterable[str] = (),
    raw_access_tokens: Iterable[str] = (),
    passwords: Iterable[str] = (PASSWORD, EMPLOYEE_PASSWORD),
) -> None:
    token_hashes = db.scalars(select(AuthSession.token_hash)).all()
    forbidden_values = [
        *raw_refresh_tokens,
        *raw_access_tokens,
        *token_hashes,
        *passwords,
        "Bearer ",
        settings.AUTH_REFRESH_COOKIE_NAME,
        "Authorization",
    ]
    for event in events:
        payload = _event_payload(event)
        for value in forbidden_values:
            if value:
                assert value not in payload


def _assert_no_reuse_events(db: Session) -> None:
    assert _events(db, event_type="auth.session.reuse_detected") == []
    assert _events(db, event_type="auth.session.revoked_by_family_reuse") == []


def test_admin_login_creates_root_session_with_family(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-root-admin-{uuid.uuid4()}@example.com")

    with test_session_local() as db:
        session = _session_by_token(db, admin["refresh_token"])
        assert session.session_family_id is not None
        assert session.parent_session_id is None


def test_employee_login_creates_root_session_with_family(
    client: TestClient,
    test_session_local,
) -> None:
    _, _, _, employee_login = _create_admin_employee_context(client)

    with test_session_local() as db:
        session = _session_by_token(db, employee_login["refresh_token"])
        assert session.session_family_id is not None
        assert session.parent_session_id is None


def test_refresh_creates_same_family_child_with_parent(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-child-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 200
    with test_session_local() as db:
        parent = _session_by_token(db, admin["refresh_token"])
        child = _session_by_token(db, response.json()["refresh_token"])
        assert child.session_family_id == parent.session_family_id
        assert child.parent_session_id == parent.id
        assert parent.is_revoked is True


def test_reusing_rotated_token_revokes_family_and_logs_events(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-reuse-{uuid.uuid4()}@example.com")
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )
    assert rotated.status_code == 200

    reused = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert reused.status_code == 401
    assert admin["refresh_token"] not in reused.text
    with test_session_local() as db:
        sessions = list(db.scalars(select(AuthSession)).all())
        assert len(sessions) == 2
        assert all(session.is_revoked for session in sessions)
        parent = _session_by_token(db, admin["refresh_token"])
        assert parent.reuse_detected_at is not None
        assert len(_events(db, event_type="auth.session.reuse_detected")) == 1
        revoked_events = _events(db, event_type="auth.session.revoked_by_family_reuse")
        assert len(revoked_events) == 2
        assert all(event.metadata_json["family_id"] == str(parent.session_family_id) for event in revoked_events)
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"], rotated.json()["refresh_token"]],
            raw_access_tokens=[admin["token"], rotated.json()["access_token"]],
        )


def test_subsequent_family_revoked_refresh_logs_family_revoked(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-family-revoked-{uuid.uuid4()}@example.com")
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )
    assert rotated.status_code == 200
    assert client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    ).status_code == 401

    subsequent = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated.json()["refresh_token"], "portal": "admin"},
    )

    assert subsequent.status_code == 401
    with test_session_local() as db:
        family_revoked = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="family_revoked",
        )
        assert len(family_revoked) == 1
        assert family_revoked[0].auth_session_id is not None


def test_logout_revoked_token_does_not_trigger_reuse_detection(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-logout-{uuid.uuid4()}@example.com")
    logout = client.post("/api/v1/auth/logout", json={"refresh_token": admin["refresh_token"]})
    assert logout.status_code == 200

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.rejected", rejection_reason="revoked")) == 1
        _assert_no_reuse_events(db)


def test_expired_token_is_not_reuse_detected(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q3-3-expired-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        session = _session_by_token(db, admin["refresh_token"])
        session.expires_at = _now() - timedelta(minutes=1)
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.rejected", rejection_reason="expired")) == 1
        _assert_no_reuse_events(db)


def test_wrong_portal_is_not_reuse_detected(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q3-3-wrong-portal-{uuid.uuid4()}@example.com")

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.rejected", rejection_reason="wrong_portal")) == 1
        _assert_no_reuse_events(db)


def test_disabled_admin_is_not_reuse_detected(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"phase-q3-3-disabled-admin-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        user = db.get(User, uuid.UUID(admin["id"]))
        assert user is not None
        user.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 403
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.blocked_disabled_admin")) == 1
        _assert_no_reuse_events(db)


def test_disabled_employee_is_not_reuse_detected(client: TestClient, test_session_local) -> None:
    _, _, profile, employee_login = _create_admin_employee_context(client)
    with test_session_local() as db:
        account = db.get(EmployeeAccount, uuid.UUID(profile["employee_account_id"]))
        assert account is not None
        account.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_login["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 403
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.blocked_disabled_employee")) == 1
        _assert_no_reuse_events(db)


def test_inactive_staff_profile_is_not_reuse_detected(
    client: TestClient,
    test_session_local,
) -> None:
    _, _, profile, employee_login = _create_admin_employee_context(client)
    with test_session_local() as db:
        staff_profile = db.get(StaffProfile, uuid.UUID(profile["id"]))
        assert staff_profile is not None
        staff_profile.is_active = False
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": employee_login["refresh_token"], "portal": "employee"},
    )

    assert response.status_code == 403
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.blocked_inactive_staff_profile")) == 1
        _assert_no_reuse_events(db)


def test_independent_session_families_do_not_revoke_each_other(
    client: TestClient,
    test_session_local,
) -> None:
    first = _register_and_login(client, f"phase-q3-3-family-a-{uuid.uuid4()}@example.com")
    second = _register_and_login(client, f"phase-q3-3-family-b-{uuid.uuid4()}@example.com")
    first_rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"], "portal": "admin"},
    )
    assert first_rotated.status_code == 200
    assert client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"], "portal": "admin"},
    ).status_code == 401

    second_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second["refresh_token"], "portal": "admin"},
    )

    assert second_refresh.status_code == 200
    with test_session_local() as db:
        second_original = _session_by_token(db, second["refresh_token"])
        second_child = _session_by_token(db, second_refresh.json()["refresh_token"])
        assert second_child.session_family_id == second_original.session_family_id
        assert second_child.is_revoked is False


def test_concurrent_double_refresh_loser_does_not_create_child_or_reuse_event(
    client: TestClient,
    test_session_local,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-concurrent-{uuid.uuid4()}@example.com")
    original_find = auth_router._find_refresh_session

    def locked_find(db: Session, refresh_token: str, *, lock_for_update: bool = False):
        if lock_for_update and refresh_token == admin["refresh_token"]:
            raise OperationalError("SELECT auth_sessions", {}, Exception("row locked"))
        return original_find(db, refresh_token, lock_for_update=lock_for_update)

    monkeypatch.setattr(auth_router, "_find_refresh_session", locked_find)
    losing = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )
    monkeypatch.setattr(auth_router, "_find_refresh_session", original_find)

    winning = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert losing.status_code == 401
    assert winning.status_code == 200
    with test_session_local() as db:
        parent = _session_by_token(db, admin["refresh_token"])
        children = list(db.scalars(select(AuthSession).where(AuthSession.parent_session_id == parent.id)).all())
        assert len(children) == 1
        _assert_no_reuse_events(db)


def test_cookie_backed_refresh_still_requires_csrf_header(client: TestClient) -> None:
    _register_and_login(client, f"phase-q3-3-cookie-csrf-{uuid.uuid4()}@example.com")

    response = client.post("/api/v1/auth/refresh", json={"portal": "admin"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_CSRF_REQUIRED"


def test_missing_csrf_still_logs_missing_csrf_header(
    client: TestClient,
    test_session_local,
) -> None:
    _register_and_login(client, f"phase-q3-3-cookie-csrf-log-{uuid.uuid4()}@example.com")

    response = client.post("/api/v1/auth/refresh", json={"portal": "admin"})

    assert response.status_code == 403
    with test_session_local() as db:
        missing = _events(
            db,
            event_type="auth.session.rejected",
            rejection_reason="missing_csrf_header",
        )
        assert len(missing) == 1
        assert missing[0].metadata_json == {"cookie_backed": True}


def test_security_events_and_business_audit_logs_do_not_contain_secrets(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-leakage-{uuid.uuid4()}@example.com")
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )
    assert rotated.status_code == 200
    assert client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    ).status_code == 401

    with test_session_local() as db:
        _assert_no_secret_leakage(
            db,
            _events(db),
            raw_refresh_tokens=[admin["refresh_token"], rotated.json()["refresh_token"]],
            raw_access_tokens=[admin["token"], rotated.json()["access_token"]],
        )
        audit_payloads = [
            json.dumps(
                {
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": log.entity_id,
                },
                sort_keys=True,
            )
            for log in db.scalars(select(AuditLog)).all()
        ]
        forbidden = [
            admin["refresh_token"],
            rotated.json()["refresh_token"],
            admin["token"],
            rotated.json()["access_token"],
            *db.scalars(select(AuthSession.token_hash)).all(),
            PASSWORD,
            "Bearer ",
            settings.AUTH_REFRESH_COOKIE_NAME,
        ]
        for payload in audit_payloads:
            for value in forbidden:
                assert value not in payload


def test_migration_revokes_existing_active_sessions_without_fake_family_ids(tmp_path) -> None:
    migration = importlib.import_module(
        "apps.api.alembic.versions.0024_phase_q3_3_session_family"
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE auth_sessions ("
                "id CHAR(32) PRIMARY KEY, "
                "is_revoked BOOLEAN NOT NULL, "
                "revoked_at DATETIME NULL"
                ")"
            )
        )
        connection.execute(
            text("INSERT INTO auth_sessions (id, is_revoked, revoked_at) VALUES (:id, 0, NULL)"),
            {"id": uuid.uuid4().hex},
        )

        class FakeOp:
            def add_column(self, table_name, column):
                compiled_type = column.type.compile(dialect=sqlite.dialect())
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} {compiled_type}")
                )

            def create_foreign_key(self, *args, **kwargs):
                return None

            def drop_constraint(self, *args, **kwargs):
                return None

            def create_check_constraint(self, *args, **kwargs):
                return None

            def create_index(self, name, table_name, columns, unique=False):
                unique_sql = "UNIQUE " if unique else ""
                connection.execute(
                    text(f"CREATE {unique_sql}INDEX {name} ON {table_name} ({', '.join(columns)})")
                )

            def execute(self, statement):
                connection.execute(statement)

        original_op = migration.op
        migration.op = FakeOp()
        try:
            migration.upgrade()
        finally:
            migration.op = original_op

        row = connection.execute(
            text(
                "SELECT is_revoked, revoked_at, session_family_id, parent_session_id, reuse_detected_at "
                "FROM auth_sessions"
            )
        ).mappings().one()
        assert row["is_revoked"] in {1, True}
        assert row["revoked_at"] is not None
        assert row["session_family_id"] is None
        assert row["parent_session_id"] is None
        assert row["reuse_detected_at"] is None


def test_null_family_revoked_session_returns_revoked_without_reuse_detection(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, f"phase-q3-3-null-family-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        session = _session_by_token(db, admin["refresh_token"])
        session.session_family_id = None
        session.is_revoked = True
        session.revoked_at = _now()
        db.commit()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": admin["refresh_token"], "portal": "admin"},
    )

    assert response.status_code == 401
    with test_session_local() as db:
        assert len(_events(db, event_type="auth.session.rejected", rejection_reason="revoked")) == 1
        _assert_no_reuse_events(db)


def test_create_auth_session_without_required_family_id_raises(
    client: TestClient,
    test_session_local,
) -> None:
    _register_and_login(client, f"phase-q3-3-helper-{uuid.uuid4()}@example.com")
    with test_session_local() as db:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/auth/login",
                "headers": [],
                "client": ("testclient", 50000),
            }
        )
        with pytest.raises(ValueError, match="session_family_id"):
            _create_auth_session(
                db,
                request=request,
                portal="admin",
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )
