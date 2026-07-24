from collections.abc import Generator
from datetime import date, datetime, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.base import Base
from apps.api.db.deps import get_db
from apps.api.main import app
from apps.api.models.audit_log import AuditLog
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.generation_run import GenerationRun
from apps.api.models.rota_recommendation_draft import RotaRecommendationDraft
from apps.api.models.shift import Shift
from apps.api.models.tenant_user import TenantUser


PASSWORD = "password123"
WEEK_START = "2026-08-03"


@pytest.fixture
def test_session_local(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'coverage_1a.db'}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
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


def _register_and_login(client: TestClient, prefix: str) -> dict:
    email = f"{prefix}-{uuid.uuid4()}@example.com"
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert logged_in.status_code == 200
    return {
        "id": registered.json()["id"],
        "tenant_id": registered.json()["active_tenant_id"],
        "token": logged_in.json()["access_token"],
    }


def _auth(admin: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin['token']}"}


def _create_store(client: TestClient, admin: dict, code: str) -> str:
    response = client.post(
        "/api/v1/stores",
        json={"code": f"{code}-{uuid.uuid4().hex[:8]}", "name": code, "timezone": "UTC"},
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_work_area(client: TestClient, admin: dict, store_id: str, label: str = "Kitchen") -> dict:
    response = client.post(
        f"/api/v1/sites/{store_id}/work-areas",
        json={"label": label},
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _create_template(
    client: TestClient,
    admin: dict,
    store_id: str,
    *,
    headcount: int = 1,
    start_time: str = "09:00:00",
    end_time: str = "17:00:00",
    role: str | None = " Crew ",
    work_area_id: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 0,
            "start_time": start_time,
            "end_time": end_time,
            "required_headcount": headcount,
            "required_role": role,
            "work_area_id": work_area_id,
            "display_label": "Monday demand",
        },
        headers=_auth(admin),
    )
    assert response.status_code == 201
    return response.json()


def _generate(client: TestClient, admin: dict, store_id: str, week_start: str = WEEK_START):
    return client.post(
        "/api/v1/rota/generate-week",
        json={"store_id": store_id, "week_start": week_start},
        headers=_auth(admin),
    )


def _store_shifts(test_session_local, store_id: str) -> list[Shift]:
    with test_session_local() as db:
        return list(
            db.scalars(
                select(Shift)
                .where(Shift.store_id == uuid.UUID(store_id))
                .order_by(Shift.created_at.asc(), Shift.id.asc())
            ).all()
        )


def test_work_area_validation_isolation_and_soft_deactivation_guards(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-area")
    other = _register_and_login(client, "c1a-area-other")
    store_id = _create_store(client, admin, "C1A-AREA")

    blank = client.post(
        f"/api/v1/sites/{store_id}/work-areas",
        json={"label": "   "},
        headers=_auth(admin),
    )
    assert blank.status_code == 422

    area = _create_work_area(client, admin, store_id, "  Kitchen  ")
    assert area["label"] == "Kitchen"
    duplicate = client.post(
        f"/api/v1/sites/{store_id}/work-areas",
        json={"label": "kItChEn"},
        headers=_auth(admin),
    )
    assert duplicate.status_code == 409
    second_area = _create_work_area(client, admin, store_id, "Back office")
    duplicate_patch = client.patch(
        f"/api/v1/sites/{store_id}/work-areas/{second_area['id']}",
        json={"label": "KITCHEN"},
        headers=_auth(admin),
    )
    assert duplicate_patch.status_code == 409

    forbidden_patch = client.patch(
        f"/api/v1/sites/{store_id}/work-areas/{area['id']}",
        json={"label": "Prep", "is_active": False, "tenant_id": other["tenant_id"]},
        headers=_auth(admin),
    )
    assert forbidden_patch.status_code == 422
    cross_tenant = client.get(
        f"/api/v1/sites/{store_id}/work-areas",
        headers=_auth(other),
    )
    assert cross_tenant.status_code == 404

    template = _create_template(client, admin, store_id, work_area_id=area["id"])
    blocked = client.delete(
        f"/api/v1/sites/{store_id}/work-areas/{area['id']}",
        headers=_auth(admin),
    )
    assert blocked.status_code == 409

    generated = _generate(client, admin, store_id)
    assert generated.status_code == 200
    shift_id = _store_shifts(test_session_local, store_id)[0].id
    deactivated_template = client.delete(
        f"/api/v1/coverage-templates/{template['id']}",
        headers=_auth(admin),
    )
    assert deactivated_template.status_code == 200
    assert deactivated_template.json()["is_active"] is False
    deactivated_area = client.delete(
        f"/api/v1/sites/{store_id}/work-areas/{area['id']}",
        headers=_auth(admin),
    )
    assert deactivated_area.status_code == 200
    assert deactivated_area.json()["is_active"] is False

    with test_session_local() as db:
        historical_shift = db.get(Shift, shift_id)
        assert historical_shift is not None
        assert historical_shift.source_coverage_template_id == uuid.UUID(template["id"])
        assert historical_shift.work_area_id == uuid.UUID(area["id"])

    inactive_create = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_id,
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
            "work_area_id": area["id"],
        },
        headers=_auth(admin),
    )
    assert inactive_create.status_code == 422
    active_without_area = _create_template(client, admin, store_id, start_time="10:00:00")
    inactive_update = client.patch(
        f"/api/v1/coverage-templates/{active_without_area['id']}",
        json={"work_area_id": area["id"]},
        headers=_auth(admin),
    )
    assert inactive_update.status_code == 422

    with test_session_local() as db:
        membership = db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == uuid.UUID(admin["tenant_id"]),
                TenantUser.user_id == uuid.UUID(admin["id"]),
            )
        )
        assert membership is not None
        membership.role = "member"
        db.commit()
    member_read = client.get(
        f"/api/v1/sites/{store_id}/work-areas",
        headers=_auth(admin),
    )
    assert member_read.status_code == 403


