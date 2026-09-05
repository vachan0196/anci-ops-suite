import copy
from http.cookies import SimpleCookie
import json
import os
import subprocess
import sys
from unittest.mock import Mock

from fastapi import Response
from pydantic import ValidationError
import pytest

from apps.api.core import observability
from apps.api.core.settings import Settings
from apps.api.routers import auth
from apps.api.schemas.auth import PasswordResetConfirmRequest


SECRET = "credential-must-not-leave-process"
REDACTED = "[Filtered]"
ENVIRONMENTS = ("local", "development", "test", "staging", "production")
BACKENDS = ("local_log", "test_capture")
SENSITIVE_KEYS = (
    "token", "raw_token", "token_hash", "access_token", "refresh_token",
    "password", "new_password", "confirm_password", "authorization", "cookie",
    "secret", "api_key", "reset_url", "verification_url",
)


@pytest.mark.parametrize("interface", ["request", "contexts", "extra"])
def test_sentry_scrubs_sensitive_keys_recursively(interface: str) -> None:
    sensitive = {key.upper(): SECRET for key in SENSITIVE_KEYS}
    event = {
        interface: {
            **sensitive,
            "data": {"nested": [dict(sensitive), {"safe": "preserved"}]},
        }
    }

    sanitized = observability._before_send(event, {})

    assert SECRET not in json.dumps(sanitized)
    for key in sensitive:
        assert sanitized[interface][key] == REDACTED
        assert sanitized[interface]["data"]["nested"][0][key] == REDACTED
    assert sanitized[interface]["data"]["nested"][1] == {"safe": "preserved"}


@pytest.mark.parametrize("interface", ["request", "contexts", "extra"])
def test_sentry_scrubs_list_interfaces(interface: str) -> None:
    event = {interface: [{"raw_token": SECRET}, [None, {"reset_url": SECRET}]]}

    assert observability._before_send(event, {}) == {
        interface: [{"raw_token": REDACTED}, [None, {"reset_url": REDACTED}]]
    }


@pytest.mark.parametrize(
    ("interface", "trace_name"),
    [
        (None, "stacktrace"),
        ("exception", "stacktrace"),
        ("exception", "raw_stacktrace"),
        ("threads", "stacktrace"),
        ("threads", "raw_stacktrace"),
    ],
)
def test_sentry_strips_all_frame_vars_in_every_stacktrace(interface, trace_name) -> None:
    payload = PasswordResetConfirmRequest(
        token=SECRET, new_password=SECRET, confirm_password=SECRET
    )
    assert SECRET in repr(payload)
    trace = {
        "frames": [
            {"filename": "auth.py", "vars": {"payload": repr(payload)}},
            {"filename": "helper.py", "vars": {"count": 7}},
            {"filename": "caller.py"},
        ]
    }
    traces = [trace] if interface is None else [trace, copy.deepcopy(trace)]
    event = (
        {trace_name: trace}
        if interface is None
        else {interface: {"values": [{trace_name: item} for item in traces]}}
    )

    sanitized = observability._before_send(event, {})

    assert SECRET not in json.dumps(sanitized)
    for item in traces:
        assert item["frames"] == [
            {"filename": "auth.py"},
            {"filename": "helper.py"},
            {"filename": "caller.py"},
        ]


@pytest.mark.parametrize(
    "malformed",
    [None, 7, "invalid", [], {}, {"values": None}, {"values": {}},
     {"values": "invalid"}, {"values": [None, 7, [], {}]}],
)
def test_sentry_handles_missing_or_malformed_interfaces(malformed) -> None:
    event = {
        "exception": malformed, "threads": malformed,
        "request": malformed, "contexts": malformed, "extra": malformed,
    }

    assert observability._before_send(event, {}) is event
    assert observability._before_send({}, {}) == {}


@pytest.mark.parametrize(
    "trace",
    [None, 7, [], {}, {"frames": None}, {"frames": {}}, {"frames": "invalid"},
     {"frames": [None, 7, [], {}, {"filename": "safe.py"}, {"vars": None}]}],
)
def test_sentry_handles_missing_or_malformed_stacktraces(trace) -> None:
    event = {
        "stacktrace": trace,
        "exception": {"values": [{"stacktrace": trace, "raw_stacktrace": trace}]},
        "threads": {"values": [{"stacktrace": trace, "raw_stacktrace": trace}]},
    }

    assert observability._before_send(event, {}) is event
    if isinstance(trace, dict) and isinstance(trace.get("frames"), list):
        assert all("vars" not in frame for frame in trace["frames"] if isinstance(frame, dict))


@pytest.mark.parametrize("event", [None, [], "invalid", 7])
def test_sentry_drops_malformed_events(event) -> None:
    assert observability._before_send(event, {}) is None


def test_sentry_redacts_cycles_and_deep_structures_without_leaking() -> None:
    cyclic_dict = {"token": SECRET}
    cyclic_list = [{"password": SECRET}]
    cyclic_dict["loop"] = cyclic_list
    cyclic_list.extend([cyclic_dict, cyclic_list])
    deep = {"verification_url": SECRET}
    for _ in range(1500):
        deep = {"nested": [deep]}
    shared = {"raw_token": SECRET, "safe": "preserved"}
    event = {"extra": {"cycle": cyclic_dict, "deep": deep, "shared": [shared, shared]}}

    sanitized = observability._before_send(event, {})

    assert SECRET not in json.dumps(sanitized)
    assert sanitized["extra"]["cycle"] == {
        "token": REDACTED, "loop": [{"password": REDACTED}, REDACTED, REDACTED]
    }
    assert sanitized["extra"]["shared"] == [
        {"raw_token": REDACTED, "safe": "preserved"},
        {"raw_token": REDACTED, "safe": "preserved"},
    ]


