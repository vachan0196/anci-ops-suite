from collections.abc import Generator
from datetime import date, time, timedelta
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.core.errors import ApiError
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.routers.availability import _validate_availability_payload
from apps.api.schemas.availability import AvailabilityCreate


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_h088a_availability_date_boundaries.db"
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


def _monday_for(anchor: date) -> date:
    return anchor - timedelta(days=anchor.weekday())


def _future_monday(anchor: date) -> date:
    return _monday_for(anchor) + timedelta(weeks=2)


def _payload(
    *,
    week_start: date,
    entry_date: date,
    start_time: str | None = None,
    end_time: str | None = None,
) -> AvailabilityCreate:
    return AvailabilityCreate(
        week_start=week_start,
        date=entry_date,
        start_time=start_time,
        end_time=end_time,
        type="available",
    )


def _assert_validation_error(response) -> None:
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def _register_and_login(client: TestClient) -> dict:
    email = f"h088a-admin-{uuid.uuid4()}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert registered.status_code == 201, registered.text

    logged_in = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert logged_in.status_code == 200, logged_in.text
    return {
        "id": registered.json()["id"],
        "token": logged_in.json()["access_token"],
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_availability_context(client: TestClient) -> dict:
    admin = _register_and_login(client)
    store_code = f"H088A-{uuid.uuid4()}"
    store_response = client.post(
        "/api/v1/stores",
        json={
            "code": store_code,
            "name": f"Store {store_code}",
            "timezone": "Europe/London",
        },
        headers=_auth(admin["token"]),
    )
    assert store_response.status_code == 201, store_response.text
    store_id = store_response.json()["id"]

    username = f"h088a-{uuid.uuid4()}"
    member_response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"{username}@example.com",
            "password": PASSWORD,
            "full_name": "H088a Employee",
            "role": "member",
        },
        headers=_auth(admin["token"]),
    )
    assert member_response.status_code == 201, member_response.text
    member_id = member_response.json()["id"]

    staff_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": member_id,
            "store_id": store_id,
            "employee_username": username,
            "employee_password": EMPLOYEE_PASSWORD,
            "display_name": "H088a Employee",
            "is_active": True,
        },
        headers=_auth(admin["token"]),
    )
    assert staff_response.status_code == 201, staff_response.text

    employee_login = client.post(
        "/api/v1/auth/employee/login",
        json={
            "site_id": store_id,
            "username": username,
            "password": EMPLOYEE_PASSWORD,
        },
    )
    assert employee_login.status_code == 200, employee_login.text
    return {
        "admin_token": admin["token"],
        "employee_token": employee_login.json()["access_token"],
        "staff_user_id": member_id,
    }


def _employee_create(
    client: TestClient,
    *,
    token: str,
    week_start: date,
    entry_date: date,
):
    return client.post(
        "/api/v1/employee/me/availability",
        json={
            "week_start": week_start.isoformat(),
            "date": entry_date.isoformat(),
            "type": "available",
        },
        headers=_auth(token),
    )


def _admin_replace(
    client: TestClient,
    *,
    token: str,
    staff_user_id: str,
    week_start: date,
    entries: list[dict],
):
    return client.put(
        f"/api/v1/staff/{staff_user_id}/availability/week",
        json={"week_start": week_start.isoformat(), "entries": entries},
        headers=_auth(token),
    )


def test_shared_validation_accepts_monday_week_start() -> None:
    today = date.today()
    week_start = _monday_for(today)

    assert _validate_availability_payload(
        _payload(week_start=week_start, entry_date=week_start)
    ) is None


