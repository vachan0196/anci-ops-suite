from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import os
from threading import Barrier
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from apps.api.core.errors import ApiError
from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.hour_target import HourTarget
from apps.api.models.shift import Shift
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.staff_role import StaffRole
from apps.api.models.store import Store
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers.availability import (
    _validate_no_hard_contradiction,
    create_availability,
)
from apps.api.routers.rota_recommendations import (
    _TargetBounds,
    _build_availability_map,
    _pick_candidate,
    _pick_candidate_result,
    create_rota_recommendation_draft_detail,
)
from apps.api.routers.shifts import _is_available_for_shift
from apps.api.schemas.availability import AvailabilityCreate
from apps.api.services.declared_availability import (
    AvailabilityExclusionCause,
    acquire_availability_write_lock,
    availability_entries_overlap,
    evaluate_declared_availability,
    has_hard_contradiction,
)


PASSWORD = "password123"
EMPLOYEE_PASSWORD = "employee-pass-123"


def _future_monday(days_ahead: int = 14) -> date:
    target = date.today() + timedelta(days=days_ahead)
    return target - timedelta(days=target.weekday())


WEEK_START = _future_monday()
SHIFT_DATE = WEEK_START + timedelta(days=1)


def _entry(
    availability_type: str,
    *,
    start: time | None = None,
    end: time | None = None,
    source: str | None = "employee",
    entry_date: date = SHIFT_DATE,
    user_id: uuid.UUID | None = None,
    store_id: uuid.UUID | None = None,
) -> AvailabilityEntry:
    return AvailabilityEntry(
        tenant_id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        store_id=store_id,
        week_start=WEEK_START,
        date=entry_date,
        start_time=start,
        end_time=end,
        type=availability_type,
        source=source,
    )


def _shift(
    *,
    start_hour: int = 9,
    end_hour: int = 17,
    end_day_offset: int = 0,
    required_role: str | None = None,
    tenant_id: uuid.UUID | None = None,
    store_id: uuid.UUID | None = None,
) -> Shift:
    return Shift(
        tenant_id=tenant_id or uuid.uuid4(),
        store_id=store_id or uuid.uuid4(),
        start_at=datetime.combine(SHIFT_DATE, time(start_hour), tzinfo=timezone.utc),
        end_at=datetime.combine(
            SHIFT_DATE + timedelta(days=end_day_offset),
            time(end_hour),
            tzinfo=timezone.utc,
        ),
        required_role=required_role,
        status="scheduled",
    )


def test_full_containment_is_required_and_positive_windows_do_not_stitch() -> None:
    shift = _shift()
    partial = evaluate_declared_availability(
        [_entry("available", start=time(9), end=time(12))],
        shift,
    )
    contained = evaluate_declared_availability(
        [_entry("available", start=time(8), end=time(18))],
        shift,
    )
    stitched = evaluate_declared_availability(
        [
            _entry("available", start=time(9), end=time(12)),
            _entry("available", start=time(12), end=time(17)),
        ],
        shift,
    )

    assert partial == evaluate_declared_availability([], shift)
    assert partial.exclusion_cause == AvailabilityExclusionCause.NO_DECLARATION
    assert contained.eligible is True
    assert stitched.eligible is False


def test_negative_and_soft_windows_apply_by_overlap_and_compose() -> None:
    result = evaluate_declared_availability(
        [
            _entry("available"),
            _entry("preferred_off", start=time(12), end=time(13)),
            _entry("unavailable", start=time(12), end=time(13)),
        ],
        _shift(),
    )

    assert result.eligible is False
    assert result.preferred_off is True
    assert result.exclusion_cause == AvailabilityExclusionCause.SAME_SOURCE_CONFLICT

    preferred_only = evaluate_declared_availability(
        [_entry("available"), _entry("preferred_off", start=time(12), end=time(13))],
        _shift(),
    )
    assert preferred_only.eligible is True
    assert preferred_only.preferred_off is True


def test_preferred_off_requires_a_containing_hard_positive_for_eligibility() -> None:
    shift = _shift()

    covered = evaluate_declared_availability(
        [
            _entry("available", start=time(9), end=time(17)),
            _entry("preferred_off", start=time(12), end=time(13)),
        ],
        shift,
    )
    preference_only = evaluate_declared_availability(
        [_entry("preferred_off", start=time(12), end=time(13))],
        shift,
    )
    partial_positive = evaluate_declared_availability(
        [
            _entry("available", start=time(9), end=time(12)),
            _entry("preferred_off", start=time(12), end=time(13)),
        ],
        shift,
    )

    assert covered.eligible is True
    assert covered.preferred_off is True
    assert preference_only.eligible is False
    assert preference_only.preferred_off is True
    assert preference_only.exclusion_cause == AvailabilityExclusionCause.NO_DECLARATION
    assert partial_positive.eligible is False
    assert partial_positive.preferred_off is True
    assert partial_positive.exclusion_cause == AvailabilityExclusionCause.NO_DECLARATION


def test_half_open_adjacency_and_full_day_overlap() -> None:
    morning = _entry("available", start=time(9), end=time(12))
    afternoon = _entry("unavailable", start=time(12), end=time(17))
    full_day = _entry("preferred_off")

    assert availability_entries_overlap(morning, afternoon) is False
    assert availability_entries_overlap(full_day, morning) is True


def test_cross_midnight_shift_fails_closed_even_with_full_day_availability() -> None:
    result = evaluate_declared_availability(
        [_entry("available")],
        _shift(start_hour=22, end_hour=6, end_day_offset=1),
    )

    assert result.eligible is False
    assert result.exclusion_cause == AvailabilityExclusionCause.CROSS_MIDNIGHT_UNSUPPORTED


