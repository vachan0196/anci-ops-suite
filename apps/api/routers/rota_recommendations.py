from dataclasses import dataclass
from datetime import date as date_type, datetime, time, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.core.deps import require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.hour_target import HourTarget
from apps.api.models.rota_recommendation_draft import RotaRecommendationDraft, RotaRecommendationItem
from apps.api.models.shift import Shift
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.staff_role import StaffRole
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.schemas.rota_recommendation import (
    ApplyResponse,
    DraftCreate,
    DraftCreateResponse,
    DraftDetailRead,
    DraftRead,
    DraftStatus,
    ItemRead,
)

router = APIRouter()

_AVAILABLE_TYPES = {"available", "available_extra"}


@dataclass
class _TargetBounds:
    min_hours: int | None
    max_hours: int | None
    target_hours: int | None


@dataclass
class _ScoredCandidate:
    user_id: uuid.UUID
    score: int
    projected_hours: float
    reason_parts: list[str]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = role.strip().lower()
    return normalized or None


def _week_bounds(week_start: date_type) -> tuple[datetime, datetime]:
    week_start_at = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    return week_start_at, week_start_at + timedelta(days=7)


def _week_start_for_datetime(dt: datetime) -> date_type:
    date_value = _as_utc(dt).date()
    return date_value - timedelta(days=date_value.weekday())


def _get_store_or_404(db: Session, *, tenant_id: uuid.UUID, store_id: uuid.UUID) -> Store:
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


def _get_draft_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> RotaRecommendationDraft:
    draft = db.scalar(
        select(RotaRecommendationDraft).where(
            RotaRecommendationDraft.id == draft_id,
            RotaRecommendationDraft.tenant_id == tenant_id,
        )
    )
    if draft is None:
        raise ApiError(
            status_code=404,
            code="ROTA_RECOMMENDATION_DRAFT_NOT_FOUND",
            message="Rota recommendation draft not found in active tenant",
        )
    return draft


def _shift_duration_hours(shift: Shift) -> float:
    start_at = _as_utc(shift.start_at)
    end_at = _as_utc(shift.end_at)
    duration = (end_at - start_at).total_seconds() / 3600
    return max(duration, 0.0)


def _build_target_map(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    week_start: date_type,
    candidate_user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, _TargetBounds]:
    if not candidate_user_ids:
        return {}

    targets = db.scalars(
        select(HourTarget).where(
            HourTarget.tenant_id == tenant_id,
            HourTarget.week_start == week_start,
            HourTarget.user_id.in_(candidate_user_ids),
            or_(
                HourTarget.store_id == store_id,
                HourTarget.store_id.is_(None),
            ),
        )
    ).all()

    selected: dict[uuid.UUID, tuple[int, _TargetBounds]] = {}
    for target in targets:
        priority = 2 if target.store_id == store_id else 1
        existing = selected.get(target.user_id)
        if existing is None or priority >= existing[0]:
            selected[target.user_id] = (
                priority,
                _TargetBounds(
                    min_hours=target.min_hours,
                    max_hours=target.max_hours,
                    target_hours=target.target_hours,
                ),
            )

    return {user_id: data[1] for user_id, data in selected.items()}


def _build_assigned_hours_map(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    week_start: date_type,
    candidate_user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, float]:
    assigned_hours = {user_id: 0.0 for user_id in candidate_user_ids}
    if not candidate_user_ids:
        return assigned_hours

    week_start_at, week_end_at = _week_bounds(week_start)
    assigned_shifts = db.scalars(
        select(Shift).where(
            Shift.tenant_id == tenant_id,
            Shift.store_id == store_id,
            Shift.status == "scheduled",
            Shift.assigned_user_id.in_(candidate_user_ids),
            Shift.start_at >= week_start_at,
            Shift.start_at < week_end_at,
        )
    ).all()

    for shift in assigned_shifts:
        if shift.assigned_user_id is None:
            continue
        assigned_hours[shift.assigned_user_id] = assigned_hours.get(shift.assigned_user_id, 0.0) + _shift_duration_hours(shift)

    return assigned_hours


