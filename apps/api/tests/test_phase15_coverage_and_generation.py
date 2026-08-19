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
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.shift import Shift
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers.rota import _validate_templates


PASSWORD = "password123"


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _register_and_login(client: TestClient, email: str) -> dict:
    register_body = _register(client, email)
    token = _login(client, email)
    return {
        "id": uuid.UUID(register_body["id"]),
        "active_tenant_id": uuid.UUID(register_body["active_tenant_id"]),
        "token": token,
    }


def _set_membership(
    test_session_local,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    set_active_tenant: bool = True,
) -> None:
    db = test_session_local()
    try:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.user_id == user_id,
                TenantUser.tenant_id == tenant_id,
            )
        )
        if membership is None:
            db.add(TenantUser(user_id=user_id, tenant_id=tenant_id, role=role))
        else:
            membership.role = role

        user = db.get(User, user_id)
        assert user is not None
        if set_active_tenant:
            user.active_tenant_id = tenant_id
        db.commit()
    finally:
        db.close()


def _create_store(client: TestClient, token: str, code: str) -> str:
    response = client.post(
        "/api/v1/stores",
        json={"code": code, "name": f"Store {code}", "timezone": "UTC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _auth(user: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _future_monday_away_from_month_boundary() -> date:
    candidate = date.today() + timedelta(days=(-date.today().weekday()) % 7)
    while not 7 <= candidate.day <= 14:
        candidate += timedelta(days=7)
    return candidate


def _create_overnight_template(
    client: TestClient,
    admin: dict,
    store_id: str,
    *,
    day_of_week: int = 6,
    start_time: str = "22:00:00",
    end_time: str = "06:00:00",
):
    return client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": day_of_week,
            "start_time": start_time,
            "end_time": end_time,
            "required_headcount": 1,
            "is_active": True,
        },
        headers=_auth(admin),
    )


def _generate_week(
    client: TestClient,
    admin: dict,
    store_id: str,
    week_start: date,
):
    return client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_id, "week_start": week_start.isoformat()},
        headers=_auth(admin),
    )


def _overnight_setup(client: TestClient) -> tuple[dict, str, date, dict]:
    admin = _register_and_login(client, f"p15-overnight-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], f"P15-ON-{uuid.uuid4().hex[:8]}")
    week_start = _future_monday_away_from_month_boundary()
    template_response = _create_overnight_template(client, admin, store_id)
    assert template_response.status_code == 201, template_response.text
    return admin, store_id, week_start, template_response.json()


def _create_member_and_staff_profile(
    client: TestClient,
    admin: dict,
    store_id: str,
) -> dict:
    member_response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"p15-overnight-staff-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": "Overnight Staff",
            "role": "member",
        },
        headers=_auth(admin),
    )
    assert member_response.status_code == 201, member_response.text
    member = member_response.json()
    profile_response = client.post(
        "/api/v1/staff",
        json={
            "user_id": member["id"],
            "store_id": store_id,
            "display_name": "Overnight Staff",
            "job_title": "Cashier",
            "is_active": True,
        },
        headers=_auth(admin),
    )
    assert profile_response.status_code == 201, profile_response.text
    return member