@pytest.mark.parametrize("weekday_offset", range(1, 7))
def test_shared_validation_rejects_each_non_monday_week_start(weekday_offset: int) -> None:
    today = date.today()
    week_start = _monday_for(today) + timedelta(days=weekday_offset)

    with pytest.raises(ApiError) as exc_info:
        _validate_availability_payload(
            _payload(week_start=week_start, entry_date=week_start)
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("date_offset", [0, 6])
def test_shared_validation_accepts_inclusive_date_window_boundaries(date_offset: int) -> None:
    today = date.today()
    week_start = _monday_for(today)
    entry_date = week_start + timedelta(days=date_offset)

    assert _validate_availability_payload(
        _payload(week_start=week_start, entry_date=entry_date)
    ) is None


@pytest.mark.parametrize("date_offset", [-1, 7])
def test_shared_validation_rejects_outside_half_open_date_window(date_offset: int) -> None:
    today = date.today()
    week_start = _monday_for(today)
    entry_date = week_start + timedelta(days=date_offset)

    with pytest.raises(ApiError) as exc_info:
        _validate_availability_payload(
            _payload(week_start=week_start, entry_date=entry_date)
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_employee_past_date_guard_rejects_yesterday_accepts_today_and_future(
    client: TestClient,
) -> None:
    today = date.today()
    context = _create_availability_context(client)
    responses = {}

    for date_offset in (-1, 0, 1):
        entry_date = today + timedelta(days=date_offset)
        responses[date_offset] = _employee_create(
            client,
            token=context["employee_token"],
            week_start=_monday_for(entry_date),
            entry_date=entry_date,
        )

    _assert_validation_error(responses[-1])
    assert responses[0].status_code == 201, responses[0].text
    assert responses[1].status_code == 201, responses[1].text


def test_submitted_row_shape_validation_and_persistence(
    client: TestClient,
    test_session_local,
) -> None:
    today = date.today()
    week_start = _future_monday(today)
    entry_date = week_start + timedelta(days=1)
    context = _create_availability_context(client)
    common = {
        "token": context["admin_token"],
        "staff_user_id": context["staff_user_id"],
        "week_start": week_start,
    }

    full_day = _admin_replace(
        client,
        **common,
        entries=[{"date": entry_date.isoformat(), "type": "available"}],
    )
    assert full_day.status_code == 200, full_day.text
    assert full_day.json()["items"][0]["start_time"] is None
    assert full_day.json()["items"][0]["end_time"] is None

    with test_session_local() as db:
        persisted_full_day = db.scalars(
            select(AvailabilityEntry).where(
                AvailabilityEntry.user_id == uuid.UUID(context["staff_user_id"]),
                AvailabilityEntry.week_start == week_start,
            )
        ).all()
        assert len(persisted_full_day) == 1
        assert persisted_full_day[0].start_time is None
        assert persisted_full_day[0].end_time is None

    for half_open_times in (
        {"start_time": "09:00:00"},
        {"end_time": "17:00:00"},
    ):
        half_open = _admin_replace(
            client,
            **common,
            entries=[
                {
                    "date": entry_date.isoformat(),
                    "type": "available",
                    **half_open_times,
                }
            ],
        )
        _assert_validation_error(half_open)

    for invalid_end_time in ("09:00:00", "08:59:59"):
        invalid_order = _admin_replace(
            client,
            **common,
            entries=[
                {
                    "date": entry_date.isoformat(),
                    "type": "available",
                    "start_time": "09:00:00",
                    "end_time": invalid_end_time,
                }
            ],
        )
        _assert_validation_error(invalid_order)

    timed = _admin_replace(
        client,
        **common,
        entries=[
            {
                "date": entry_date.isoformat(),
                "type": "available",
                "start_time": "09:00:00",
                "end_time": "17:00:00",
            }
        ],
    )
    assert timed.status_code == 200, timed.text
    assert timed.json()["items"][0]["start_time"] == "09:00:00"
    assert timed.json()["items"][0]["end_time"] == "17:00:00"

    with test_session_local() as db:
        persisted_timed = db.scalars(
            select(AvailabilityEntry).where(
                AvailabilityEntry.user_id == uuid.UUID(context["staff_user_id"]),
                AvailabilityEntry.week_start == week_start,
            )
        ).all()
        assert len(persisted_timed) == 1
        assert persisted_timed[0].start_time == time(hour=9)
        assert persisted_timed[0].end_time == time(hour=17)


def test_admin_replace_week_matches_employee_week_and_date_validation(
    client: TestClient,
) -> None:
    today = date.today()
    week_start = _future_monday(today)
    context = _create_availability_context(client)
    non_monday = week_start + timedelta(days=1)
    out_of_window = week_start + timedelta(days=7)

    employee_bad_week = _employee_create(
        client,
        token=context["employee_token"],
        week_start=non_monday,
        entry_date=non_monday,
    )
    admin_bad_week = _admin_replace(
        client,
        token=context["admin_token"],
        staff_user_id=context["staff_user_id"],
        week_start=non_monday,
        entries=[{"date": non_monday.isoformat(), "type": "available"}],
    )
    employee_bad_date = _employee_create(
        client,
        token=context["employee_token"],
        week_start=week_start,
        entry_date=out_of_window,
    )
    admin_bad_date = _admin_replace(
        client,
        token=context["admin_token"],
        staff_user_id=context["staff_user_id"],
        week_start=week_start,
        entries=[{"date": out_of_window.isoformat(), "type": "available"}],
    )

    for response in (
        employee_bad_week,
        admin_bad_week,
        employee_bad_date,
        admin_bad_date,
    ):
        _assert_validation_error(response)
