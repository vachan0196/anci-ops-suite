import base64


def deployed_settings() -> dict:
    """Fresh, explicitly fake configuration for staging/production construction."""
    return {
        "JWT_SECRET_KEY": "h154-fake-jwt-marker-not-a-real-secret",
        "TOTP_ENCRYPTION_KEY": base64.b64encode(bytes(range(32))).decode("ascii"),
        "CORS_ORIGINS": ["https://app.example.test"],
        "BCRYPT_TEST_FAST": False,
        "RATE_LIMIT_ENABLED": True,
        "JWT_ALGORITHM": "HS256",
        "APP_BASE_URL": "https://app.example.test",
        "LOG_LEVEL": "INFO",
    }
