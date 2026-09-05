import os

import sqlalchemy
from sqlalchemy.pool import StaticPool

os.environ["ENV"] = "test"
os.environ.setdefault("BCRYPT_TEST_FAST", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

_real_create_engine = sqlalchemy.create_engine


def _create_test_engine(url, *args, **kwargs):
    if isinstance(url, str) and url.startswith("sqlite:///"):
        engine_kwargs = dict(kwargs)
        connect_args = dict(engine_kwargs.get("connect_args") or {})
        connect_args.setdefault("check_same_thread", False)
        engine_kwargs["connect_args"] = connect_args
        engine_kwargs.setdefault("poolclass", StaticPool)
        return _real_create_engine("sqlite://", *args, **engine_kwargs)
    return _real_create_engine(url, *args, **kwargs)


sqlalchemy.create_engine = _create_test_engine
