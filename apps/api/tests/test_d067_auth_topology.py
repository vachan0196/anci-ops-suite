"""Closed decoder inventory; HTTP enforcement is proved by the separate sweep.

Resolve imports and simple aliases to Python objects, then compare identities.
Production sources exclude tests by directory, not by function naming. These
checks cover the repository's static decoder calls; the HTTP sweep also covers
routes using other mechanisms.
"""
import ast
import importlib
import inspect
from pathlib import Path

from jose import jwt
from apps.api.core import deps, security
from apps.api.routers import auth

ROOT = Path(__file__).resolve().parents[3]
WRAPPER = security.decode_access_token
AUTHENTICATORS = {
    deps.get_current_user, deps.get_current_employee_account,
    deps.get_current_admin_user_and_session, auth._get_current_admin_user,
    auth.me, inspect.unwrap(auth.request_email_verification),
}


def _resolve(node, names):
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.Attribute):
        parent = _resolve(node.value, names)
        return getattr(parent, node.attr, None) if parent is not None else None
    return None


def _decoder_calls():
    targets = (jwt.decode, security.decode_access_token, security.decode_access_token_payload)
    found = []
    for base in (ROOT/'apps/api', ROOT/'services'):
        for path in base.rglob('*.py'):
            if 'tests' in path.relative_to(ROOT).parts:
                continue
            tree = ast.parse(path.read_text())
            relevant_import = path == ROOT / "apps/api/core/security.py"
            for imported in tree.body:
                if isinstance(imported, ast.Import):
                    relevant_import = relevant_import or any(
                        alias.name in {"jose", "jose.jwt", "apps.api.core.security"}
                        for alias in imported.names
                    )
                elif isinstance(imported, ast.ImportFrom):
                    relevant_import = relevant_import or imported.module in {
                        "jose", "apps.api.core", "apps.api.core.security"
                    }
            if not relevant_import:
                continue
            names = {}
            module_name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
            module = importlib.import_module(module_name)
            for definition in tree.body:
                if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names[definition.name] = getattr(module, definition.name)

            def bind(nodes, scope):
                for node in nodes:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in {'jose','jose.jwt','apps.api.core.security'}:
                                scope[alias.asname or alias.name.split('.')[0]] = importlib.import_module(alias.name if alias.asname else alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom) and node.module in {'jose','apps.api.core','apps.api.core.security'}:
                        module = importlib.import_module(node.module)
                        for alias in node.names:
                            assert alias.name != '*', f'Uninspectable wildcard import: {path}'
                            scope[alias.asname or alias.name] = getattr(module, alias.name)
                    elif isinstance(node, ast.Assign):
                        value = _resolve(node.value, scope)
                        for target in node.targets:
                            if isinstance(target, ast.Name) and value is not None:
                                scope[target.id] = value
            bind(tree.body,names)
            # Local import/assignment aliases are resolved separately for each function.
            for function in ast.walk(tree):
                if not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    continue
                scope = dict(names)
                bind(list(ast.walk(function)),scope)
                for call in ast.walk(function):
                    if not isinstance(call,ast.Call):
                        continue
                    target = _resolve(call.func,scope)
                    if any(target is candidate for candidate in targets):
                        enclosing = getattr(module,function.name,None)
                        assert enclosing is not None, f'Unresolved decoder caller: {path}:{function.lineno}'
                        found.append((inspect.unwrap(enclosing),target))
    return found


def test_jwt_decode_has_one_production_caller():
    callers = [caller for caller,target in _decoder_calls() if target is jwt.decode]
    assert callers == [security.decode_access_token_payload]


def test_decoder_enclosing_set_and_internal_wrapper():
    calls = [(caller,target) for caller,target in _decoder_calls() if target is not jwt.decode]
    assert {caller for caller,_ in calls} == AUTHENTICATORS | {WRAPPER}
    wrapper_calls = [target for caller,target in calls if caller is WRAPPER]
    assert wrapper_calls == [security.decode_access_token_payload]
    assert WRAPPER not in AUTHENTICATORS
    # The wrapper is a decoder only: no request/dependency/database inputs.
    assert list(inspect.signature(WRAPPER).parameters) == ['token']
