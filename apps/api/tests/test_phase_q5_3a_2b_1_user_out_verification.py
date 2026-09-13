from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.user import User
from apps.api.routers.auth import _as_aware
from apps.api.tests.auth_session_support import employee_token


PASSWORD = "password123"


@pytest.fixture(scope="module")
def migrated_sessions():
    database_url = make_url(os.environ["DATABASE_URL"])
    assert database_url.get_backend_name() == "postgresql", "Run these integration tests with Compose"
    schema = "q532b1_" + uuid.uuid4().hex
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


def _register(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"q532b1-{uuid.uuid4().hex}@example.com", "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def _login(client, user):
    response = client.post(
        "/api/v1/auth/login", data={"username": user["email"], "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _me(client, token):
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()


def _verification_time():
    return datetime.combine(
        date.today() - timedelta(days=3), time(7, 23, 41, 123456), tzinfo=timezone.utc,
    )


def _set_verified(sessions, user, timestamp):
    with sessions() as db:
        stored_user = db.get(User, uuid.UUID(user["id"]))
        assert stored_user is not None
        stored_user.email_verified_at = timestamp
        db.commit()


def test_t1_unverified_admin_me_has_explicit_null(client):
    user = _register(client)
    body = _me(client, _login(client, user))
    assert "email_verified_at" in body
    assert body["email_verified_at"] is None


def test_t2_verified_admin_me_preserves_exact_timestamp(client, migrated_sessions):
    user = _register(client)
    timestamp = _verification_time()
    _set_verified(migrated_sessions, user, timestamp)
    body = _me(client, _login(client, user))
    parsed = datetime.fromisoformat(body["email_verified_at"])
    assert parsed.utcoffset() is not None
    assert _as_aware(parsed) == timestamp


def test_t3_me_returns_each_users_own_verification_state(client, migrated_sessions):
    verified = _register(client)
    unverified = _register(client)
    timestamp = _verification_time()
    _set_verified(migrated_sessions, verified, timestamp)
    verified_token = _login(client, verified)
    unverified_token = _login(client, unverified)
    verified_body = _me(client, verified_token)
    unverified_body = _me(client, unverified_token)
    assert verified_body["id"] == verified["id"]
    assert unverified_body["id"] == unverified["id"]
    assert verified_body["email_verified_at"] != unverified_body["email_verified_at"]
    assert _as_aware(datetime.fromisoformat(verified_body["email_verified_at"])) == timestamp
    assert unverified_body["email_verified_at"] is None


def test_t4_registration_returns_explicit_null(client):
    body = _register(client)
    assert "email_verified_at" in body
    assert body["email_verified_at"] is None


def test_t5_employee_me_has_no_verification_field(client):
    token = employee_token(client)
    body = _me(client, token)
    response = client.get(
        "/api/v1/auth/employee/me", headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert body == response.json()
    assert body["portal"] == "employee"
    assert "email_verified_at" not in body


def test_t6_verification_timestamp_is_aware_and_round_trips(client, migrated_sessions):
    user = _register(client)
    timestamp = _verification_time().astimezone(timezone(timedelta(hours=5, minutes=30)))
    _set_verified(migrated_sessions, user, timestamp)
    body = _me(client, _login(client, user))
    verified_at = datetime.fromisoformat(body["email_verified_at"])
    created_at = datetime.fromisoformat(body["created_at"])
    assert verified_at.utcoffset() is not None
    assert created_at.utcoffset() is not None
    with migrated_sessions() as db:
        stored_user = db.get(User, uuid.UUID(user["id"]))
        assert _as_aware(verified_at) == _as_aware(stored_user.email_verified_at) == timestamp
        assert _as_aware(created_at) == _as_aware(stored_user.created_at)
    assert datetime.fromisoformat(verified_at.isoformat()) == timestamp