def _configure_opening_hours(client: TestClient, admin: dict, store_id: str) -> None:
    response = client.put(
        f"/api/v1/stores/{store_id}/opening-hours",
        json={
            "opening_hours": [
                {
                    "day_of_week": day,
                    "open_time": "06:00",
                    "close_time": "22:00",
                    "is_closed": False,
                }
                for day in range(7)
            ]
        },
        headers=_auth(admin),
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_phase15_coverage_and_generation.db"
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


def test_coverage_templates_admin_crud_happy_path(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-ct-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-CT-001")

    create_response = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 2,
            "required_role": "crew",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_response.status_code == 201
    template_id = create_response.json()["id"]

    list_response = client.get(
        "/api/v1/coverage-templates",
        params={"store_id": store_id},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    patch_response = client.patch(
        f"/api/v1/coverage-templates/{template_id}",
        json={"required_headcount": 3, "is_active": False},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["required_headcount"] == 3
    assert patch_response.json()["is_active"] is False

    delete_response = client.delete(
        f"/api/v1/coverage-templates/{template_id}",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert delete_response.status_code == 200


def test_coverage_templates_cross_tenant_access_returns_404(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"p15-ct-iso-admin-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p15-ct-iso-admin-b-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin_a["token"], "P15-CT-ISO")

    create_response = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 1,
            "start_time": "10:00:00",
            "end_time": "18:00:00",
            "required_headcount": 1,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin_a['token']}"},
    )
    assert create_response.status_code == 201
    template_id = create_response.json()["id"]

    cross_patch = client.patch(
        f"/api/v1/coverage-templates/{template_id}",
        json={"required_headcount": 2},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_patch.status_code == 404

    cross_delete = client.delete(
        f"/api/v1/coverage-templates/{template_id}",
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert cross_delete.status_code == 404


def test_coverage_templates_validation_errors(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-ct-validation-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-CT-VAL")

    bad_day = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 7,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert bad_day.status_code == 422

    bad_headcount = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 2,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 0,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert bad_headcount.status_code == 422

    bad_time = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 2,
            "start_time": "17:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert bad_time.status_code == 422


def test_validate_templates_rejects_equal_time_transient_template(
    test_session_local,
) -> None:
    template = CoverageTemplate(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        day_of_week=0,
        start_time=time(9),
        end_time=time(9),
        required_headcount=1,
        is_active=True,
    )
    db = test_session_local()
    try:
        with pytest.raises(ApiError) as raised:
            _validate_templates(
                db,
                tenant_id=template.tenant_id,
                store_id=template.store_id,
                templates=[template],
            )
        assert raised.value.status_code == 422
        assert raised.value.code == "COVERAGE_TEMPLATE_INVALID"
    finally:
        db.close()


def test_overnight_coverage_template_post_succeeds(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-overnight-post-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], f"P15-OP-{uuid.uuid4().hex[:8]}")

    response = _create_overnight_template(client, admin, store_id)

    assert response.status_code == 201, response.text
    assert response.json()["start_time"] == "22:00:00"
    assert response.json()["end_time"] == "06:00:00"


def test_overnight_coverage_template_can_be_updated_via_patch(client: TestClient) -> None:
    admin, store_id, _, template = _overnight_setup(client)

    response = client.patch(
        f"/api/v1/coverage-templates/{template['id']}",
        json={"start_time": "21:00:00", "end_time": "05:00:00"},
        headers=_auth(admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["start_time"] == "21:00:00"
    assert response.json()["end_time"] == "05:00:00"


def test_generate_week_accepts_persisted_overnight_template(client: TestClient) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)

    response = _generate_week(client, admin, store_id, week_start)

    assert response.status_code == 200, response.text
    assert response.json()["created_count"] == 1


def test_generated_overnight_shift_ends_next_day_with_correct_duration(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    generate = _generate_week(client, admin, store_id, week_start)
    assert generate.status_code == 200, generate.text

    db = test_session_local()
    try:
        shift = db.scalar(
            select(Shift).where(
                Shift.store_id == uuid.UUID(store_id),
                Shift.status == "scheduled",
            )
        )
        assert shift is not None
        assert shift.end_at.date() == shift.start_at.date() + timedelta(days=1)
        assert shift.end_at - shift.start_at == timedelta(hours=8)
    finally:
        db.close()


def test_sunday_overnight_shift_is_owned_by_sunday_starting_week(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    generate = _generate_week(client, admin, store_id, week_start)
    assert generate.status_code == 200, generate.text

    db = test_session_local()
    try:
        shift = db.scalar(
            select(Shift).where(
                Shift.store_id == uuid.UUID(store_id),
                Shift.status == "scheduled",
            )
        )
        assert shift is not None
        assert shift.start_at.date() == week_start + timedelta(days=6)
        assert shift.start_at.time() == time(22)
        assert shift.end_at.date() == week_start + timedelta(days=7)
        assert shift.end_at.time() == time(6)
    finally:
        db.close()


def test_regenerating_owning_week_does_not_duplicate_sunday_overnight_shift(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    first = _generate_week(client, admin, store_id, week_start)
    assert first.status_code == 200, first.text
    second = _generate_week(client, admin, store_id, week_start)
    assert second.status_code == 200, second.text
    assert second.json()["created_count"] == 1
    assert second.json()["replaced_count"] == 1

    db = test_session_local()
    try:
        shifts = db.scalars(
            select(Shift).where(Shift.store_id == uuid.UUID(store_id))
        ).all()
        active = [shift for shift in shifts if shift.status == "scheduled"]
        cancelled = [shift for shift in shifts if shift.status == "cancelled"]
        assert len(active) == 1
        assert len(cancelled) == 1
        assert active[0].start_at == cancelled[0].start_at
        assert active[0].end_at == cancelled[0].end_at
    finally:
        db.close()


def test_following_week_generation_does_not_absorb_or_delete_owning_week_shift(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    first = _generate_week(client, admin, store_id, week_start)
    assert first.status_code == 200, first.text
    following = _generate_week(client, admin, store_id, week_start + timedelta(days=7))
    assert following.status_code == 200, following.text

    db = test_session_local()
    try:
        active = db.scalars(
            select(Shift).where(
                Shift.store_id == uuid.UUID(store_id),
                Shift.status == "scheduled",
            )
        ).all()
        assert len(active) == 2
        assert {shift.start_at.date() for shift in active} == {
            week_start + timedelta(days=6),
            week_start + timedelta(days=13),
        }
    finally:
        db.close()


def test_publish_and_unpublish_scope_sunday_overnight_shift_to_owning_week(
    client: TestClient,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    _create_member_and_staff_profile(client, admin, store_id)
    _configure_opening_hours(client, admin, store_id)
    generate = _generate_week(client, admin, store_id, week_start)
    assert generate.status_code == 200, generate.text

    following_publish = client.post(
        f"/api/v1/sites/{store_id}/rota/publish",
        json={"week_start": (week_start + timedelta(days=7)).isoformat()},
        headers=_auth(admin),
    )
    assert following_publish.status_code == 409
    assert following_publish.json()["error"]["code"] == "ROTA_NO_SHIFTS"

    publish = client.post(
        f"/api/v1/sites/{store_id}/rota/publish",
        json={"week_start": week_start.isoformat()},
        headers=_auth(admin),
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["published_shift_count"] == 1

    following_unpublish = client.post(
        f"/api/v1/sites/{store_id}/rota/unpublish",
        json={"week_start": (week_start + timedelta(days=7)).isoformat()},
        headers=_auth(admin),
    )
    assert following_unpublish.status_code == 409
    assert following_unpublish.json()["error"]["code"] == "ROTA_NOT_PUBLISHED"

    unpublish = client.post(
        f"/api/v1/sites/{store_id}/rota/unpublish",
        json={"week_start": week_start.isoformat()},
        headers=_auth(admin),
    )
    assert unpublish.status_code == 200, unpublish.text
    assert unpublish.json()["published_shift_count"] == 0


def test_weekly_rota_read_returns_sunday_overnight_shift_only_in_owning_week(
    client: TestClient,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    generate = _generate_week(client, admin, store_id, week_start)
    assert generate.status_code == 200, generate.text

    owning = client.get(
        f"/api/v1/sites/{store_id}/rota/week",
        params={"week_start": week_start.isoformat()},
        headers=_auth(admin),
    )
    following = client.get(
        f"/api/v1/sites/{store_id}/rota/week",
        params={"week_start": (week_start + timedelta(days=7)).isoformat()},
        headers=_auth(admin),
    )

    assert owning.status_code == 200, owning.text
    assert len(owning.json()["shifts"]) == 1
    assert following.status_code == 200, following.text
    assert following.json()["shifts"] == []


def test_weekly_hour_status_counts_full_overnight_duration_in_owning_week(
    client: TestClient,
    test_session_local,
) -> None:
    admin, store_id, week_start, _ = _overnight_setup(client)
    member = _create_member_and_staff_profile(client, admin, store_id)
    generate = _generate_week(client, admin, store_id, week_start)
    assert generate.status_code == 200, generate.text

    db = test_session_local()
    try:
        shift = db.scalar(
            select(Shift).where(
                Shift.store_id == uuid.UUID(store_id),
                Shift.status == "scheduled",
            )
        )
        assert shift is not None
        shift.assigned_user_id = uuid.UUID(member["id"])
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"/api/v1/sites/{store_id}/rota/week",
        params={"week_start": week_start.isoformat()},
        headers=_auth(admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["weekly_hour_status"] == [
        {
            "user_id": member["id"],
            "scheduled_hours": 8.0,
            "weekly_soft_cap": None,
            "exceeded": False,
        }
    ]


def test_generate_week_creates_expected_shifts_and_fields(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, f"p15-rota-generate-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-ROTA-001")

    create_template_monday = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 2,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_template_monday.status_code == 201

    create_template_tuesday = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 1,
            "start_time": "12:00:00",
            "end_time": "16:00:00",
            "required_headcount": 1,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert create_template_tuesday.status_code == 201

    generate = client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_id, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert generate.status_code == 200
    assert generate.json()["created_count"] == 3

    db = test_session_local()
    try:
        shifts = db.scalars(select(Shift).where(Shift.store_id == uuid.UUID(store_id))).all()
        assert len(shifts) == 3
        assert all(shift.assigned_user_id is None for shift in shifts)
        assert all(shift.status == "scheduled" for shift in shifts)
        assert all(shift.published_at is None for shift in shifts)
    finally:
        db.close()


def test_generate_week_safely_regenerates_when_manual_shift_already_exists(client: TestClient) -> None:
    admin = _register_and_login(client, f"p15-rota-conflict-admin-{uuid.uuid4()}@example.com")
    store_id = _create_store(client, admin["token"], "P15-ROTA-409")

    template = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert template.status_code == 201

    existing_shift = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": "2026-04-06T09:00:00Z",
            "end_at": "2026-04-06T17:00:00Z",
        },
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert existing_shift.status_code == 201

    generate = client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_id, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert generate.status_code == 200
    assert generate.json()["created_count"] == 1
    assert generate.json()["replaced_count"] == 0
    assert generate.json()["kept_conflict_count"] == 1


def test_generate_week_cross_tenant_store_returns_404(client: TestClient) -> None:
    admin_a = _register_and_login(client, f"p15-rota-iso-admin-a-{uuid.uuid4()}@example.com")
    admin_b = _register_and_login(client, f"p15-rota-iso-admin-b-{uuid.uuid4()}@example.com")
    store_a = _create_store(client, admin_a["token"], "P15-ROTA-ISO")

    generate = client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_a, "week_start": "2026-04-06"},
        headers={"Authorization": f"Bearer {admin_b['token']}"},
    )
    assert generate.status_code == 404
