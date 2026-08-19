import hashlib
import struct
import uuid
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.generation_run import GenerationRun
from apps.api.models.rota_recommendation_draft import RotaRecommendationDraft
from apps.api.models.shift import Shift
from apps.api.models.site_work_area import SiteWorkArea
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.routers.rota_recommendations import (
    discard_rota_recommendation_draft_without_commit,
)
from apps.api.schemas.rota import GenerateWeekRequest, GenerateWeekResponse

router = APIRouter()


def _normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = role.strip().lower()
    return normalized or None


def _week_bounds(week_start) -> tuple[datetime, datetime]:
    start_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=7)
    return start_at, end_at


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_store_or_404(db: Session, *, tenant_id, store_id) -> Store:
    store = db.scalar(
        select(Store).where(
            Store.id == store_id,
            Store.tenant_id == tenant_id,
        )
    )
    if store is None:
        raise ApiError(
            status_code=404,
            code="STORE_NOT_FOUND",
            message="Store not found in active tenant",
        )
    return store


def _acquire_generation_lock(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    week_start,
) -> None:
    """Serialize one tenant/site/week generation key for this transaction.

    PostgreSQL uses a deterministic transaction-scoped advisory lock. SQLite's
    test dialect has no equivalent; its normal database write serialization is
    the minimal fallback and is not evidence of PostgreSQL concurrency safety.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    lock_material = f"{tenant_id}:{store_id}:{week_start.isoformat()}".encode()
    lock_key_1, lock_key_2 = struct.unpack(">ii", hashlib.sha256(lock_material).digest()[:8])
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key_1, :lock_key_2)"),
        {"lock_key_1": lock_key_1, "lock_key_2": lock_key_2},
    )


def _occurrence_key(
    *,
    template_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    required_role: str | None,
    work_area_id: uuid.UUID | None,
) -> tuple[uuid.UUID, datetime, datetime, str | None, uuid.UUID | None]:
    return (
        template_id,
        _as_utc(start_at),
        _as_utc(end_at),
        required_role,
        work_area_id,
    )


def _validate_templates(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    templates: list[CoverageTemplate],
) -> None:
    for template in templates:
        if template.required_headcount < 1 or template.end_time == template.start_time:
            raise ApiError(
                status_code=422,
                code="COVERAGE_TEMPLATE_INVALID",
                message="An active coverage template has an invalid time window or headcount",
            )
        if template.work_area_id is None:
            continue
        work_area = db.scalar(
            select(SiteWorkArea.id).where(
                SiteWorkArea.id == template.work_area_id,
                SiteWorkArea.tenant_id == tenant_id,
                SiteWorkArea.store_id == store_id,
                SiteWorkArea.is_active.is_(True),
            )
        )
        if work_area is None:
            raise ApiError(
                status_code=422,
                code="COVERAGE_TEMPLATE_WORK_AREA_INVALID",
                message="An active coverage template references an inactive or foreign work area",
            )


@router.post("/generate-week", response_model=GenerateWeekResponse)
def generate_week_shifts(
    payload: GenerateWeekRequest,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> GenerateWeekResponse:
    _get_store_or_404(db, tenant_id=membership.tenant_id, store_id=payload.store_id)
    _acquire_generation_lock(
        db,
        tenant_id=membership.tenant_id,
        store_id=payload.store_id,
        week_start=payload.week_start,
    )

    templates = list(
        db.scalars(
            select(CoverageTemplate)
            .where(
                CoverageTemplate.tenant_id == membership.tenant_id,
                CoverageTemplate.store_id == payload.store_id,
                CoverageTemplate.is_active.is_(True),
            )
            .with_for_update()
        ).all()
    )

    week_start_at, week_end_at = _week_bounds(payload.week_start)
    existing_shifts = list(
        db.scalars(
            select(Shift)
            .where(
                Shift.tenant_id == membership.tenant_id,
                Shift.store_id == payload.store_id,
                Shift.start_at >= week_start_at,
                Shift.start_at < week_end_at,
            )
            .with_for_update()
        ).all()
    )
    active_draft = db.scalar(
        select(RotaRecommendationDraft)
        .where(
            RotaRecommendationDraft.tenant_id == membership.tenant_id,
            RotaRecommendationDraft.store_id == payload.store_id,
            RotaRecommendationDraft.week_start == payload.week_start,
            RotaRecommendationDraft.status == "draft",
        )
        .with_for_update()
    )

    if not templates:
        raise ApiError(
            status_code=409,
            code="NO_ACTIVE_COVERAGE_TEMPLATES",
            message="No active coverage templates exist for this store",
        )
    _validate_templates(
        db,
        tenant_id=membership.tenant_id,
        store_id=payload.store_id,
        templates=templates,
    )

    occurrences: list[tuple[CoverageTemplate, datetime, datetime, str | None]] = []
    for day_offset in range(7):
        current_date = payload.week_start + timedelta(days=day_offset)
        for template in templates:
            if template.day_of_week != current_date.weekday():
                continue
            end_date = current_date
            if template.end_time < template.start_time:
                end_date += timedelta(days=1)
            occurrences.append(
                (
                    template,
                    datetime.combine(current_date, template.start_time, tzinfo=timezone.utc),
                    datetime.combine(end_date, template.end_time, tzinfo=timezone.utc),
                    _normalize_role(template.required_role),
                )
            )

    replaceable = [
        shift
        for shift in existing_shifts
        if shift.source == "demand_generation"
        and shift.status == "scheduled"
        and shift.assigned_user_id is None
        and shift.published_at is None
        and not shift.role_override
        and not shift.availability_override
    ]
    replaceable_ids = {shift.id for shift in replaceable}
    preserved_active = [
        shift
        for shift in existing_shifts
        if shift.status == "scheduled" and shift.id not in replaceable_ids
    ]

    occurrence_keys = {
        _occurrence_key(
            template_id=template.id,
            start_at=start_at,
            end_at=end_at,
            required_role=required_role,
            work_area_id=template.work_area_id,
        )
        for template, start_at, end_at, required_role in occurrences
    }
    matching_preserved: dict[
        tuple[uuid.UUID, datetime, datetime, str | None, uuid.UUID | None],
        list[Shift],
    ] = {key: [] for key in occurrence_keys}
    kept_conflict_count = 0
    for shift in preserved_active:
        if shift.source in {"manual", "legacy_untracked"}:
            kept_conflict_count += 1
            continue
        if shift.source != "demand_generation" or shift.source_coverage_template_id is None:
            kept_conflict_count += 1
            continue
        key = _occurrence_key(
            template_id=shift.source_coverage_template_id,
            start_at=shift.start_at,
            end_at=shift.end_at,
            required_role=_normalize_role(shift.required_role),
            work_area_id=shift.work_area_id,
        )
        if key not in matching_preserved:
            kept_conflict_count += 1
            continue
        matching_preserved[key].append(shift)

    kept_matching_count = 0
    shifts_to_create: list[tuple[CoverageTemplate, datetime, datetime, str | None]] = []
    for template, start_at, end_at, required_role in occurrences:
        key = _occurrence_key(
            template_id=template.id,
            start_at=start_at,
            end_at=end_at,
            required_role=required_role,
            work_area_id=template.work_area_id,
        )
        matching_count = len(matching_preserved[key])
        satisfying_kept = min(template.required_headcount, matching_count)
        kept_matching_count += satisfying_kept
        kept_conflict_count += max(matching_count - template.required_headcount, 0)
        shifts_to_create.extend(
            (template, start_at, end_at, required_role)
            for _ in range(template.required_headcount - satisfying_kept)
        )

    generation_run = GenerationRun(
        tenant_id=membership.tenant_id,
        store_id=payload.store_id,
        week_start=payload.week_start,
        status="completed",
        created_count=len(shifts_to_create),
        replaced_count=len(replaceable),
        kept_matching_count=kept_matching_count,
        kept_conflict_count=kept_conflict_count,
        generated_by_user_id=membership.user_id,
    )
    db.add(generation_run)
    db.flush()

    superseded_at = datetime.now(timezone.utc)
    for shift in replaceable:
        shift.status = "cancelled"
        shift.superseded_at = superseded_at
        shift.superseded_by_generation_run_id = generation_run.id
        db.add(
            AuditLog(
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                action="supersede",
                entity_type="shift",
                entity_id=str(shift.id),
            )
        )

    new_shifts = [
        Shift(
            tenant_id=membership.tenant_id,
            store_id=payload.store_id,
            assigned_user_id=None,
            start_at=start_at,
            end_at=end_at,
            required_role=required_role,
            status="scheduled",
            published_at=None,
            published_by_user_id=None,
            source="demand_generation",
            generation_run_id=generation_run.id,
            source_coverage_template_id=template.id,
            work_area_id=template.work_area_id,
        )
        for template, start_at, end_at, required_role in shifts_to_create
    ]
    db.add_all(new_shifts)
    db.flush()
    for shift in new_shifts:
        db.add(
            AuditLog(
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                action="create",
                entity_type="shift",
                entity_id=str(shift.id),
            )
        )

    if active_draft is not None:
        discard_rota_recommendation_draft_without_commit(
            db,
            tenant_id=membership.tenant_id,
            actor_user_id=membership.user_id,
            draft=active_draft,
        )
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="generate_week",
            entity_type="generation_run",
            entity_id=str(generation_run.id),
        )
    )
    db.commit()

    return GenerateWeekResponse(
        created_count=generation_run.created_count,
        replaced_count=generation_run.replaced_count,
        kept_matching_count=generation_run.kept_matching_count,
        kept_conflict_count=generation_run.kept_conflict_count,
        generation_run_id=generation_run.id,
        draft_discarded=active_draft is not None,
    )