def test_no_declaration_and_explicit_unavailable_are_distinct() -> None:
    no_declaration = evaluate_declared_availability([], _shift())
    unavailable = evaluate_declared_availability([_entry("unavailable")], _shift())

    assert no_declaration.eligible is unavailable.eligible is False
    assert no_declaration.exclusion_cause == AvailabilityExclusionCause.NO_DECLARATION
    assert unavailable.exclusion_cause == AvailabilityExclusionCause.UNAVAILABLE


def test_available_extra_has_the_same_eligibility_as_available() -> None:
    available = evaluate_declared_availability([_entry("available")], _shift())
    available_extra = evaluate_declared_availability([_entry("available_extra")], _shift())

    assert available == available_extra


def test_cross_source_conflict_is_order_and_timestamp_independent() -> None:
    available = _entry("available", source="admin")
    unavailable = _entry("unavailable", source="employee")
    available.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    unavailable.created_at = datetime.now(timezone.utc) - timedelta(hours=1)

    first = evaluate_declared_availability([available, unavailable], _shift())
    available.created_at, unavailable.created_at = unavailable.created_at, available.created_at
    second = evaluate_declared_availability([unavailable, available], _shift())

    assert first == second
    assert first.exclusion_cause == AvailabilityExclusionCause.SOURCE_CONFLICT
    assert first.would_be_eligible_without_source_conflict is True


def test_historical_same_source_and_null_source_conflicts_fail_closed_distinctly() -> None:
    same_source = evaluate_declared_availability(
        [_entry("available", source="admin"), _entry("unavailable", source="admin")],
        _shift(),
    )
    unknown = evaluate_declared_availability(
        [_entry("available", source=None), _entry("unavailable", source="admin")],
        _shift(),
    )
    lone_null_negative = evaluate_declared_availability(
        [_entry("unavailable", source=None)],
        _shift(),
    )

    assert same_source.exclusion_cause == AvailabilityExclusionCause.SAME_SOURCE_CONFLICT
    assert unknown.exclusion_cause == AvailabilityExclusionCause.UNKNOWN_PROVENANCE
    assert lone_null_negative.exclusion_cause == AvailabilityExclusionCause.UNAVAILABLE


def test_read_time_contradictions_are_scoped_to_their_intersection_with_shift() -> None:
    entries = [
        _entry("available", start=time(9), end=time(17), source="admin"),
        _entry("available", start=time(18), end=time(20), source="admin"),
        _entry("unavailable", start=time(18, 30), end=time(19), source="admin"),
    ]

    morning = evaluate_declared_availability(entries, _shift())
    evening = evaluate_declared_availability(
        entries,
        _shift(start_hour=18, end_hour=19),
    )

    assert morning.eligible is True
    assert evening.exclusion_cause == AvailabilityExclusionCause.SAME_SOURCE_CONFLICT


def _candidate_entry(user_id: uuid.UUID, availability_type: str) -> AvailabilityEntry:
    return _entry(availability_type, user_id=user_id)


def _candidate_entries(
    user_id: uuid.UUID,
    availability_type: str,
) -> list[AvailabilityEntry]:
    entries = [_candidate_entry(user_id, availability_type)]
    if availability_type == "preferred_off":
        entries.insert(0, _candidate_entry(user_id, "available"))
    return entries


def _pick(
    first_id: uuid.UUID,
    second_id: uuid.UUID,
    *,
    first_type: str,
    second_type: str,
    first_hours: float = 0.0,
    second_hours: float = 0.0,
    first_bounds: _TargetBounds | None = None,
    second_bounds: _TargetBounds | None = None,
):
    target_map = {}
    if first_bounds is not None:
        target_map[first_id] = first_bounds
    if second_bounds is not None:
        target_map[second_id] = second_bounds
    return _pick_candidate(
        shift=_shift(),
        candidate_user_ids=[first_id, second_id],
        projected_hours={first_id: first_hours, second_id: second_hours},
        target_map=target_map,
        availability_map={
            first_id: _candidate_entries(first_id, first_type),
            second_id: _candidate_entries(second_id, second_type),
        },
        role_map={first_id: set(), second_id: set()},
    )


def test_d056_ranking_examples_and_available_extra_equality() -> None:
    alice = uuid.UUID(int=1)
    bob = uuid.UUID(int=2)
    under_cap = _TargetBounds(None, 40, "staff_profile", None)
    over_soft_cap = _TargetBounds(None, 4, "staff_profile", None)

    assert _pick(
        alice,
        bob,
        first_type="available",
        second_type="preferred_off",
        first_bounds=under_cap,
        second_bounds=under_cap,
    ).user_id == alice
    assert _pick(
        alice,
        bob,
        first_type="available",
        second_type="preferred_off",
        first_bounds=over_soft_cap,
        second_bounds=under_cap,
    ).user_id == bob

    only_preferred = _pick_candidate(
        shift=_shift(),
        candidate_user_ids=[bob],
        projected_hours={bob: 0.0},
        target_map={},
        availability_map={
            bob: [
                _candidate_entry(bob, "available"),
                _candidate_entry(bob, "preferred_off"),
            ]
        },
        role_map={bob: set()},
    )
    assert only_preferred is not None
    assert "preferred_off" in only_preferred.reason_parts

    equal_first = _pick(
        alice,
        bob,
        first_type="available_extra",
        second_type="available",
    )
    equal_second = _pick(
        alice,
        bob,
        first_type="available",
        second_type="available_extra",
    )
    assert equal_first.user_id == equal_second.user_id == alice


