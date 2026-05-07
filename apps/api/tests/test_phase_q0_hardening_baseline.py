import warnings

from apps.api.core.observability import _before_send
from apps.api.core.security import get_password_hash, verify_password


def test_bcrypt_password_hashing_without_passlib_crypt_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        hashed_password = get_password_hash("password123")

    assert hashed_password.startswith("$2")
    assert verify_password("password123", hashed_password) is True
    assert verify_password("wrong-password", hashed_password) is False
    assert verify_password("a" * 73, hashed_password) is False
    assert not any("crypt" in str(warning.message) for warning in caught)


def test_sentry_before_send_redacts_sensitive_request_data() -> None:
    event = {
        "request": {
            "headers": {
                "authorization": "Bearer secret",
                "x-api-key": "secret-key",
                "user-agent": "test-client",
            },
            "cookies": {"session": "secret"},
            "data": {
                "username": "employee",
                "password": "secret-password",
                "nested": {"access_token": "secret-token"},
            },
        }
    }

    sanitized = _before_send(event, {})

    assert sanitized is not None
    request = sanitized["request"]
    assert request["headers"]["authorization"] == "[Filtered]"
    assert request["headers"]["x-api-key"] == "[Filtered]"
    assert request["headers"]["user-agent"] == "test-client"
    assert request["cookies"] == "[Filtered]"
    assert request["data"]["username"] == "employee"
    assert request["data"]["password"] == "[Filtered]"
    assert request["data"]["nested"]["access_token"] == "[Filtered]"
