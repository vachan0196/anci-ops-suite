from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from jose import jwt
import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from fastapi.routing import APIRoute

from apps.api.core import deps
from apps.api.core.security import decode_access_token_payload
from apps.api.core.settings import settings
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.auth_session import AuthSession
from apps.api.models.employee_account import EmployeeAccount
from apps.api.models.user import User
from apps.api.routers import auth
from apps.api.tests.auth_session_support import employee_token, session_token
from apps.api.tests.test_phase_q5_3a_1_local_email import migrated_sessions

SECURITY = json.loads((Path(__file__).parent / 'fixtures/d067_security_e9716b1.json').read_text())
PASSWORD = 'd067-test-password'


@pytest.fixture(scope='module')
def principals(migrated_sessions):
    def override():
        with migrated_sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            email = f'd067-{uuid.uuid4().hex}@example.com'
            response = client.post('/api/v1/auth/register', json={'email':email,'password':PASSWORD})
            assert response.status_code == 201
            admin_id = response.json()['id']
            employee = employee_token(client)
            employee_id = decode_access_token_payload(employee)['sub'].removeprefix('employee:')
            return {'admin':admin_id,'employee':employee_id,'email':email}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(principals, migrated_sessions):
    def override():
        with migrated_sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _subject(principals, portal):
    return ('employee:' if portal == 'employee' else '') + principals[portal]


def _token(client, principals, portal='admin'):
    return session_token(client, _subject(principals, portal))


def _headers(token):
    return {'Authorization':f'Bearer {token}'}


def _portal(path):
    return 'employee' if path == '/api/v1/auth/employee/me' or path.startswith((
        '/api/v1/employee/rota/my', '/api/v1/employee/me/availability',
        '/api/v1/employee/me/request', '/api/v1/employee/me/inbound-requests',
    )) else 'admin'


def _sample(schema):
    if 'anyOf' in schema:
        return _sample(next(s for s in schema['anyOf'] if s.get('type') != 'null'))
    if 'enum' in schema:
        return schema['enum'][0]
    if schema.get('format') == 'uuid':
        return str(uuid.uuid4())
    if schema.get('format') == 'date':
        today = date.today()
        return (today - timedelta(days=today.weekday()) + timedelta(days=7)).isoformat()
    if schema.get('type') in {'integer','number'}:
        return max(1, schema.get('minimum', 1))
    if schema.get('type') == 'boolean':
        return False
    return 'fixture'


def _operation_request(operation):
    method, path = operation.split(' ', 1)
    definition = app.openapi()['paths'][path][method.lower()]
    params = {}
    for parameter in definition.get('parameters', []):
        if parameter['in'] == 'path':
            path = path.replace('{'+parameter['name']+'}', str(_sample(parameter['schema'])))
        elif parameter['in'] == 'query' and parameter.get('required'):
            params[parameter['name']] = _sample(parameter['schema'])
    body = {'code':'123456'} if path.endswith('/2fa/step-up') else None
    return method, path, {'params':params, **({'json':body} if body is not None else {})}


def test_security_declarations_are_identical():
    methods = {'get','post','put','patch','delete','head','options','trace'}
    app.openapi_schema = None
    schema = app.openapi()
    actual = {f'{m.upper()} {p}':op.get('security') for p,item in schema['paths'].items() for m,op in item.items() if m in methods}
    assert actual == SECURITY
    assert len(actual) == 112
    assert sum(bool(value) for value in actual.values()) == 100


def _dependency_calls(dependant):
    yield dependant.call
    for child in dependant.dependencies:
        yield from _dependency_calls(child)