def test_selected_candidate_reason_parts_are_additive() -> None:
    user_id = uuid.uuid4()
    selected = _pick_candidate(
        shift=_shift(),
        candidate_user_ids=[user_id],
        projected_hours={user_id: 5.0},
        target_map={user_id: _TargetBounds(None, 4, "staff_profile", None)},
        availability_map={
            user_id: [
                _candidate_entry(user_id, "available"),
                _candidate_entry(user_id, "preferred_off"),
            ]
        },
        role_map={user_id: set()},
    )

    assert selected is not None
    assert {"over_weekly_soft_cap", "preferred_off"}.issubset(selected.reason_parts)


def test_source_conflict_reason_is_causal_across_role_hours_and_availability() -> None:
    user_id = uuid.uuid4()
    entries = [
        _entry("available", source="admin", user_id=user_id),
        _entry("unavailable", source="employee", user_id=user_id),
    ]

    wrong_role = _pick_candidate_result(
        shift=_shift(required_role="manager"),
        candidate_user_ids=[user_id],
        projected_hours={user_id: 0.0},
        target_map={},
        availability_map={user_id: entries},
        role_map={user_id: {"crew"}},
    )
    hard_max = _pick_candidate_result(
        shift=_shift(),
        candidate_user_ids=[user_id],
        projected_hours={user_id: 5.0},
        target_map={user_id: _TargetBounds(None, 4, "hour_target", None)},
        availability_map={user_id: entries},
        role_map={user_id: set()},
    )
    partial_conflict = _pick_candidate_result(
        shift=_shift(),
        candidate_user_ids=[user_id],
        projected_hours={user_id: 0.0},
        target_map={},
        availability_map={
            user_id: [
                _entry(
                    "available",
                    start=time(9),
                    end=time(12),
                    source="admin",
                    user_id=user_id,
                ),
                _entry(
                    "unavailable",
                    start=time(10),
                    end=time(11),
                    source="employee",
                    user_id=user_id,
                ),
            ]
        },
        role_map={user_id: set()},
    )
    pure_conflict = _pick_candidate_result(
        shift=_shift(),
        candidate_user_ids=[user_id],
        projected_hours={user_id: 0.0},
        target_map={},
        availability_map={user_id: entries},
        role_map={user_id: set()},
    )

    assert wrong_role.source_conflict_was_sole_exclusion is False
    assert hard_max.source_conflict_was_sole_exclusion is False
    assert partial_conflict.source_conflict_was_sole_exclusion is False
    assert pure_conflict.source_conflict_was_sole_exclusion is True


def _persist_recommendation_case(
    test_session_local,
    *,
    entries: list[AvailabilityEntry],
    required_role: str | None = None,
    assigned_role: str | None = None,
    hard_max: int | None = None,
    weekly_soft_cap: Decimal | None = None,
) -> str:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    db = test_session_local()
    try:
        db.add(Tenant(id=tenant_id, name="Availability.1a recommendation tenant"))
        db.flush()
        db.add(
            User(
                id=user_id,
                email=f"availability-reason-{uuid.uuid4()}@example.com",
                hashed_password="not-used",
                active_tenant_id=tenant_id,
            )
        )
        db.add(
            Store(
                id=store_id,
                tenant_id=tenant_id,
                code=f"A1AR-{uuid.uuid4().hex[:10]}",
                name="Availability reason store",
                timezone="Europe/London",
            )
        )
        db.flush()
        db.add(TenantUser(tenant_id=tenant_id, user_id=user_id, role="member"))
        profile = StaffProfile(
            tenant_id=tenant_id,
            user_id=user_id,
            store_id=store_id,
            display_name="Availability reason candidate",
            is_active=True,
            weekly_working_hour_soft_cap=weekly_soft_cap,
        )
        db.add(profile)
        db.flush()
        if assigned_role is not None:
            db.add(
                StaffRole(
                    tenant_id=tenant_id,
                    staff_id=profile.id,
                    role=assigned_role,
                )
            )
        if hard_max is not None:
            db.add(
                HourTarget(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    store_id=store_id,
                    week_start=WEEK_START,
                    min_hours=0,
                    max_hours=hard_max,
                    target_hours=0,
                )
            )
        db.add(
            _shift(
                required_role=required_role,
                tenant_id=tenant_id,
                store_id=store_id,
            )
        )
        for entry in entries:
            entry.tenant_id = tenant_id
            entry.user_id = user_id
            entry.store_id = store_id
            db.add(entry)
        db.commit()

        detail = create_rota_recommendation_draft_detail(
            db,
            tenant_id=tenant_id,
            actor_user_id=user_id,
            store_id=store_id,
            week_start=WEEK_START,
        )
        assert len(detail.items) == 1
        assert detail.items[0].reason is not None
        return detail.items[0].reason
    finally:
        db.close()


@pytest.mark.parametrize(
    ("case", "expected_reason"),
    [
        ("pure_conflict", "source_conflict"),
        ("role", "no_eligible_candidate"),
        ("hard_max", "no_eligible_candidate"),
        ("partial", "no_eligible_candidate"),
    ],
)
def test_persisted_unfilled_reason_is_causal(
    test_session_local,
    case: str,
    expected_reason: str,
) -> None:
    entries = [_entry("available", source="admin"), _entry("unavailable", source="employee")]
    kwargs = {}
    if case == "role":
        kwargs = {"required_role": "manager", "assigned_role": "crew"}
    elif case == "hard_max":
        kwargs = {"hard_max": 4}
    elif case == "partial":
        entries = [
            _entry("available", start=time(9), end=time(12), source="admin"),
            _entry("unavailable", start=time(10), end=time(11), source="employee"),
        ]

    reason = _persist_recommendation_case(
        test_session_local,
        entries=entries,
        **kwargs,
    )
    assert reason == expected_reason


def test_persisted_selected_reason_composes_soft_cap_and_preferred_off(
    test_session_local,
) -> None:
    reason = _persist_recommendation_case(
        test_session_local,
        entries=[_entry("available"), _entry("preferred_off")],
        weekly_soft_cap=Decimal("4.00"),
    )

    assert {"over_weekly_soft_cap", "preferred_off"}.issubset(reason.split(","))