def _availability_covers_shift(entries: list[AvailabilityEntry], shift: Shift) -> bool:
    shift_start = _as_utc(shift.start_at)
    shift_end = _as_utc(shift.end_at)
    shift_date = shift_start.date()
    shift_starts_and_ends_same_day = shift_start.date() == shift_end.date()
    shift_start_time = shift_start.time().replace(tzinfo=None)
    shift_end_time = shift_end.time().replace(tzinfo=None)

    for entry in entries:
        if entry.date != shift_date:
            continue
        if entry.start_time is None and entry.end_time is None:
            return True
        if not shift_starts_and_ends_same_day:
            continue
        if entry.start_time is not None and entry.end_time is not None:
            if entry.start_time <= shift_start_time and entry.end_time >= shift_end_time:
                return True
    return False


def _build_availability_map(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    week_start: date_type,
    store_id: uuid.UUID,
    candidate_user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[AvailabilityEntry]]:
    if not candidate_user_ids:
        return {}

    entries = db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.tenant_id == tenant_id,
            AvailabilityEntry.week_start == week_start,
            AvailabilityEntry.user_id.in_(candidate_user_ids),
            AvailabilityEntry.type.in_(tuple(_AVAILABLE_TYPES)),
            or_(
                AvailabilityEntry.store_id == store_id,
                AvailabilityEntry.store_id.is_(None),
            ),
        )
    ).all()

    by_user: dict[uuid.UUID, list[AvailabilityEntry]] = {user_id: [] for user_id in candidate_user_ids}
    for entry in entries:
        by_user.setdefault(entry.user_id, []).append(entry)
    return by_user


def _build_staff_role_map(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    candidate_user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, set[str]]:
    if not candidate_user_ids:
        return {}

    rows = db.execute(
        select(StaffProfile.user_id, StaffRole.role)
        .join(
            StaffRole,
            (StaffRole.tenant_id == StaffProfile.tenant_id)
            & (StaffRole.staff_id == StaffProfile.id),
        )
        .where(
            StaffProfile.tenant_id == tenant_id,
            StaffProfile.user_id.in_(candidate_user_ids),
        )
    ).all()

    role_map: dict[uuid.UUID, set[str]] = {user_id: set() for user_id in candidate_user_ids}
    for user_id, role in rows:
        role_map.setdefault(user_id, set()).add(role)
    return role_map


def _pick_candidate(
    *,
    shift: Shift,
    candidate_user_ids: list[uuid.UUID],
    projected_hours: dict[uuid.UUID, float],
    target_map: dict[uuid.UUID, _TargetBounds],
    availability_map: dict[uuid.UUID, list[AvailabilityEntry]],
    role_map: dict[uuid.UUID, set[str]],
) -> _ScoredCandidate | None:
    shift_hours = _shift_duration_hours(shift)
    required_role = _normalize_role(shift.required_role)
    scored: list[_ScoredCandidate] = []

    for user_id in candidate_user_ids:
        if required_role is not None and required_role not in role_map.get(user_id, set()):
            continue

        user_entries = availability_map.get(user_id, [])
        if not _availability_covers_shift(user_entries, shift):
            continue

        candidate_hours = projected_hours.get(user_id, 0.0)
        bounds = target_map.get(user_id)

        if bounds is not None and bounds.max_hours is not None:
            if candidate_hours + shift_hours > bounds.max_hours:
                continue

        score = 0
        reason_parts: list[str] = []
        if bounds is not None and bounds.min_hours is not None and candidate_hours < bounds.min_hours:
            score += 50
            reason_parts.append("below_min_hours")
        if bounds is not None and bounds.target_hours is not None and candidate_hours < bounds.target_hours:
            score += 30
            reason_parts.append("below_target_hours")

        scored.append(
            _ScoredCandidate(
                user_id=user_id,
                score=score,
                projected_hours=candidate_hours,
                reason_parts=reason_parts,
            )
        )

    if not scored:
        return None

    minimum_hours = min(candidate.projected_hours for candidate in scored)
    for candidate in scored:
        if abs(candidate.projected_hours - minimum_hours) < 1e-9:
            candidate.score += 10
            candidate.reason_parts.append("lowest_current_hours")

    scored.sort(
        key=lambda candidate: (
            -candidate.score,
            candidate.projected_hours,
            str(candidate.user_id),
        )
    )
    return scored[0]


def _read_draft_detail(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    draft: RotaRecommendationDraft,
) -> DraftDetailRead:
    items = db.scalars(
        select(RotaRecommendationItem)
        .where(
            RotaRecommendationItem.tenant_id == tenant_id,
            RotaRecommendationItem.draft_id == draft.id,
        )
        .order_by(RotaRecommendationItem.created_at.asc())
    ).all()
    return DraftDetailRead(
        draft=DraftRead.model_validate(draft),
        items=[ItemRead.model_validate(item) for item in items],
        shifts_considered=len(items),
        items_created=len(items),
        unfilled=sum(1 for item in items if item.proposed_user_id is None),
    )