def test_every_secured_operation_has_mandatory_oauth_root():
    secured = {operation for operation, declaration in SECURITY.items() if declaration}
    routes = {}
    for route in app.routes:
        effective_routes = (
            [route]
            if isinstance(route, APIRoute)
            else list(route.effective_route_contexts())
            if hasattr(route, "effective_route_contexts")
            else []
        )
        for effective_route in effective_routes:
            for method in effective_route.methods:
                operation = f"{method} {effective_route.path}"
                if operation in secured:
                    routes[operation] = effective_route
    assert set(routes) == secured
    assert deps.oauth2_scheme.auto_error is True
    for operation, route in routes.items():
        roots = [
            call
            for call in _dependency_calls(route.dependant)
            if call is deps.oauth2_scheme
        ]
        assert roots, operation
        assert all(root.auto_error is True for root in roots), operation


@pytest.mark.parametrize('operation', [key for key,value in SECURITY.items() if value])
def test_every_secured_operation_rejects_revoked_session(operation, client, principals, migrated_sessions):
    portal = _portal(operation.split(' ',1)[1])
    token = _token(client, principals, portal)
    sid = uuid.UUID(decode_access_token_payload(token)['sid'])
    with migrated_sessions() as db:
        session = db.get(AuthSession, sid)
        session.is_revoked = True
        session.revoked_at = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
        db.commit()
    method,path,kwargs = _operation_request(operation)
    response = client.request(method,path,headers=_headers(token),**kwargs)
    assert response.status_code == 401, (operation,response.status_code,response.text)
    assert response.json()['error']['code'] == 'AUTH_INVALID_TOKEN', (operation,response.text)


@pytest.mark.parametrize('operation', [key for key,value in SECURITY.items() if value])
def test_every_secured_operation_requires_authentication(operation, client):
    method,path,kwargs = _operation_request(operation)
    response = client.request(method,path,**kwargs)
    assert response.status_code == 401, (operation,response.status_code,response.text)


ENTRY_REQUESTS = [
    ('user','GET','/api/v1/hot-food/demand-inputs?store_id=fixture',None,'admin'),
    ('employee','GET','/api/v1/auth/employee/me',None,'employee'),
    ('admin_2fa','GET','/api/v1/auth/2fa/status',None,'admin'),
    ('me_admin','GET','/api/v1/auth/me',None,'admin'),
    ('me_employee','GET','/api/v1/auth/me',None,'employee'),
    ('verification','POST','/api/v1/auth/email-verification/request',None,'admin'),
    ('sensitive','POST','/api/v1/stores/{id}/deactivate',None,'admin'),
    ('step_up','POST','/api/v1/auth/2fa/step-up',{'code':'123456'},'admin'),
]


def _entry_request(client, entry, token):
    _,method,path,body,_ = entry
    return client.request(method,path.replace('{id}',str(uuid.uuid4())),headers=_headers(token),**({'json':body} if body else {}))


@pytest.mark.parametrize('entry', ENTRY_REQUESTS, ids=lambda e:e[0])
@pytest.mark.parametrize('failure', ['missing_sid','integer_sid','list_sid','object_sid','malformed_sid','missing_row','revoked','expired','portal','subject'])
def test_session_conditions_at_each_authentication_path(entry, failure, client, principals, migrated_sessions):
    token = _token(client, principals, entry[-1])
    payload = decode_access_token_payload(token)
    if failure.endswith('_sid'):
        replacements = {'integer_sid':1,'list_sid':[],'object_sid':{},'malformed_sid':'not-a-uuid'}
        if failure == 'missing_sid':
            del payload['sid']
        else:
            payload['sid'] = replacements[failure]
    elif failure == 'missing_row':
        payload['sid'] = str(uuid.uuid4())
    else:
        with migrated_sessions() as db:
            session = db.get(AuthSession,uuid.UUID(payload['sid']))
            if failure == 'revoked':
                session.is_revoked = True
            elif failure == 'expired':
                session.expires_at = datetime.combine(date.today()-timedelta(days=1),time.min,tzinfo=timezone.utc)
            elif failure == 'portal':
                session.portal = 'employee' if entry[-1] == 'admin' else 'admin'
            else:
                # Keep all FK bindings valid; wrong subject is a different existing principal.
                if entry[-1] == 'admin':
                    session.user_id = None
                else:
                    session.employee_account_id = None
            db.commit()
    token = jwt.encode(payload,settings.JWT_SECRET_KEY,algorithm=settings.JWT_ALGORITHM)
    response = _entry_request(client,entry,token)
    assert response.status_code == 401, response.text
    assert response.json()['error']['code'] == 'AUTH_INVALID_TOKEN'