def test_preferred_off_does_not_supply_source_conflict_counterfactual(
    test_session_local,
) -> None:
    reason = _persist_recommendation_case(
        test_session_local,
        entries=[
            _entry("available", start=time(9), end=time(12), source="employee"),
            _entry("preferred_off", start=time(12), end=time(13), source="employee"),
            _entry("unavailable", start=time(10), end=time(11), source="admin"),
        ],
    )

    assert reason == "no_eligible_candidate"


@pytest.fixture
def test_session_local(tmp_path):
    db_path = tmp_path / "test_availability_1a.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield session_local
    finally:
        engine.dispose()


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, prefix: str) -> dict:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert registered.status_code == 201, registered.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    return {
        "id": uuid.UUID(registered.json()["id"]),
        "tenant_id": uuid.UUID(registered.json()["active_tenant_id"]),
        "token": login.json()["access_token"],
    }


def _create_store(client: TestClient, admin: dict) -> str:
    response = client.post(
        "/api/v1/stores",
        json={
            "code": f"A1A-{uuid.uuid4().hex[:10]}",
            "name": "Availability 1a",
            "timezone": "Europe/London",
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_tenant_member(client: TestClient, admin: dict, username: str) -> dict:
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": f"availability-1a-{username}-{uuid.uuid4()}@example.com",
            "password": PASSWORD,
            "full_name": f"Availability 1a {username}",
            "role": "member",
        },
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_staff(
    client: TestClient,
    admin: dict,
    *,
    store_id: str,
    username: str,
    employee_account: bool = False,
) -> dict:
    user = _create_tenant_member(client, admin, username)
    payload = {
        "user_id": user["id"],
        "store_id": store_id,
        "display_name": f"Availability 1a {username}",
        "is_active": True,
    }
    if employee_account:
        payload.update(
            {
                "employee_username": username,
                "employee_password": EMPLOYEE_PASSWORD,
            }
        )
    response = client.post(
        "/api/v1/staff",
        json=payload,
        headers=_auth(admin["token"]),
    )
    assert response.status_code == 201, response.text
    return {"user": user, "profile": response.json()}


def _employee_login(client: TestClient, *, store_id: str, username: str) -> str:
    response = client.post(
        "/api/v1/auth/employee/login",
        json={
            "site_id": store_id,
            "username": username,
            "password": EMPLOYEE_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _availability_payload(
    availability_type: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    return {
        "week_start": WEEK_START.isoformat(),
        "date": SHIFT_DATE.isoformat(),
        "start_time": start,
        "end_time": end,
        "type": availability_type,
    }


def test_generic_availability_writer_rejects_same_source_contradiction(
    client: TestClient,
) -> None:
    member = _register_and_login(client, "availability-1a-generic")

    available = client.post(
        "/api/v1/availability",
        json=_availability_payload("available", start="09:00", end="12:00"),
        headers=_auth(member["token"]),
    )
    adjacent = client.post(
        "/api/v1/availability",
        json=_availability_payload("unavailable", start="12:00", end="17:00"),
        headers=_auth(member["token"]),
    )
    preferred = client.post(
        "/api/v1/availability",
        json=_availability_payload("preferred_off", start="09:00", end="12:00"),
        headers=_auth(member["token"]),
    )
    contradiction = client.post(
        "/api/v1/availability",
        json=_availability_payload("unavailable", start="11:00", end="13:00"),
        headers=_auth(member["token"]),
    )
    available_extra_contradiction = client.post(
        "/api/v1/availability",
        json=_availability_payload("available_extra", start="13:00", end="14:00"),
        headers=_auth(member["token"]),
    )

    assert available.status_code == adjacent.status_code == preferred.status_code == 201
    assert contradiction.status_code == 409
    assert contradiction.json()["error"]["code"] == "AVAILABILITY_CONTRADICTION"
    assert available_extra_contradiction.status_code == 409


def test_admin_replace_week_rejects_contradiction_before_destructive_replace(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "availability-1a-admin")
    store_id = _create_store(client, admin)
    staff = _create_staff(client, admin, store_id=store_id, username="admin-writer")
    endpoint = f"/api/v1/staff/{staff['user']['id']}/availability/week"

    allowed = client.put(
        endpoint,
        json={
            "week_start": WEEK_START.isoformat(),
            "entries": [
                {
                    "date": SHIFT_DATE.isoformat(),
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "type": "available",
                },
                {
                    "date": SHIFT_DATE.isoformat(),
                    "start_time": "12:00",
                    "end_time": "17:00",
                    "type": "unavailable",
                },
                {
                    "date": SHIFT_DATE.isoformat(),
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "type": "preferred_off",
                },
            ],
        },
        headers=_auth(admin["token"]),
    )
    rejected = client.put(
        endpoint,
        json={
            "week_start": WEEK_START.isoformat(),
            "entries": [
                {"date": SHIFT_DATE.isoformat(), "type": "available"},
                {
                    "date": SHIFT_DATE.isoformat(),
                    "start_time": "10:00",
                    "end_time": "11:00",
                    "type": "unavailable",
                },
            ],
        },
        headers=_auth(admin["token"]),
    )

    assert allowed.status_code == 200, allowed.text
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "AVAILABILITY_CONTRADICTION"
    assert len(allowed.json()["items"]) == 3
    db = test_session_local()
    try:
        rows = db.scalars(
            select(AvailabilityEntry).where(
                AvailabilityEntry.tenant_id == admin["tenant_id"],
                AvailabilityEntry.user_id == uuid.UUID(staff["user"]["id"]),
                AvailabilityEntry.week_start == WEEK_START,
            )
        ).all()
        assert {row.type for row in rows} == {"available", "unavailable", "preferred_off"}
    finally:
        db.close()


def test_employee_writer_rejects_contradiction_and_retains_overnight_guard(
    client: TestClient,
) -> None:
    admin = _register_and_login(client, "availability-1a-employee")
    store_id = _create_store(client, admin)
    _create_staff(
        client,
        admin,
        store_id=store_id,
        username="employee-writer",
        employee_account=True,
    )
    token = _employee_login(client, store_id=store_id, username="employee-writer")

    available = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("available", start="09:00", end="12:00"),
        headers=_auth(token),
    )
    adjacent = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("unavailable", start="12:00", end="17:00"),
        headers=_auth(token),
    )
    preferred = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("preferred_off", start="09:00", end="12:00"),
        headers=_auth(token),
    )
    contradiction = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("unavailable", start="11:00", end="13:00"),
        headers=_auth(token),
    )
    overnight = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("available", start="22:00", end="06:00"),
        headers=_auth(token),
    )

    assert available.status_code == adjacent.status_code == preferred.status_code == 201
    assert contradiction.status_code == 409
    assert contradiction.json()["error"]["code"] == "AVAILABILITY_CONTRADICTION"
    assert overnight.status_code == 422


