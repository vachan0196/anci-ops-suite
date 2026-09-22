import base64
import json
import os
import subprocess
import sys

from pydantic import ValidationError
import pytest

from apps.api.core.settings import Settings
from apps.api.core.totp_key import TOTP_KEY_BYTES, validate_totp_key
from apps.api.tests._deployed_settings import deployed_settings


DEPLOYED_ENVIRONMENTS = ("staging", "production")
ALL_ENVIRONMENTS = ("local", "development", "test", "staging", "production")
HOST63 = "a" * 63
HOST64 = "a" * 64
HOST253 = ".".join([HOST63, HOST63, HOST63, "b" * 61])
HOST254 = ".".join([HOST63, HOST63, HOST63, "b" * 62])


def _settings(environment="staging", **overrides):
    values = deployed_settings()
    values.update(overrides)
    return Settings(
        ENV=environment,
        EMAIL_BACKEND="resend" if environment in DEPLOYED_ENVIRONMENTS else "local_log",
        _env_file=None,
        **values,
    )


def test_hostname_boundary_fixtures():
    assert len(HOST63) == 63
    assert len(HOST64) == 64
    assert len(HOST253) == 253
    assert len(HOST254) == 254
    assert all(1 <= len(label) <= 63 for label in HOST253.split("."))
    assert all(1 <= len(label) <= 63 for label in HOST254.split("."))


def test_deployed_helper_returns_fresh_values():
    first = deployed_settings()
    second = deployed_settings()
    assert first == second
    first["CORS_ORIGINS"].append("https://another.example.test")
    assert second["CORS_ORIGINS"] == ["https://app.example.test"]
    assert len(first["JWT_SECRET_KEY"]) >= 32
    assert first["TOTP_ENCRYPTION_KEY"] != first["JWT_SECRET_KEY"]


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_valid_deployed_configuration_constructs_without_h181_settings(environment):
    config = _settings(environment, RESEND_API_KEY=None, EMAIL_FROM_ADDRESS=None)
    assert config.ENV == environment
    assert config.RESEND_API_KEY is None
    assert config.EMAIL_FROM_ADDRESS is None


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("secret", ["dev-secret-change-me", "x" * 31])
def test_jwt_secret_rejection(environment, secret):
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        _settings(environment, JWT_SECRET_KEY=secret)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_jwt_secret_32_character_boundary(environment):
    assert _settings(environment, JWT_SECRET_KEY="x" * 32).JWT_SECRET_KEY == "x" * 32


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("name,value", [("BCRYPT_TEST_FAST", True), ("RATE_LIMIT_ENABLED", False)])
def test_security_boolean_rejection(environment, name, value):
    with pytest.raises(ValidationError, match=name):
        _settings(environment, **{name: value})


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("key", [
    None, "", "   ", "not-base64!",
    base64.b64encode(bytes(range(31))).decode("ascii"),
    base64.b64encode(bytes(range(33))).decode("ascii"),
])
def test_totp_key_rejection(environment, key):
    with pytest.raises(ValidationError, match="TOTP_ENCRYPTION_KEY"):
        _settings(environment, TOTP_ENCRYPTION_KEY=key)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