@pytest.mark.parametrize('entry', ENTRY_REQUESTS, ids=lambda e:e[0])
@pytest.mark.parametrize('claim', ['exp','iat','nbf'])
@pytest.mark.parametrize('value', [None,[],{}])
def test_malformed_time_claims(entry,claim,value,client,principals):
    payload = decode_access_token_payload(_token(client,principals,entry[-1]))
    payload[claim] = value
    token = jwt.encode(payload,settings.JWT_SECRET_KEY,algorithm=settings.JWT_ALGORITHM)
    response = _entry_request(client,entry,token)
    assert response.status_code == 401, response.text
    assert response.json()['error']['code'] == 'AUTH_INVALID_TOKEN'


@pytest.mark.parametrize('portal', ['admin','employee'])
def test_valid_session_authenticates(client,principals,portal):
    response = client.get('/api/v1/auth/me',headers=_headers(_token(client,principals,portal)))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize('dependency',[deps.get_current_tenant_id,deps.require_tenant_member,deps.require_tenant_role()])
def test_chaining_dependencies_inherit_revocation(dependency,client,principals,migrated_sessions):
    # A temporary route invokes the actual post-change dependency object.
    from fastapi import Depends, FastAPI
    from apps.api.core.errors import register_exception_handlers
    probe = FastAPI()
    register_exception_handlers(probe)
    @probe.get('/probe')
    def endpoint(membership=Depends(dependency)):
        return {'reached':True}
    probe.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    token = _token(client,principals)
    with migrated_sessions() as db:
        db.get(AuthSession,uuid.UUID(decode_access_token_payload(token)['sid'])).is_revoked = True
        db.commit()
    with TestClient(probe) as test_client:
        response = test_client.get('/probe',headers=_headers(token))
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'AUTH_INVALID_TOKEN'


@pytest.mark.parametrize('entry',ENTRY_REQUESTS,ids=lambda e:e[0])
def test_tenant_drift_differential_and_post_validation_reach(entry,client,principals,migrated_sessions,monkeypatch):
    token = _token(client,principals,entry[-1])
    sid = uuid.UUID(decode_access_token_payload(token)['sid'])
    reached = []
    original = deps.validate_access_session
    existing = deps.get_current_admin_user_and_session
    def record_new(*args,**kwargs):
        result = original(*args,**kwargs)
        reached.append(result.id)
        return result
    def record_existing(*args,**kwargs):
        result = existing(*args,**kwargs)
        reached.append(result[1].id)
        return result
    monkeypatch.setattr(deps,'validate_access_session',record_new)
    monkeypatch.setattr(auth,'validate_access_session',record_new)
    monkeypatch.setattr(deps,'get_current_admin_user_and_session',record_existing)
    monkeypatch.setattr(auth,'get_current_admin_user_and_session',record_existing)
    control = _entry_request(client,entry,token)
    assert reached == [sid], (entry,control.text)
    reached.clear()
    with migrated_sessions() as db:
        db.get(AuthSession,sid).tenant_id = None
        db.commit()
    subject = _entry_request(client,entry,token)
    if entry[0] in {'sensitive','step_up'}:
        assert reached == []
        assert control.status_code == 403
        assert subject.status_code == 401
        assert subject.json()['error']['code'] == 'AUTH_INVALID_TOKEN'
    else:
        assert reached == [sid], (entry,subject.text)
        assert (subject.status_code,subject.json()) == (control.status_code,control.json())