def test_work_area_reference_is_rejected_across_sites_in_same_tenant(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-area-cross-site")
    store_a_id = _create_store(client, admin, "C1A-AREA-SITE-A")
    store_b_id = _create_store(client, admin, "C1A-AREA-SITE-B")
    area_a = _create_work_area(client, admin, store_a_id, "Site A kitchen")

    invalid_create = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_b_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
            "work_area_id": area_a["id"],
        },
        headers=_auth(admin),
    )
    assert invalid_create.status_code == 422
    assert invalid_create.json()["error"]["code"] == "COVERAGE_TEMPLATE_WORK_AREA_INVALID"

    template_b = _create_template(client, admin, store_b_id)
    invalid_update = client.patch(
        f"/api/v1/coverage-templates/{template_b['id']}",
        json={"work_area_id": area_a["id"]},
        headers=_auth(admin),
    )
    assert invalid_update.status_code == 422
    assert invalid_update.json()["error"]["code"] == "COVERAGE_TEMPLATE_WORK_AREA_INVALID"
    with test_session_local() as db:
        persisted = db.get(CoverageTemplate, uuid.UUID(template_b["id"]))
        assert persisted is not None
        assert persisted.work_area_id is None


def test_work_area_reference_is_rejected_across_tenants(
    client: TestClient,
    test_session_local,
) -> None:
    admin_a = _register_and_login(client, "c1a-area-tenant-a")
    admin_b = _register_and_login(client, "c1a-area-tenant-b")
    store_a_id = _create_store(client, admin_a, "C1A-AREA-TENANT-A")
    store_b_id = _create_store(client, admin_b, "C1A-AREA-TENANT-B")
    area_b = _create_work_area(client, admin_b, store_b_id, "Tenant B kitchen")

    invalid_create = client.post(
        "/api/v1/coverage-templates",
        json={
            "store_id": store_a_id,
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "required_headcount": 1,
            "work_area_id": area_b["id"],
        },
        headers=_auth(admin_a),
    )
    assert invalid_create.status_code == 422
    assert invalid_create.json()["error"] == {
        "code": "COVERAGE_TEMPLATE_WORK_AREA_INVALID",
        "message": "Work area must be active and belong to the same tenant and site",
        "details": None,
    }
    assert area_b["id"] not in invalid_create.text
    assert admin_b["tenant_id"] not in invalid_create.text

    template_a = _create_template(client, admin_a, store_a_id)
    invalid_update = client.patch(
        f"/api/v1/coverage-templates/{template_a['id']}",
        json={"work_area_id": area_b["id"]},
        headers=_auth(admin_a),
    )
    assert invalid_update.status_code == 422
    assert invalid_update.json()["error"] == invalid_create.json()["error"]
    assert area_b["id"] not in invalid_update.text
    assert admin_b["tenant_id"] not in invalid_update.text
    with test_session_local() as db:
        persisted = db.get(CoverageTemplate, uuid.UUID(template_a["id"]))
        assert persisted is not None
        assert persisted.work_area_id is None