def test_cross_source_conflict_is_reachable_after_admin_replace_then_employee_write(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "availability-1a-production-conflict")
    store_id = _create_store(client, admin)
    staff = _create_staff(
        client,
        admin,
        store_id=store_id,
        username="production-conflict",
        employee_account=True,
    )
    admin_write = client.put(
        f"/api/v1/staff/{staff['user']['id']}/availability/week",
        json={
            "week_start": WEEK_START.isoformat(),
            "entries": [{"date": SHIFT_DATE.isoformat(), "type": "unavailable"}],
        },
        headers=_auth(admin["token"]),
    )
    token = _employee_login(client, store_id=store_id, username="production-conflict")
    employee_write = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("available"),
        headers=_auth(token),
    )

    assert admin_write.status_code == 200, admin_write.text
    assert employee_write.status_code == 201, employee_write.text
    db = test_session_local()
    try:
        rows = list(
            db.scalars(
                select(AvailabilityEntry).where(
                    AvailabilityEntry.tenant_id == admin["tenant_id"],
                    AvailabilityEntry.user_id == uuid.UUID(staff["user"]["id"]),
                    AvailabilityEntry.date == SHIFT_DATE,
                )
            ).all()
        )
        result = evaluate_declared_availability(rows, _shift())
        assert {row.source for row in rows} == {"admin", "employee"}
        assert result.exclusion_cause == AvailabilityExclusionCause.SOURCE_CONFLICT
    finally:
        db.close()

    control = evaluate_declared_availability(
        [_entry("available", source="admin"), _entry("preferred_off", source="employee")],
        _shift(),
    )
    assert control.eligible is True
    assert control.preferred_off is True


def test_shift_side_consumer_uses_declared_availability_evaluator(test_session_local) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    shift = _shift(tenant_id=tenant_id, store_id=store_id)

    def check(entries: list[AvailabilityEntry]) -> bool:
        db = test_session_local()
        try:
            db.query(AvailabilityEntry).delete()
            for entry in entries:
                entry.tenant_id = tenant_id
                entry.user_id = user_id
                entry.store_id = store_id
                db.add(entry)
            db.commit()
            return _is_available_for_shift(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                shift=shift,
            )
        finally:
            db.close()

    assert check([_entry("unavailable")]) is False
    # D059 corrects the previous preferred_off-only eligibility assertion.
    assert check([_entry("available"), _entry("preferred_off")]) is True
    assert check([_entry("preferred_off")]) is False
    assert check([]) is False
    assert check(
        [_entry("available", source="admin"), _entry("unavailable", source="employee")]
    ) is False