def create_rota_recommendation_draft_detail(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    store_id: uuid.UUID,
    week_start: date_type,
    replace_existing_draft: bool = False,
) -> DraftDetailRead:
    _get_store_or_404(db, tenant_id=tenant_id, store_id=store_id)

    existing_active = db.scalars(
        select(RotaRecommendationDraft).where(
            RotaRecommendationDraft.tenant_id == tenant_id,
            RotaRecommendationDraft.store_id == store_id,
            RotaRecommendationDraft.week_start == week_start,
            RotaRecommendationDraft.status == "draft",
        )
    ).all()
    if existing_active and not replace_existing_draft:
        raise ApiError(
            status_code=409,
            code="ROTA_RECOMMENDATION_DRAFT_EXISTS",
            message="An active draft already exists for this store and week",
        )

    if replace_existing_draft:
        for draft in existing_active:
            draft.status = "discarded"
            db.add(
                AuditLog(
                    tenant_id=tenant_id,
                    user_id=actor_user_id,
                    action="discard",
                    entity_type="rota_recommendation_draft",
                    entity_id=str(draft.id),
                )
            )

    week_start_at, week_end_at = _week_bounds(week_start)
    open_shifts = db.scalars(
        select(Shift)
        .where(
            Shift.tenant_id == tenant_id,
            Shift.store_id == store_id,
            Shift.status == "scheduled",
            Shift.assigned_user_id.is_(None),
            Shift.start_at >= week_start_at,
            Shift.start_at < week_end_at,
        )
        .order_by(Shift.start_at.asc(), Shift.id.asc())
    ).all()

    candidate_user_ids = [
        row[0]
        for row in db.execute(
            select(TenantUser.user_id)
            .join(
                StaffProfile,
                (StaffProfile.tenant_id == TenantUser.tenant_id)
                & (StaffProfile.user_id == TenantUser.user_id),
            )
            .where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.role.in_(["admin", "member"]),
                StaffProfile.is_active.is_(True),
                or_(
                    StaffProfile.store_id == store_id,
                    StaffProfile.store_id.is_(None),
                ),
            )
            .order_by(TenantUser.user_id.asc())
        ).all()
    ]

    target_map = _build_target_map(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        week_start=week_start,
        candidate_user_ids=candidate_user_ids,
    )
    projected_hours = _build_assigned_hours_map(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        week_start=week_start,
        candidate_user_ids=candidate_user_ids,
    )
    availability_map = _build_availability_map(
        db,
        tenant_id=tenant_id,
        week_start=week_start,
        store_id=store_id,
        candidate_user_ids=candidate_user_ids,
    )
    role_map = _build_staff_role_map(
        db,
        tenant_id=tenant_id,
        candidate_user_ids=candidate_user_ids,
    )

    draft = RotaRecommendationDraft(
        tenant_id=tenant_id,
        store_id=store_id,
        week_start=week_start,
        status="draft",
        created_by_user_id=actor_user_id,
    )
    db.add(draft)
    db.flush()

    for shift in open_shifts:
        selected = _pick_candidate(
            shift=shift,
            candidate_user_ids=candidate_user_ids,
            projected_hours=projected_hours,
            target_map=target_map,
            availability_map=availability_map,
            role_map=role_map,
        )

        if selected is None:
            db.add(
                RotaRecommendationItem(
                    tenant_id=tenant_id,
                    draft_id=draft.id,
                    shift_id=shift.id,
                    proposed_user_id=None,
                    score=0,
                    reason="no_eligible_candidate",
                )
            )
            continue

        projected_hours[selected.user_id] = projected_hours.get(selected.user_id, 0.0) + _shift_duration_hours(shift)
        db.add(
            RotaRecommendationItem(
                tenant_id=tenant_id,
                draft_id=draft.id,
                shift_id=shift.id,
                proposed_user_id=selected.user_id,
                score=selected.score,
                reason=",".join(selected.reason_parts) if selected.reason_parts else "best_tiebreak",
            )
        )

    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="create",
            entity_type="rota_recommendation_draft",
            entity_id=str(draft.id),
        )
    )
    db.commit()
    db.refresh(draft)
    return _read_draft_detail(db, tenant_id=tenant_id, draft=draft)