def test_generated_shift_and_run_provenance_and_counts(client: TestClient, test_session_local) -> None:
    admin = _register_and_login(client, "c1a-provenance")
    store_id = _create_store(client, admin, "C1A-PROV")
    area = _create_work_area(client, admin, store_id, "Front counter")
    template = _create_template(client, admin, store_id, headcount=2, work_area_id=area["id"])

    response = _generate(client, admin, store_id)
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "created_count": 2,
        "replaced_count": 0,
        "kept_matching_count": 0,
        "kept_conflict_count": 0,
        "generation_run_id": body["generation_run_id"],
        "draft_discarded": False,
    }

    with test_session_local() as db:
        run = db.get(GenerationRun, uuid.UUID(body["generation_run_id"]))
        assert run is not None
        assert (run.created_count, run.replaced_count, run.kept_matching_count, run.kept_conflict_count) == (
            2,
            0,
            0,
            0,
        )
        shifts = db.scalars(select(Shift).where(Shift.store_id == uuid.UUID(store_id))).all()
        assert len(shifts) == 2
        assert all(shift.source == "demand_generation" for shift in shifts)
        assert all(shift.generation_run_id == run.id for shift in shifts)
        assert all(shift.source_coverage_template_id == uuid.UUID(template["id"]) for shift in shifts)
        assert all(shift.work_area_id == uuid.UUID(area["id"]) for shift in shifts)
        assert all(shift.required_role == "crew" for shift in shifts)


@pytest.mark.parametrize(
    "protection",
    ["assigned", "published", "role_override", "availability_override"],
)
def test_protected_matching_generated_shift_satisfies_demand_without_duplication(
    client: TestClient,
    test_session_local,
    protection: str,
) -> None:
    admin = _register_and_login(client, f"c1a-{protection}")
    store_id = _create_store(client, admin, f"C1A-{protection}")
    _create_template(client, admin, store_id)
    assert _generate(client, admin, store_id).status_code == 200

    with test_session_local() as db:
        shift = db.scalar(select(Shift).where(Shift.store_id == uuid.UUID(store_id)))
        assert shift is not None
        if protection == "assigned":
            shift.assigned_user_id = uuid.UUID(admin["id"])
        elif protection == "published":
            shift.published_at = datetime.now(timezone.utc)
            shift.published_by_user_id = uuid.UUID(admin["id"])
        elif protection == "role_override":
            shift.role_override = True
        else:
            shift.availability_override = True
        db.commit()

    regenerated = _generate(client, admin, store_id)
    assert regenerated.status_code == 200
    assert regenerated.json()["created_count"] == 0
    assert regenerated.json()["replaced_count"] == 0
    assert regenerated.json()["kept_matching_count"] == 1
    assert regenerated.json()["kept_conflict_count"] == 0
    assert len([shift for shift in _store_shifts(test_session_local, store_id) if shift.status == "scheduled"]) == 1


