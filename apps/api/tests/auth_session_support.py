"""Explicit persisted-session fixtures for tests that bypass normal login."""
from datetime import date, datetime, time, timedelta, timezone
import uuid

from apps.api.core.security import create_access_token, create_refresh_token, hash_refresh_token
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_session import AuthSession
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.user import User

CSRF_HEADERS = {"X-Requested-With": "ForecourtOS"}


def current_refresh_token(client) -> str:
    token = client.cookies.get(
        settings.AUTH_REFRESH_COOKIE_NAME,
        domain="testserver.local",
        path="/api/v1/auth",
    )
    assert token is not None
    return token


def issued_refresh_token(response, client, *, previous: str | None = None) -> str:
    # HTTPX builds response.cookies from this response's Set-Cookie headers.
    token = response.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    assert token
    if previous is not None:
        assert token != previous
    assert current_refresh_token(client) == token
    return token


def use_refresh_cookie(client, token: str) -> dict[str, str]:
    client.cookies.set(
        settings.AUTH_REFRESH_COOKIE_NAME,
        token,
        domain="testserver.local",
        path="/api/v1/auth",
    )
    return CSRF_HEADERS


def session_token(client, subject: str) -> str:
    # Use the calling test's database override; never the development database.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        employee = subject.startswith('employee:')
        principal_id = uuid.UUID(subject.removeprefix('employee:'))
        principal = db.get(EmployeeAccount if employee else User, principal_id)
        assert principal is not None
        session = AuthSession(
            portal='employee' if employee else 'admin',
            tenant_id=principal.tenant_id if employee else principal.active_tenant_id,
            user_id=None if employee else principal.id,
            employee_account_id=principal.id if employee else None,
            token_hash=hash_refresh_token(create_refresh_token()),
            session_family_id=uuid.uuid4(), is_revoked=False,
            expires_at=datetime.combine(date.today() + timedelta(days=14), time.min, tzinfo=timezone.utc),
        )
        db.add(session)
        db.flush()
        token = create_access_token(subject, auth_session_id=str(session.id))
        db.commit()
        return token
    finally:
        generator.close()


def employee_token(client) -> str:
    password = 'session-fixture-password'
    email = f'session-fixture-{uuid.uuid4().hex}@example.com'
    response = client.post('/api/v1/auth/register', json={'email': email, 'password': password})
    assert response.status_code == 201, response.text
    owner_id = response.json()['id']
    login = client.post('/api/v1/auth/login', data={'username':email, 'password':password})
    assert login.status_code == 200, login.text
    headers = {'Authorization':f"Bearer {login.json()['access_token']}"}
    store = client.post('/api/v1/stores', headers=headers, json={'name':'Session fixture store'})
    assert store.status_code == 201, store.text
    staff = client.post('/api/v1/staff', headers=headers, json={
        'user_id':owner_id, 'store_id':store.json()['id'], 'display_name':'Session fixture employee',
        'employee_username':'session-fixture', 'employee_password':password, 'is_active':True,
    })
    assert staff.status_code == 201, staff.text
    login = client.post('/api/v1/auth/employee/login', json={
        'site_id':store.json()['id'], 'username':'session-fixture', 'password':password,
    })
    assert login.status_code == 200, login.text
    return login.json()['access_token']