def test_postgresql_concurrent_same_source_writes_cannot_commit_a_contradiction() -> None:
    """SQLite cannot prove the PostgreSQL advisory-lock boundary."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+")):
        pytest.skip("PostgreSQL-backed Availability.1a concurrency integration test")

    engine = create_engine(database_url, poolclass=NullPool)
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-backed Availability.1a concurrency integration test")
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    with session_local() as db:
        db.add(Tenant(id=tenant_id, name="Availability.1a concurrency tenant"))
        db.flush()
        db.add(
            User(
                id=user_id,
                email=f"availability-concurrency-{uuid.uuid4()}@example.com",
                hashed_password="not-used",
                active_tenant_id=tenant_id,
            )
        )
        db.flush()
        db.add(
            TenantUser(
                id=membership_id,
                tenant_id=tenant_id,
                user_id=user_id,
                role="member",
            )
        )
        db.commit()

    barrier = Barrier(2)

    def write(availability_type: str) -> str:
        with session_local() as db:
            membership = db.get(TenantUser, membership_id)
            assert membership is not None
            barrier.wait(timeout=10)
            try:
                create_availability(
                    AvailabilityCreate(
                        week_start=WEEK_START,
                        date=SHIFT_DATE,
                        type=availability_type,
                    ),
                    membership,
                    db,
                )
            except ApiError as exc:
                db.rollback()
                return exc.code
            return "committed"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = sorted(
                future.result(timeout=30)
                for future in [
                    executor.submit(write, "available"),
                    executor.submit(write, "unavailable"),
                ]
            )

        assert outcomes == ["AVAILABILITY_CONTRADICTION", "committed"]
        with session_local() as db:
            rows = db.scalars(
                select(AvailabilityEntry).where(
                    AvailabilityEntry.tenant_id == tenant_id,
                    AvailabilityEntry.user_id == user_id,
                )
            ).all()
            assert len(rows) == 1
    finally:
        with session_local() as db:
            db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
            db.execute(delete(AvailabilityEntry).where(AvailabilityEntry.tenant_id == tenant_id))
            db.execute(delete(TenantUser).where(TenantUser.tenant_id == tenant_id))
            user = db.get(User, user_id)
            if user is not None:
                user.active_tenant_id = None
                db.flush()
            db.execute(delete(User).where(User.id == user_id))
            db.execute(delete(Tenant).where(Tenant.id == tenant_id))
            db.commit()
        engine.dispose()


def test_coverage_1bb_t1a_overnight_negative_changes_exclusion_cause() -> None:
    result = evaluate_declared_availability(
        [_entry("unavailable", start=time(22), end=time(6))],
        _shift(start_hour=22, end_hour=23),
    )

    assert result.eligible is False
    assert result.exclusion_cause == AvailabilityExclusionCause.UNAVAILABLE


def test_coverage_1bb_t1b_overnight_negative_changes_eligibility() -> None:
    result = evaluate_declared_availability(
        [
            _entry("available", source="admin"),
            _entry(
                "unavailable",
                start=time(22),
                end=time(6),
                source="employee",
            ),
        ],
        _shift(start_hour=22, end_hour=23),
    )

    assert result.eligible is False
    assert result.exclusion_cause == AvailabilityExclusionCause.SOURCE_CONFLICT
    assert result.would_be_eligible_without_source_conflict is True


def test_coverage_1bb_t2_evaluator_admits_prior_day_entries() -> None:
    prior_day = SHIFT_DATE
    shift_date = prior_day + timedelta(days=1)
    shift = Shift(
        tenant_id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        start_at=datetime.combine(shift_date, time(0, 30), tzinfo=timezone.utc),
        end_at=datetime.combine(shift_date, time(4), tzinfo=timezone.utc),
        status="scheduled",
    )
    result = evaluate_declared_availability(
        [
            _entry(
                "unavailable",
                start=time(22),
                end=time(6),
                source="admin",
                entry_date=prior_day,
            ),
            _entry(
                "available",
                start=time(0),
                end=time(6),
                source="employee",
                entry_date=shift_date,
            ),
        ],
        shift,
    )

    assert result.eligible is False
    assert result.exclusion_cause == AvailabilityExclusionCause.SOURCE_CONFLICT
    assert result.would_be_eligible_without_source_conflict is True


def test_coverage_1bb_t3_shift_loader_admits_prior_week_sunday(
    test_session_local,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    sunday = WEEK_START - timedelta(days=1)
    shift = Shift(
        tenant_id=tenant_id,
        store_id=store_id,
        start_at=datetime.combine(WEEK_START, time(0, 30), tzinfo=timezone.utc),
        end_at=datetime.combine(WEEK_START, time(4), tzinfo=timezone.utc),
        status="scheduled",
    )
    prior_negative = _entry(
        "unavailable",
        start=time(22),
        end=time(6),
        entry_date=sunday,
        user_id=user_id,
        store_id=store_id,
    )
    prior_negative.tenant_id = tenant_id
    prior_negative.week_start = WEEK_START - timedelta(days=7)
    current_positive = _entry(
        "available",
        start=time(0),
        end=time(6),
        entry_date=WEEK_START,
        user_id=user_id,
        store_id=store_id,
    )
    current_positive.tenant_id = tenant_id

    db = test_session_local()
    try:
        db.add_all([prior_negative, current_positive])
        db.commit()

        assert (
            _is_available_for_shift(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                shift=shift,
            )
            is False
        )
    finally:
        db.close()


def test_coverage_1bb_t4_recommendation_loader_admits_prior_week_sunday_with_scope(
    test_session_local,
) -> None:
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    other_store_id = uuid.uuid4()
    sunday = WEEK_START - timedelta(days=1)

    target = _entry(
        "unavailable",
        start=time(22),
        end=time(6),
        entry_date=sunday,
        user_id=user_id,
        store_id=store_id,
    )
    target.tenant_id = tenant_id
    target.week_start = WEEK_START - timedelta(days=7)
    other_tenant = _entry(
        "unavailable",
        start=time(22),
        end=time(6),
        entry_date=sunday,
        user_id=user_id,
        store_id=store_id,
    )
    other_tenant.tenant_id = other_tenant_id
    other_tenant.week_start = WEEK_START - timedelta(days=7)
    other_store = _entry(
        "preferred_off",
        start=time(23),
        end=time(5),
        entry_date=sunday,
        user_id=user_id,
        store_id=other_store_id,
    )
    other_store.tenant_id = tenant_id
    other_store.week_start = WEEK_START - timedelta(days=7)

    db = test_session_local()
    try:
        db.add_all([target, other_tenant, other_store])
        db.commit()

        availability_map = _build_availability_map(
            db,
            tenant_id=tenant_id,
            week_start=WEEK_START,
            store_id=store_id,
            candidate_user_ids=[user_id],
        )

        assert [entry.id for entry in availability_map[user_id]] == [target.id]
        assert other_tenant.id not in {
            entry.id for entries in availability_map.values() for entry in entries
        }
        assert other_store.id not in {
            entry.id for entries in availability_map.values() for entry in entries
        }
    finally:
        db.close()


def test_coverage_1bb_t4b_recommendation_loader_upper_bound_is_inclusive(
    test_session_local,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    next_monday = WEEK_START + timedelta(days=7)

    in_range = _entry(
        "available",
        start=time(0),
        end=time(6),
        entry_date=next_monday,
        user_id=user_id,
        store_id=store_id,
    )
    in_range.tenant_id = tenant_id
    in_range.week_start = next_monday

    out_of_range = _entry(
        "available",
        start=time(0),
        end=time(6),
        entry_date=next_monday + timedelta(days=1),
        user_id=user_id,
        store_id=store_id,
    )
    out_of_range.tenant_id = tenant_id
    out_of_range.week_start = next_monday

    db = test_session_local()
    try:
        db.add_all([in_range, out_of_range])
        db.commit()

        availability_map = _build_availability_map(
            db,
            tenant_id=tenant_id,
            week_start=WEEK_START,
            store_id=store_id,
            candidate_user_ids=[user_id],
        )
        loaded = {entry.id for entry in availability_map[user_id]}

        assert in_range.id in loaded
        assert out_of_range.id not in loaded
    finally:
        db.close()


def test_coverage_1bb_t5_cross_date_hard_contradiction_is_detected() -> None:
    sunday = WEEK_START - timedelta(days=1)

    assert (
        has_hard_contradiction(
            [
                _entry(
                    "available",
                    start=time(22),
                    end=time(6),
                    entry_date=sunday,
                ),
                _entry(
                    "unavailable",
                    start=time(1),
                    end=time(3),
                    entry_date=WEEK_START,
                ),
            ]
        )
        is True
    )


def test_coverage_1bb_t6_adjacent_date_rows_remain_non_contradictory() -> None:
    next_day = SHIFT_DATE + timedelta(days=1)

    assert (
        has_hard_contradiction(
            [
                _entry("available", start=time(9), end=time(17)),
                _entry(
                    "unavailable",
                    start=time(9),
                    end=time(17),
                    entry_date=next_day,
                ),
            ]
        )
        is False
    )
    assert (
        has_hard_contradiction(
            [
                _entry("available"),
                _entry("unavailable", entry_date=next_day),
            ]
        )
        is False
    )


def test_coverage_1bb_t7_cross_midnight_branch_remains_fail_closed() -> None:
    result = evaluate_declared_availability(
        [
            _entry("available"),
            _entry("preferred_off", start=time(22, 30), end=time(23)),
        ],
        _shift(start_hour=22, end_hour=6, end_day_offset=1),
    )

    assert result.eligible is False
    assert result.exclusion_cause == AvailabilityExclusionCause.CROSS_MIDNIGHT_UNSUPPORTED
    assert result.preferred_off is True


def test_coverage_1bb_t7b_cross_midnight_branch_ignores_next_day_preference() -> None:
    result = evaluate_declared_availability(
        [
            _entry("available"),
            _entry(
                "preferred_off",
                start=time(1),
                end=time(3),
                entry_date=SHIFT_DATE + timedelta(days=1),
            ),
        ],
        _shift(start_hour=22, end_hour=6, end_day_offset=1),
    )

    assert result.eligible is False
    assert result.exclusion_cause == AvailabilityExclusionCause.CROSS_MIDNIGHT_UNSUPPORTED
    assert result.preferred_off is False


def test_coverage_1bb_t8_generic_writer_checks_prior_day_contradictions(
    client: TestClient,
    test_session_local,
) -> None:
    member = _register_and_login(client, "coverage-1bb-generic-writer")
    db = test_session_local()
    try:
        db.add(
            AvailabilityEntry(
                tenant_id=member["tenant_id"],
                user_id=member["id"],
                week_start=WEEK_START,
                date=SHIFT_DATE - timedelta(days=1),
                start_time=time(22),
                end_time=time(6),
                type="available",
                source="employee",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/availability",
        json=_availability_payload("unavailable", start="01:00", end="03:00"),
        headers=_auth(member["token"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AVAILABILITY_CONTRADICTION"


def test_coverage_1bb_t9_employee_writer_checks_prior_day_contradictions(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "coverage-1bb-employee-writer")
    store_id = _create_store(client, admin)
    staff = _create_staff(
        client,
        admin,
        store_id=store_id,
        username="coverage-1bb-employee",
        employee_account=True,
    )
    token = _employee_login(
        client,
        store_id=store_id,
        username="coverage-1bb-employee",
    )
    db = test_session_local()
    try:
        db.add(
            AvailabilityEntry(
                tenant_id=admin["tenant_id"],
                user_id=uuid.UUID(staff["user"]["id"]),
                store_id=uuid.UUID(store_id),
                site_id=uuid.UUID(store_id),
                employee_account_id=uuid.UUID(
                    staff["profile"]["employee_account_id"]
                ),
                week_start=WEEK_START,
                date=SHIFT_DATE - timedelta(days=1),
                start_time=time(22),
                end_time=time(6),
                type="available",
                source="employee",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/employee/me/availability",
        json=_availability_payload("unavailable", start="01:00", end="03:00"),
        headers=_auth(token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AVAILABILITY_CONTRADICTION"


def test_coverage_1bb_t10_admin_replace_week_checks_retained_prior_sunday(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "coverage-1bb-t10-admin")
    store_id = _create_store(client, admin)
    staff = _create_staff(client, admin, store_id=store_id, username="t10-admin")
    staff_user_id = uuid.UUID(staff["user"]["id"])

    db = test_session_local()
    try:
        db.add(
            AvailabilityEntry(
                tenant_id=admin["tenant_id"],
                user_id=staff_user_id,
                store_id=uuid.UUID(store_id),
                site_id=uuid.UUID(store_id),
                week_start=WEEK_START - timedelta(days=7),
                date=WEEK_START - timedelta(days=1),
                start_time=time(22),
                end_time=time(6),
                type="available",
                source="admin",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.put(
        f"/api/v1/staff/{staff_user_id}/availability/week",
        json={
            "week_start": WEEK_START.isoformat(),
            "entries": [
                {
                    "date": WEEK_START.isoformat(),
                    "start_time": "01:00",
                    "end_time": "03:00",
                    "type": "unavailable",
                }
            ],
        },
        headers=_auth(admin["token"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AVAILABILITY_CONTRADICTION"


def test_coverage_1bb_t11_admin_replace_week_resave_does_not_self_conflict(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "coverage-1bb-t11-admin")
    store_id = _create_store(client, admin)
    staff = _create_staff(client, admin, store_id=store_id, username="t11-admin")
    staff_user_id = uuid.UUID(staff["user"]["id"])
    endpoint = f"/api/v1/staff/{staff_user_id}/availability/week"

    def payload(availability_type: str) -> dict:
        return {
            "week_start": WEEK_START.isoformat(),
            "entries": [
                {
                    "date": WEEK_START.isoformat(),
                    "start_time": "09:00",
                    "end_time": "17:00",
                    "type": availability_type,
                }
            ],
        }

    first = client.put(endpoint, json=payload("available"), headers=_auth(admin["token"]))
    second = client.put(endpoint, json=payload("unavailable"), headers=_auth(admin["token"]))

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    db = test_session_local()
    try:
        rows = db.scalars(
            select(AvailabilityEntry).where(
                AvailabilityEntry.user_id == staff_user_id,
                AvailabilityEntry.date == WEEK_START,
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].type == "unavailable"
        assert rows[0].source == "admin"
    finally:
        db.close()


def test_coverage_1bb_t12_admin_replace_week_ignores_employee_neighbour(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "coverage-1bb-t12-admin")
    store_id = _create_store(client, admin)
    staff = _create_staff(client, admin, store_id=store_id, username="t12-admin")
    staff_user_id = uuid.UUID(staff["user"]["id"])

    db = test_session_local()
    try:
        db.add(
            AvailabilityEntry(
                tenant_id=admin["tenant_id"],
                user_id=staff_user_id,
                store_id=uuid.UUID(store_id),
                site_id=uuid.UUID(store_id),
                week_start=WEEK_START - timedelta(days=7),
                date=WEEK_START - timedelta(days=1),
                start_time=time(22),
                end_time=time(6),
                type="available",
                source="employee",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.put(
        f"/api/v1/staff/{staff_user_id}/availability/week",
        json={
            "week_start": WEEK_START.isoformat(),
            "entries": [
                {
                    "date": WEEK_START.isoformat(),
                    "start_time": "01:00",
                    "end_time": "03:00",
                    "type": "unavailable",
                }
            ],
        },
        headers=_auth(admin["token"]),
    )

    assert response.status_code == 200, response.text


def test_coverage_1bb_t13_concurrent_adjacent_date_writes_are_serialized() -> None:
    """SQLite cannot prove the PostgreSQL advisory-lock boundary."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+")):
        pytest.skip("PostgreSQL-backed Coverage.1bB-2a concurrency integration test")

    engine = create_engine(database_url, poolclass=NullPool)
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-backed Coverage.1bB-2a concurrency integration test")
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    first_date = _future_monday()
    with session_local() as db:
        db.add(Tenant(id=tenant_id, name="Coverage.1bB-2a concurrency tenant"))
        db.flush()
        db.add(
            User(
                id=user_id,
                email=f"coverage-1bb-t13-{uuid.uuid4()}@example.com",
                hashed_password="not-used",
                active_tenant_id=tenant_id,
            )
        )
        db.flush()
        db.add(
            TenantUser(
                id=membership_id,
                tenant_id=tenant_id,
                user_id=user_id,
                role="member",
            )
        )
        db.commit()

    barrier = Barrier(2)

    def write(
        entry_date: date,
        availability_type: str,
        start_time: time,
        end_time: time,
    ) -> str:
        with session_local() as db:
            membership = db.get(TenantUser, membership_id)
            assert membership is not None
            entry = AvailabilityEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                week_start=first_date,
                date=entry_date,
                start_time=start_time,
                end_time=end_time,
                type=availability_type,
                source="employee",
            )
            barrier.wait(timeout=10)
            try:
                acquire_availability_write_lock(
                    db,
                    writer_identity="employee",
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                same_source_entries = db.scalars(
                    select(AvailabilityEntry).where(
                        AvailabilityEntry.tenant_id == tenant_id,
                        AvailabilityEntry.user_id == user_id,
                        AvailabilityEntry.date >= entry_date - timedelta(days=1),
                        AvailabilityEntry.date <= entry_date + timedelta(days=1),
                        AvailabilityEntry.source == "employee",
                    )
                ).all()
                _validate_no_hard_contradiction([*same_source_entries, entry])
                db.add(entry)
                db.flush()
                db.commit()
            except ApiError as exc:
                db.rollback()
                return exc.code
            return "committed"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = sorted(
                future.result(timeout=30)
                for future in [
                    executor.submit(
                        write,
                        first_date,
                        "available",
                        time(22),
                        time(6),
                    ),
                    executor.submit(
                        write,
                        first_date + timedelta(days=1),
                        "unavailable",
                        time(1),
                        time(3),
                    ),
                ]
            )

        assert outcomes == ["AVAILABILITY_CONTRADICTION", "committed"]
        with session_local() as db:
            rows = db.scalars(
                select(AvailabilityEntry).where(
                    AvailabilityEntry.tenant_id == tenant_id,
                    AvailabilityEntry.user_id == user_id,
                )
            ).all()
            assert len(rows) == 1
    finally:
        with session_local() as db:
            db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
            db.execute(delete(AvailabilityEntry).where(AvailabilityEntry.tenant_id == tenant_id))
            db.execute(delete(TenantUser).where(TenantUser.tenant_id == tenant_id))
            user = db.get(User, user_id)
            if user is not None:
                user.active_tenant_id = None
                db.flush()
            db.execute(delete(User).where(User.id == user_id))
            db.execute(delete(Tenant).where(Tenant.id == tenant_id))
            db.commit()
        engine.dispose()