def test_preserved_mismatch_is_conflict_and_new_occurrence_is_created(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-mismatch")
    store_id = _create_store(client, admin, "C1A-MISMATCH")
    template = _create_template(client, admin, store_id)
    assert _generate(client, admin, store_id).status_code == 200
    with test_session_local() as db:
        shift = db.scalar(select(Shift).where(Shift.store_id == uuid.UUID(store_id)))
        assert shift is not None
        shift.assigned_user_id = uuid.UUID(admin["id"])
        db.commit()
    patched = client.patch(
        f"/api/v1/coverage-templates/{template['id']}",
        json={"start_time": "10:00:00", "end_time": "18:00:00"},
        headers=_auth(admin),
    )
    assert patched.status_code == 200

    regenerated = _generate(client, admin, store_id)
    assert regenerated.status_code == 200
    assert regenerated.json()["created_count"] == 1
    assert regenerated.json()["kept_matching_count"] == 0
    assert regenerated.json()["kept_conflict_count"] == 1
    assert len([shift for shift in _store_shifts(test_session_local, store_id) if shift.status == "scheduled"]) == 2


def test_headcount_reduction_reports_excess_preserved_matching_shifts(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-reduce")
    store_id = _create_store(client, admin, "C1A-REDUCE")
    template = _create_template(client, admin, store_id, headcount=3)
    assert _generate(client, admin, store_id).status_code == 200
    with test_session_local() as db:
        shifts = db.scalars(select(Shift).where(Shift.store_id == uuid.UUID(store_id))).all()
        for shift in shifts:
            shift.assigned_user_id = uuid.UUID(admin["id"])
        db.commit()
    patched = client.patch(
        f"/api/v1/coverage-templates/{template['id']}",
        json={"required_headcount": 1},
        headers=_auth(admin),
    )
    assert patched.status_code == 200

    regenerated = _generate(client, admin, store_id)
    assert regenerated.status_code == 200
    assert regenerated.json()["created_count"] == 0
    assert regenerated.json()["kept_matching_count"] == 1
    assert regenerated.json()["kept_conflict_count"] == 2


def test_manual_and_legacy_shifts_are_preserved_but_do_not_satisfy_demand(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-untracked")
    store_id = _create_store(client, admin, "C1A-UNTRACKED")
    _create_template(client, admin, store_id)
    manual = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": f"{WEEK_START}T09:00:00Z",
            "end_at": f"{WEEK_START}T17:00:00Z",
            "required_role": "crew",
        },
        headers=_auth(admin),
    )
    assert manual.status_code == 201
    with test_session_local() as db:
        db.add(
            Shift(
                tenant_id=uuid.UUID(admin["tenant_id"]),
                store_id=uuid.UUID(store_id),
                start_at=datetime(2026, 8, 3, 9, tzinfo=timezone.utc),
                end_at=datetime(2026, 8, 3, 17, tzinfo=timezone.utc),
                required_role="crew",
                source="legacy_untracked",
                status="scheduled",
            )
        )
        db.commit()

    generated = _generate(client, admin, store_id)
    assert generated.status_code == 200
    assert generated.json()["created_count"] == 1
    assert generated.json()["replaced_count"] == 0
    assert generated.json()["kept_conflict_count"] == 2
    sources = sorted(shift.source for shift in _store_shifts(test_session_local, store_id))
    assert sources == ["demand_generation", "legacy_untracked", "manual"]


def test_cancelled_history_and_other_store_or_week_are_untouched(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-history")
    store_id = _create_store(client, admin, "C1A-HISTORY")
    other_store_id = _create_store(client, admin, "C1A-HISTORY-OTHER")
    _create_template(client, admin, store_id)
    first = _generate(client, admin, store_id)
    assert first.status_code == 200
    original_superseded_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    with test_session_local() as db:
        historical = db.scalar(select(Shift).where(Shift.store_id == uuid.UUID(store_id)))
        assert historical is not None
        historical.status = "cancelled"
        historical.superseded_at = original_superseded_at
        historical.superseded_by_generation_run_id = uuid.UUID(first.json()["generation_run_id"])
        other_store_shift = Shift(
            tenant_id=uuid.UUID(admin["tenant_id"]),
            store_id=uuid.UUID(other_store_id),
            start_at=datetime(2026, 8, 3, 9, tzinfo=timezone.utc),
            end_at=datetime(2026, 8, 3, 17, tzinfo=timezone.utc),
            source="manual",
            status="scheduled",
        )
        other_week_shift = Shift(
            tenant_id=uuid.UUID(admin["tenant_id"]),
            store_id=uuid.UUID(store_id),
            start_at=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
            end_at=datetime(2026, 8, 10, 17, tzinfo=timezone.utc),
            source="manual",
            status="scheduled",
        )
        db.add_all([other_store_shift, other_week_shift])
        db.commit()
        historical_id = historical.id
        other_store_shift_id = other_store_shift.id
        other_week_shift_id = other_week_shift.id

    regenerated = _generate(client, admin, store_id)
    assert regenerated.status_code == 200
    assert regenerated.json()["created_count"] == 1
    assert regenerated.json()["replaced_count"] == 0
    assert regenerated.json()["kept_conflict_count"] == 0
    with test_session_local() as db:
        historical = db.get(Shift, historical_id)
        assert historical is not None
        assert historical.superseded_at == original_superseded_at.replace(tzinfo=None)
        assert db.get(Shift, other_store_shift_id).status == "scheduled"
        assert db.get(Shift, other_week_shift_id).status == "scheduled"


def test_generation_discards_active_recommendation_draft_atomically(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-draft")
    store_id = _create_store(client, admin, "C1A-DRAFT")
    _create_template(client, admin, store_id)
    assert _generate(client, admin, store_id).status_code == 200
    draft = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": WEEK_START},
        headers=_auth(admin),
    )
    assert draft.status_code == 201

    regenerated = _generate(client, admin, store_id)
    assert regenerated.status_code == 200
    assert regenerated.json()["draft_discarded"] is True
    assert regenerated.json()["replaced_count"] == 1
    with test_session_local() as db:
        persisted = db.get(RotaRecommendationDraft, uuid.UUID(draft.json()["draft_id"]))
        assert persisted is not None
        assert persisted.status == "discarded"


def test_generation_discards_only_the_active_draft_for_the_regenerated_week(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-draft-week-boundary")
    store_id = _create_store(client, admin, "C1A-DRAFT-WEEK")
    _create_template(client, admin, store_id)

    assert _generate(client, admin, store_id, "2026-08-03").status_code == 200
    draft_a = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": "2026-08-03"},
        headers=_auth(admin),
    )
    assert draft_a.status_code == 201

    assert _generate(client, admin, store_id, "2026-08-10").status_code == 200
    draft_b = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": "2026-08-10"},
        headers=_auth(admin),
    )
    assert draft_b.status_code == 201

    regenerated_a = _generate(client, admin, store_id, "2026-08-03")
    assert regenerated_a.status_code == 200
    assert regenerated_a.json()["draft_discarded"] is True
    with test_session_local() as db:
        persisted_a = db.get(
            RotaRecommendationDraft,
            uuid.UUID(draft_a.json()["draft_id"]),
        )
        persisted_b = db.get(
            RotaRecommendationDraft,
            uuid.UUID(draft_b.json()["draft_id"]),
        )
        assert persisted_a is not None
        assert persisted_b is not None
        assert persisted_a.status == "discarded"
        assert persisted_b.status == "draft"


def test_active_draft_partial_unique_index_enforces_tenant_site_week_boundary(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-draft-unique")
    store_id = _create_store(client, admin, "C1A-DRAFT-UNIQUE")
    tenant_id = uuid.UUID(admin["tenant_id"])
    actor_id = uuid.UUID(admin["id"])
    store_uuid = uuid.UUID(store_id)

    with test_session_local() as db:
        original = RotaRecommendationDraft(
            tenant_id=tenant_id,
            store_id=store_uuid,
            week_start=date(2026, 8, 3),
            status="draft",
            created_by_user_id=actor_id,
        )
        db.add(original)
        db.commit()

        db.add(
            RotaRecommendationDraft(
                tenant_id=tenant_id,
                store_id=store_uuid,
                week_start=date(2026, 8, 3),
                status="draft",
                created_by_user_id=actor_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        other_week = RotaRecommendationDraft(
            tenant_id=tenant_id,
            store_id=store_uuid,
            week_start=date(2026, 8, 10),
            status="draft",
            created_by_user_id=actor_id,
        )
        db.add(other_week)
        db.commit()
        assert other_week.status == "draft"

        persisted_original = db.get(RotaRecommendationDraft, original.id)
        assert persisted_original is not None
        persisted_original.status = "discarded"
        db.commit()

        replacement = RotaRecommendationDraft(
            tenant_id=tenant_id,
            store_id=store_uuid,
            week_start=date(2026, 8, 3),
            status="draft",
            created_by_user_id=actor_id,
        )
        db.add(replacement)
        db.commit()
        assert replacement.status == "draft"


def test_no_active_templates_changes_nothing_and_does_not_discard_draft(
    client: TestClient,
    test_session_local,
) -> None:
    admin = _register_and_login(client, "c1a-empty")
    store_id = _create_store(client, admin, "C1A-EMPTY")
    template = _create_template(client, admin, store_id)
    assert _generate(client, admin, store_id).status_code == 200
    draft = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": WEEK_START},
        headers=_auth(admin),
    )
    assert draft.status_code == 201
    assert client.delete(
        f"/api/v1/coverage-templates/{template['id']}",
        headers=_auth(admin),
    ).status_code == 200
    with test_session_local() as db:
        run_count = db.scalar(select(func.count()).select_from(GenerationRun))
        audit_count = db.scalar(select(func.count()).select_from(AuditLog))
        shift = db.scalar(select(Shift).where(Shift.store_id == uuid.UUID(store_id)))
        assert shift is not None
        shift_id = shift.id

    failed = _generate(client, admin, store_id)
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "NO_ACTIVE_COVERAGE_TEMPLATES"
    with test_session_local() as db:
        assert db.scalar(select(func.count()).select_from(GenerationRun)) == run_count
        assert db.scalar(select(func.count()).select_from(AuditLog)) == audit_count
        assert db.get(Shift, shift_id).status == "scheduled"
        assert db.get(RotaRecommendationDraft, uuid.UUID(draft.json()["draft_id"])).status == "draft"


def test_forced_mid_operation_failure_rolls_back_all_generation_mutations(
    client: TestClient,
    test_session_local,
    monkeypatch,
) -> None:
    from apps.api.routers import rota as rota_router

    admin = _register_and_login(client, "c1a-rollback")
    store_id = _create_store(client, admin, "C1A-ROLLBACK")
    _create_template(client, admin, store_id)
    assert _generate(client, admin, store_id).status_code == 200
    draft = client.post(
        "/api/v1/rota-recommendations",
        json={"store_id": store_id, "week_start": WEEK_START},
        headers=_auth(admin),
    )
    assert draft.status_code == 201
    with test_session_local() as db:
        run_count = db.scalar(select(func.count()).select_from(GenerationRun))
        shift_count = db.scalar(select(func.count()).select_from(Shift))
        audit_count = db.scalar(select(func.count()).select_from(AuditLog))
        original_shift = db.scalar(select(Shift).where(Shift.store_id == uuid.UUID(store_id)))
        assert original_shift is not None
        original_shift_id = original_shift.id

    real_discard = rota_router.discard_rota_recommendation_draft_without_commit

    def discard_then_fail(*args, **kwargs):
        real_discard(*args, **kwargs)
        raise RuntimeError("forced Coverage.1a rollback")

    monkeypatch.setattr(
        rota_router,
        "discard_rota_recommendation_draft_without_commit",
        discard_then_fail,
    )
    with pytest.raises(RuntimeError, match="forced Coverage.1a rollback"):
        _generate(client, admin, store_id)

    with test_session_local() as db:
        assert db.scalar(select(func.count()).select_from(GenerationRun)) == run_count
        assert db.scalar(select(func.count()).select_from(Shift)) == shift_count
        assert db.scalar(select(func.count()).select_from(AuditLog)) == audit_count
        original_shift = db.get(Shift, original_shift_id)
        assert original_shift is not None
        assert original_shift.status == "scheduled"
        assert original_shift.superseded_at is None
        assert original_shift.superseded_by_generation_run_id is None
        assert db.get(RotaRecommendationDraft, uuid.UUID(draft.json()["draft_id"])).status == "draft"


def test_shift_create_and_update_reject_client_owned_provenance(client: TestClient) -> None:
    admin = _register_and_login(client, "c1a-server-owned")
    store_id = _create_store(client, admin, "C1A-SERVER")
    forged_create = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": f"{WEEK_START}T09:00:00Z",
            "end_at": f"{WEEK_START}T17:00:00Z",
            "source": "demand_generation",
            "generation_run_id": str(uuid.uuid4()),
            "source_coverage_template_id": str(uuid.uuid4()),
            "work_area_id": str(uuid.uuid4()),
            "superseded_at": f"{WEEK_START}T10:00:00Z",
            "superseded_by_generation_run_id": str(uuid.uuid4()),
        },
        headers=_auth(admin),
    )
    assert forged_create.status_code == 422

    created = client.post(
        "/api/v1/shifts",
        json={
            "store_id": store_id,
            "start_at": f"{WEEK_START}T09:00:00Z",
            "end_at": f"{WEEK_START}T17:00:00Z",
        },
        headers=_auth(admin),
    )
    assert created.status_code == 201
    forged_update = client.patch(
        f"/api/v1/shifts/{created.json()['id']}",
        json={"source": "legacy_untracked", "work_area_id": str(uuid.uuid4())},
        headers=_auth(admin),
    )
    assert forged_update.status_code == 422