def test_totp_key_cannot_reuse_jwt_secret(environment):
    key = deployed_settings()["TOTP_ENCRYPTION_KEY"]
    assert len(key) == 44
    with pytest.raises(ValidationError, match="TOTP_ENCRYPTION_KEY must be a non-blank standard base64 value that decodes to exactly 32 bytes and differs from JWT_SECRET_KEY"):
        _settings(environment, TOTP_ENCRYPTION_KEY=key, JWT_SECRET_KEY=key)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("key,reuse_jwt", [
    (None, False), ("", False), ("   ", False), ("not-base64!", False),
    (base64.b64encode(bytes(range(31))).decode("ascii"), False),
    (base64.b64encode(bytes(range(33))).decode("ascii"), False),
    (base64.b64encode(bytes(range(32))).decode("ascii"), True),
])
def test_totp_settings_error_does_not_include_decoder_messages(environment, key, reuse_jwt):
    overrides = {"TOTP_ENCRYPTION_KEY": key}
    if reuse_jwt:
        overrides["JWT_SECRET_KEY"] = key
    with pytest.raises(ValidationError) as caught:
        _settings(environment, **overrides)
    message = str(caught.value)
    assert "TOTP_ENCRYPTION_KEY must be a non-blank standard base64 value that decodes to exactly 32 bytes and differs from JWT_SECRET_KEY" in message
    for decoder_message in (
        "TOTP_ENCRYPTION_KEY is required for TOTP secret encryption",
        "TOTP_ENCRYPTION_KEY must not reuse JWT_SECRET_KEY",
        "TOTP_ENCRYPTION_KEY must be base64 encoded",
        "TOTP_ENCRYPTION_KEY must decode to exactly 32 bytes",
    ):
        assert decoder_message not in message
        assert decoder_message not in repr(caught.value)


@pytest.mark.parametrize("key,jwt_secret,message", [
    (None, "jwt", "TOTP_ENCRYPTION_KEY is required for TOTP secret encryption"),
    ("", "", "TOTP_ENCRYPTION_KEY is required for TOTP secret encryption"),
    ("invalid", "invalid", "TOTP_ENCRYPTION_KEY must not reuse JWT_SECRET_KEY"),
    ("invalid!", "jwt", "TOTP_ENCRYPTION_KEY must be base64 encoded"),
    (base64.b64encode(b"short").decode("ascii"), "jwt", "TOTP_ENCRYPTION_KEY must decode to exactly 32 bytes"),
])
def test_shared_totp_decoder_messages_and_order(key, jwt_secret, message):
    with pytest.raises(ValueError) as caught:
        validate_totp_key(key, jwt_secret)
    assert str(caught.value) == message
    if message == "TOTP_ENCRYPTION_KEY must be base64 encoded":
        assert caught.value.__cause__ is not None


def test_shared_totp_constant_and_service_import_remain_available():
    from apps.api.services.totp_crypto import TOTP_KEY_BYTES as service_key_bytes
    from apps.api.services.totp_crypto import decode_totp_encryption_key

    assert service_key_bytes == TOTP_KEY_BYTES == 32
    assert decode_totp_encryption_key(deployed_settings()["TOTP_ENCRYPTION_KEY"]) == bytes(range(32))


CORS_REJECTED_URLS = [
    "https://app.example.test\x00", "https://app.example.test\x7f",
    "http://app.example.test", "https://",
    "https://app.example.test/", "https://app.example.test/path",
    "https://user:pw@app.example.test", "https://user@app.example.test", "https://@app.example.test",
    "https://app.example.test?x=1", "https://app.example.test?",
    "https://app.example.test#f", "https://app.example.test#", "https://app.example.test?#",
    " https://app.example.test", "https://app.example.test ",
    "https://app.exa\tmple.test", "https://app.example.test\n",
    "HTTPS://APP.EXAMPLE.TEST", "https://App.example.test",
    "https://app.example.test.", "https://app.example.test..", "https://app.example.test.:8443",
    "https://app.example.test:443",
    "https://app_example.test", "https://-app.example.test", "https://app-.example.test",
    "https://app..example.test", "https://.app.example.test", "https://bücher.example",
    f"https://{HOST64}.example.test", f"https://{HOST254}",
    "https://app.example.test:abc", "https://app.example.test:99999",
    "https://app.example.test:0", "https://app.example.test:", "https://app.example.test:08443",
    "https://localhost:3000", "https://LOCALHOST", "https://localhost.", "https://localhost..",
    "https://app.localhost", "https://127.0.0.1", "https://127.0.0.1.", "https://127.1", "https://127.1.",
    "https://[::1]", "https://0.0.0.0", "https://203.0.113.10", "https://.", "https://[::1", "https://[zzz]",
]


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("origins", [
    [], ["*"], ["https://app.example.test", "*"],
    ["https://app.example.test", "https://localhost:3000"],
    *[[value] for value in CORS_REJECTED_URLS],
])
def test_cors_rejected(environment, origins):
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _settings(environment, CORS_ORIGINS=origins)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("origins", [
    ["https://app.example.test"], ["https://app.example.test:8443"],
    ["https://app.example.test", "https://admin.example.test:8443"],
    ["https://xn--bcher-kva.example"], [f"https://{HOST63}.example.test"], [f"https://{HOST253}"],
])
def test_cors_accepted(environment, origins):
    assert _settings(environment, CORS_ORIGINS=origins).CORS_ORIGINS == origins


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("algorithm", ["RS256", "HS512", "none", "hs256"])
def test_jwt_algorithm_rejection(environment, algorithm):
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        _settings(environment, JWT_ALGORITHM=algorithm)