def test_sentry_init_disables_local_variable_collection(monkeypatch) -> None:
    init = Mock()
    config = Settings(ENV="test", SENTRY_DSN="https://public@example.invalid/1", _env_file=None)
    monkeypatch.setattr(observability, "settings", config)
    monkeypatch.setattr(observability.sentry_sdk, "init", init)

    observability.init_observability()

    init.assert_called_once_with(
        dsn=config.SENTRY_DSN,
        environment="test",
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        include_local_variables=False,
        before_send=observability._before_send,
    )


@pytest.mark.parametrize("environment", ["local", "development", "test"])
@pytest.mark.parametrize("backend", BACKENDS)
def test_settings_accepts_every_allowed_pair(environment, backend) -> None:
    config = Settings(ENV=environment, EMAIL_BACKEND=backend, _env_file=None)

    assert config.ENV == environment
    assert config.EMAIL_BACKEND == backend


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("backend", BACKENDS)
def test_settings_rejects_every_incompatible_pair(environment, backend) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(ENV=environment, EMAIL_BACKEND=backend, JWT_SECRET_KEY=SECRET, _env_file=None)

    message = str(caught.value)
    assert "Incompatible EMAIL_BACKEND" in message
    assert f"recognised ENV {environment!r}" in message
    assert f"received {backend!r}" in message
    assert "permitted values: <none implemented>" in message
    assert "Unknown ENV" not in message
    assert SECRET not in message


@pytest.mark.parametrize("environment", ["dev", "prod", "DEVELOPMENT", " development ", "", None, 7, []])
def test_settings_rejects_unknown_environment_without_coercion(environment) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(ENV=environment, JWT_SECRET_KEY=SECRET, _env_file=None)

    message = str(caught.value)
    assert "Unknown ENV" in message
    assert f"received {environment!r}" in message
    assert "permitted values: " + ", ".join(ENVIRONMENTS) in message
    assert "Incompatible EMAIL_BACKEND" not in message
    assert SECRET not in message


def test_settings_requires_environment_without_default(monkeypatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    assert Settings.model_fields["ENV"].is_required()

    with pytest.raises(ValidationError) as caught:
        Settings(JWT_SECRET_KEY=SECRET, _env_file=None)

    message = str(caught.value)
    assert "Missing ENV: received <unset>" in message
    assert "permitted values: " + ", ".join(ENVIRONMENTS) in message
    assert SECRET not in message


@pytest.mark.parametrize("backend", ["smtp", "LOCAL_LOG", "", None, 7, []])
def test_settings_rejects_unknown_email_backend(backend) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(ENV="test", EMAIL_BACKEND=backend, JWT_SECRET_KEY=SECRET, _env_file=None)

    message = str(caught.value)
    assert "Unknown EMAIL_BACKEND" in message
    assert f"received {backend!r}" in message
    assert "permitted values: local_log, test_capture" in message
    assert SECRET not in message


def test_settings_retains_email_backend_default(monkeypatch) -> None:
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)

    assert Settings(ENV="development", _env_file=None).EMAIL_BACKEND == "local_log"
    with pytest.raises(ValidationError, match="Incompatible EMAIL_BACKEND"):
        Settings(ENV="production", _env_file=None)


@pytest.mark.parametrize(
    ("environment", "backend", "expected_error"),
    [
        ("production", "local_log", "Incompatible EMAIL_BACKEND"),
        ("staging", "test_capture", "Incompatible EMAIL_BACKEND"),
        ("prod", "local_log", "Unknown ENV"),
        (None, "local_log", "Missing ENV"),
        ("development", "smtp", "Unknown EMAIL_BACKEND"),
        ("development", "local_log", None),
    ],
)
def test_settings_import_enforces_configuration(environment, backend, expected_error, tmp_path) -> None:
    process_env = dict(os.environ, EMAIL_BACKEND=backend, JWT_SECRET_KEY=SECRET)
    if environment is None:
        process_env.pop("ENV", None)
    else:
        process_env["ENV"] = environment
    process_env["PYTHONPATH"] = os.pathsep.join(os.path.abspath(path) for path in sys.path)

    result = subprocess.run(
        [sys.executable, "-c", 'import apps.api.core.settings; print("ok")'],
        env=process_env, cwd=tmp_path, text=True, capture_output=True, timeout=30,
    )

    assert SECRET not in result.stdout + result.stderr
    if expected_error is None:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"
    else:
        assert result.returncode != 0
        assert expected_error in result.stderr
        assert "ok" not in result.stdout


@pytest.mark.parametrize(
    ("environment", "secure"),
    [("local", False), ("development", False), ("test", False),
     ("staging", True), ("production", True)],
)
def test_refresh_cookie_secure_flag_for_setting_and_clearing(environment, secure, monkeypatch) -> None:
    # Production cannot construct Settings yet; isolate the cookie policy through the verified seam.
    config = Settings.model_construct(ENV=environment)
    monkeypatch.setattr(auth, "settings", config)

    for clear in (False, True):
        response = Response()
        if clear:
            auth._clear_refresh_cookie(response)
        else:
            auth._set_refresh_cookie(response, "test-refresh-token")
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        refresh = cookie[config.AUTH_REFRESH_COOKIE_NAME]

        assert bool(refresh["secure"]) is secure
        assert refresh["httponly"]
        assert refresh["samesite"] == "strict"
        assert refresh["path"] == auth.REFRESH_COOKIE_PATH