@pytest.mark.parametrize('entry',ENTRY_REQUESTS,ids=lambda e:e[0])
def test_one_primary_key_session_read_per_authentication_path(entry,client,principals,migrated_sessions):
    token = _token(client,principals,entry[-1])
    statements = []
    engine = migrated_sessions.kw['bind']
    def record(connection,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'FROM auth_sessions' in statement:
            statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:
        response = _entry_request(client,entry,token)
    finally:
        event.remove(engine,'before_cursor_execute',record)
    assert response.status_code in {200,202,403}, response.text
    assert len(statements) == 1, statements
    predicate = statements[0].split('WHERE',1)[1]
    assert 'auth_sessions.id =' in predicate
    assert 'tenant_id' not in predicate


@pytest.mark.parametrize('entry',ENTRY_REQUESTS,ids=lambda e:e[0])
def test_inactive_principal_check_is_preserved(entry,client,principals,migrated_sessions):
    portal = entry[-1]
    token = _token(client,principals,portal)
    model = User if portal == 'admin' else EmployeeAccount
    principal_id = uuid.UUID(principals[portal])
    with migrated_sessions() as db:
        db.get(model,principal_id).is_active = False
        db.commit()
    try:
        response = _entry_request(client,entry,token)
        assert response.status_code == 403, response.text
        assert response.json()['error']['code'] == ('AUTH_USER_INACTIVE' if portal == 'admin' else 'AUTH_EMPLOYEE_INACTIVE')
    finally:
        with migrated_sessions() as db:
            db.get(model,principal_id).is_active = True
            db.commit()


@pytest.mark.parametrize('portal', ['admin','employee'])
def test_deleted_principal_check_is_preserved(
    portal,client,principals,migrated_sessions,monkeypatch
):
    token = _token(client,principals,portal)
    payload = decode_access_token_payload(token)
    sid = uuid.UUID(payload['sid'])
    principal_id = uuid.UUID(principals[portal])
    model = User if portal == 'admin' else EmployeeAccount
    with migrated_sessions() as db:
        auth_session = db.get(AuthSession,sid)
        assert auth_session is not None
        assert auth_session.portal == portal
        assert auth_session.is_revoked is False
        assert auth_session.expires_at > datetime.now(timezone.utc)
        assert (
            auth_session.user_id if portal == 'admin' else auth_session.employee_account_id
        ) == principal_id

    original_get = Session.get
    def missing_principal(self,entity,ident,*args,**kwargs):
        if entity is model and uuid.UUID(str(ident)) == principal_id:
            return None
        return original_get(self,entity,ident,*args,**kwargs)
    monkeypatch.setattr(Session,'get',missing_principal)

    path = '/api/v1/auth/me' if portal == 'admin' else '/api/v1/auth/employee/me'
    response = client.get(path,headers=_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()['error']['code'] == (
        'AUTH_USER_NOT_FOUND' if portal == 'admin' else 'AUTH_EMPLOYEE_NOT_FOUND'
    )


@pytest.mark.parametrize('path',[
    '/api/v1/auth/2fa/status','/api/v1/auth/2fa/totp/enrol/begin',
    '/api/v1/auth/2fa/totp/enrol/confirm','/api/v1/auth/2fa/disable',
    '/api/v1/auth/2fa/recovery-codes/regenerate',
])
def test_all_five_2fa_endpoints_reject_revoked_session(path,client,principals,migrated_sessions):
    token = _token(client,principals)
    with migrated_sessions() as db:
        db.get(AuthSession,uuid.UUID(decode_access_token_payload(token)['sid'])).is_revoked = True
        db.commit()
    response = client.request('GET' if path.endswith('/status') else 'POST',path,
        headers=_headers(token), json={'code':'123456','current_password':PASSWORD})
    assert response.status_code == 401, response.text
    assert response.json()['error']['code'] == 'AUTH_INVALID_TOKEN'