BASE_REJECTED_URLS = [
    "https://app.example.test/a\x00b", "https://app.example.test/a\x01b",
    "https://app.example.test/a\x7fb", "https://app.example.test\x7f",
    "http://app.example.test", "https://localhost:3000", "https://LOCALHOST",
    "https://localhost.", "https://localhost..", "https://app.localhost",
    "https://127.0.0.1", "https://127.0.0.1.", "https://127.0.0.1..",
    "https://127.1", "https://127.1.", "https://2130706433", "https://2130706433.",
    "https://[::1]", "https://0.0.0.0", "https://[::]", "https://203.0.113.10",
    "https://app_example.test", "https://-app.example.test", "https://app-.example.test",
    "https://app..example.test", "https://bücher.example", f"https://{HOST64}.example.test", f"https://{HOST254}",
    "https://user:pw@app.example.test", "https://user@app.example.test", "https://@app.example.test",
    "https://user@app.example.test/base",
    "https://app.example.test?x=1", "https://app.example.test?", "https://app.example.test#f",
    "https://app.example.test#", "https://app.example.test?#", "https://app.example.test/base?",
    "https://app.example.test:abc", "https://app.example.test:99999", "https://app.example.test:0",
    "https://app.example.test:", "https://app.example.test:/base",
    "https://app.example\n.test", "https://app.example.test/ba\tse", "https://app.example.test/base\n",
    "https://", "https:///path", "https://.", "https://..", "https://[::1", "https://[zzz]",
    "https://[::1]x", "https://[::1].", "app.example.test", "",
    " https://app.example.test", "https://app.example.test ",
]


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("value", BASE_REJECTED_URLS)
def test_app_base_url_rejected(environment, value):
    with pytest.raises(ValidationError, match="APP_BASE_URL"):
        _settings(environment, APP_BASE_URL=value)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("value", [
    "https://app.example.test", "https://app.example.test/", "https://app.example.test/base",
    "HTTPS://app.example.test", "https://app.example.test:8443", "https://app.example.test:8443/base",
    "https://app.example.test.", "https://app.example.test:443", "https://app.example.test/a@b", "https://xn--bcher-kva.example",
    f"https://{HOST253}",
])
def test_app_base_url_accepted_without_rewriting(environment, value):
    assert _settings(environment, APP_BASE_URL=value).APP_BASE_URL == value


@pytest.mark.parametrize("environment", ("local", "development", "test"))
def test_deployed_rules_do_not_apply_elsewhere(environment):
    config = _settings(
        environment, JWT_SECRET_KEY="dev-secret-change-me", BCRYPT_TEST_FAST=True,
        TOTP_ENCRYPTION_KEY=None, CORS_ORIGINS=["http://localhost:3000"],
        RATE_LIMIT_ENABLED=False, JWT_ALGORITHM="RS256", APP_BASE_URL="https://[::1",
    )
    assert config.ENV == environment
    assert config.APP_BASE_URL == "https://[::1"


@pytest.mark.parametrize("environment", ALL_ENVIRONMENTS)
@pytest.mark.parametrize("level", ["DEBUG", "info", "Warning", "WARN", "fatal", "ERROR", "CRITICAL"])
def test_log_level_accepted_in_every_environment(environment, level):
    assert _settings(environment, LOG_LEVEL=level).LOG_LEVEL == level