def build_recalibrated_recommendation_for_shift(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    shift: Shift,
) -> DraftDetailRead:
    return create_rota_recommendation_draft_detail(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        store_id=shift.store_id,
        week_start=_week_start_for_datetime(shift.start_at),
        replace_existing_draft=True,
    )


@router.post("", response_model=DraftCreateResponse, status_code=201)
def create_rota_recommendation_draft(
    payload: DraftCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> DraftCreateResponse:
    detail = create_rota_recommendation_draft_detail(
        db,
        tenant_id=membership.tenant_id,
        actor_user_id=membership.user_id,
        store_id=payload.store_id,
        week_start=payload.week_start,
    )
    return DraftCreateResponse(
        draft_id=detail.draft.id,
        shifts_considered=detail.shifts_considered,
        items_created=detail.items_created,
        unfilled=detail.unfilled,
    )


@router.get("", response_model=list[DraftRead])
def list_rota_recommendation_drafts(
    store_id: uuid.UUID | None = None,
    week_start: date_type | None = None,
    status: DraftStatus | None = None,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[DraftRead]:
    query = select(RotaRecommendationDraft).where(RotaRecommendationDraft.tenant_id == membership.tenant_id)

    if store_id is not None:
        query = query.where(RotaRecommendationDraft.store_id == store_id)
    if week_start is not None:
        query = query.where(RotaRecommendationDraft.week_start == week_start)
    if status is not None:
        query = query.where(RotaRecommendationDraft.status == status)

    drafts = db.scalars(query.order_by(RotaRecommendationDraft.created_at.desc())).all()
    return [DraftRead.model_validate(draft) for draft in drafts]


@router.get("/{draft_id}", response_model=DraftDetailRead)
def get_rota_recommendation_draft(
    draft_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> DraftDetailRead:
    draft = _get_draft_or_404(db, tenant_id=membership.tenant_id, draft_id=draft_id)
    return _read_draft_detail(db, tenant_id=membership.tenant_id, draft=draft)


@router.post("/{draft_id}/apply", response_model=ApplyResponse)
def apply_rota_recommendation_draft(
    draft_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> ApplyResponse:
    draft = _get_draft_or_404(db, tenant_id=membership.tenant_id, draft_id=draft_id)
    if draft.status != "draft":
        raise ApiError(
            status_code=409,
            code="ROTA_RECOMMENDATION_DRAFT_NOT_APPLICABLE",
            message="Only draft recommendations can be applied",
        )

    items = db.scalars(
        select(RotaRecommendationItem).where(
            RotaRecommendationItem.tenant_id == membership.tenant_id,
            RotaRecommendationItem.draft_id == draft.id,
        )
    ).all()

    count_applied = 0
    for item in items:
        if item.proposed_user_id is None:
            continue

        shift = db.scalar(
            select(Shift).where(
                Shift.id == item.shift_id,
                Shift.tenant_id == membership.tenant_id,
            )
        )
        if shift is None:
            raise ApiError(
                status_code=404,
                code="SHIFT_NOT_FOUND",
                message="Shift not found in active tenant",
            )

        if shift.assigned_user_id is not None:
            continue

        shift.assigned_user_id = item.proposed_user_id
        count_applied += 1
        db.add(
            AuditLog(
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                action="update",
                entity_type="shift",
                entity_id=str(shift.id),
            )
        )

    draft.status = "applied"
    draft.applied_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="apply",
            entity_type="rota_recommendation_draft",
            entity_id=str(draft.id),
        )
    )
    db.commit()
    return ApplyResponse(count_applied=count_applied)


@router.post("/{draft_id}/discard", response_model=DraftRead)
def discard_rota_recommendation_draft(
    draft_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> DraftRead:
    draft = _get_draft_or_404(db, tenant_id=membership.tenant_id, draft_id=draft_id)
    if draft.status != "draft":
        raise ApiError(
            status_code=409,
            code="ROTA_RECOMMENDATION_DRAFT_NOT_DISCARDABLE",
            message="Only draft recommendations can be discarded",
        )

    draft.status = "discarded"
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="discard",
            entity_type="rota_recommendation_draft",
            entity_id=str(draft.id),
        )
    )
    db.commit()
    db.refresh(draft)
    return DraftRead.model_validate(draft)