@pytest.mark.parametrize("environment", ALL_ENVIRONMENTS)
@pytest.mark.parametrize("level", ["NOTSET", "notset", "BASIC_FORMAT", "nonsense", "", " INFO ", "INFO "])
def test_log_level_rejected_in_every_environment(environment, level):
    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        _settings(environment, LOG_LEVEL=level)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("malformed_urls", [False, True])
def test_all_eight_rules_aggregate_even_when_url_parsing_raises(environment, malformed_urls):
    with pytest.raises(ValidationError) as caught:
        _settings(
            environment, JWT_SECRET_KEY="dev-secret-change-me", BCRYPT_TEST_FAST=True,
            TOTP_ENCRYPTION_KEY=None, CORS_ORIGINS=["https://[zzz]"] if malformed_urls else [],
            RATE_LIMIT_ENABLED=False, JWT_ALGORITHM="RS256", LOG_LEVEL="nonsense",
            APP_BASE_URL="https://[::1" if malformed_urls else "http://localhost:3000",
        )
    assert caught.value.error_count() == 1
    message = str(caught.value)
    for name in deployed_settings():
        assert name in message


def test_incompatible_backend_keeps_precedence():
    values = deployed_settings()
    values["JWT_SECRET_KEY"] = "dev-secret-change-me"
    with pytest.raises(ValidationError) as caught:
        Settings(ENV="staging", EMAIL_BACKEND="local_log", _env_file=None, **values)
    assert caught.value.error_count() == 1
    assert "Incompatible EMAIL_BACKEND" in str(caught.value)
    assert "JWT_SECRET_KEY" not in str(caught.value)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("base_url,base_marker", [
    ("http://h154-base-marker.example", "h154-base-marker"),
    ("https://[h154basemarker]", "h154basemarker"),
])
def test_rejection_never_discloses_configured_strings_or_parser_details(environment, base_url, base_marker):
    marker = "h154-jwt-marker-1234"
    assert len(marker) == 20
    invalid = {
        "JWT_SECRET_KEY": marker,
        "TOTP_ENCRYPTION_KEY": base64.b64encode(bytes(range(31))).decode("ascii"),
        "JWT_ALGORITHM": "H154ALGMARKER",
        "LOG_LEVEL": "H154LEVELMARKER",
        "CORS_ORIGINS": ["https://[h154corsmarker]"],
        "APP_BASE_URL": base_url,
    }
    with pytest.raises(ValidationError) as caught:
        _settings(environment, **invalid)
    assert caught.value.error_count() == 1
    message = str(caught.value)
    for name, value in invalid.items():
        assert name in message
        raw_value = value[0] if isinstance(value, list) else value
        assert raw_value not in message
        assert raw_value not in repr(caught.value)
    for private_part in ("h154corsmarker", base_marker):
        assert private_part not in message
        assert private_part not in repr(caught.value)


@pytest.mark.parametrize("valid", [False, True])
def test_import_time_configuration_validation(valid, tmp_path):
    process_env = dict(os.environ, ENV="production", EMAIL_BACKEND="resend")
    marker = "h154-jwt-marker-1234"
    assert len(marker) == 20
    if valid:
        for name, value in deployed_settings().items():
            process_env[name] = json.dumps(value) if isinstance(value, (list, bool)) else value
    else:
        process_env.update(
            JWT_SECRET_KEY=marker, TOTP_ENCRYPTION_KEY="", APP_BASE_URL="http://localhost:3000",
        )
    process_env["PYTHONPATH"] = os.pathsep.join(os.path.abspath(path) for path in sys.path)
    result = subprocess.run(
        [sys.executable, "-c", 'import apps.api.core.settings; print("ok")'],
        env=process_env, cwd=tmp_path, text=True, capture_output=True, timeout=30,
    )
    assert marker not in result.stdout + result.stderr
    if valid:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"
    else:
        assert result.returncode != 0
        for name in ("JWT_SECRET_KEY", "TOTP_ENCRYPTION_KEY", "APP_BASE_URL"):
            assert name in result.stderr
        assert "ok" not in result.stdout
