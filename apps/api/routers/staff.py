from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from apps.api.core.deps import get_current_user, require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.staff_role import StaffRole
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.staff import (
    StaffDirectoryItem,
    StaffProfileCreate,
    StaffProfileOut,
    StaffProfileUpdate,
    StaffRoleCreate,
    StaffRoleOut,
    StaffSelfUpdate,
)

router = APIRouter()

_ALLOWED_CONTRACT_TYPES = {"full_time", "part_time", "zero_hours"}
_ALLOWED_RTW_STATUSES = {"pending", "verified", "expired"}
_ALLOWED_PAY_TYPES = {"hourly", "salary"}


def _validate_store_belongs_to_tenant(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
) -> None:
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


def _validate_member_exists_in_tenant(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    membership = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == user_id,
        )
    )
    if membership is None:
        raise ApiError(
            status_code=400,
            code="STAFF_USER_NOT_TENANT_MEMBER",
            message="User is not a member of the active tenant",
        )


def _validate_profile_fields(
    updates: dict,
) -> None:
    if updates.get("contract_type") is not None and updates["contract_type"] not in _ALLOWED_CONTRACT_TYPES:
        raise ApiError(
            status_code=400,
            code="STAFF_CONTRACT_TYPE_INVALID",
            message="contract_type must be one of: full_time, part_time, zero_hours",
        )

    if updates.get("rtw_status") is not None and updates["rtw_status"] not in _ALLOWED_RTW_STATUSES:
        raise ApiError(
            status_code=400,
            code="STAFF_RTW_STATUS_INVALID",
            message="rtw_status must be one of: pending, verified, expired",
        )

    if updates.get("pay_type") is not None and updates["pay_type"] not in _ALLOWED_PAY_TYPES:
        raise ApiError(
            status_code=400,
            code="STAFF_PAY_TYPE_INVALID",
            message="pay_type must be one of: hourly, salary",
        )


def _normalize_role(role: str) -> str:
    normalized = role.strip().lower()
    if not normalized:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="role must not be empty",
        )
    return normalized


def _get_staff_profile_or_404(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
) -> StaffProfile:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == tenant_id,
            StaffProfile.id == staff_id,
        )
    )
    if profile is None:
        # Backward-compatible fallback for earlier phases where path param was user_id.
        profile = db.scalar(
            select(StaffProfile).where(
                StaffProfile.tenant_id == tenant_id,
                StaffProfile.user_id == staff_id,
            )
        )

    if profile is None:
        raise ApiError(
            status_code=404,
            code="STAFF_PROFILE_NOT_FOUND",
            message="Staff profile not found in active tenant",
        )
    return profile


@router.get("/me", response_model=StaffProfileOut)
def get_my_staff_profile(
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> StaffProfileOut:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == membership.tenant_id,
            StaffProfile.user_id == current_user.id,
        )
    )
    if profile is None:
        raise ApiError(
            status_code=404,
            code="STAFF_PROFILE_NOT_FOUND",
            message="Staff profile not found for current user in active tenant",
        )
    return StaffProfileOut.model_validate(profile)


@router.patch("/me", response_model=StaffProfileOut)
def update_my_staff_profile(
    payload: StaffSelfUpdate,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> StaffProfileOut:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == membership.tenant_id,
            StaffProfile.user_id == current_user.id,
        )
    )
    if profile is None:
        raise ApiError(
            status_code=404,
            code="STAFF_PROFILE_NOT_FOUND",
            message="Staff profile not found for current user in active tenant",
        )

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(profile, field_name, value)

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="update_self",
            entity_type="staff_profile",
            entity_id=str(profile.id),
        )
    )
    db.commit()
    db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.get("", response_model=list[StaffProfileOut])
def list_staff_profiles(
    store_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[StaffProfileOut]:
    query = select(StaffProfile).where(StaffProfile.tenant_id == membership.tenant_id)
    if store_id is not None:
        query = query.where(StaffProfile.store_id == store_id)
    if is_active is not None:
        query = query.where(StaffProfile.is_active == is_active)

    profiles = db.scalars(query.order_by(StaffProfile.created_at.desc())).all()
    return [StaffProfileOut.model_validate(profile) for profile in profiles]


@router.post("", response_model=StaffProfileOut, status_code=201)
def create_staff_profile(
    payload: StaffProfileCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StaffProfileOut:
    user = db.get(User, payload.user_id)
    if user is None:
        raise ApiError(
            status_code=404,
            code="STAFF_USER_NOT_FOUND",
            message="User not found",
        )

    _validate_member_exists_in_tenant(
        db,
        tenant_id=membership.tenant_id,
        user_id=payload.user_id,
    )

    if payload.store_id is not None:
        _validate_store_belongs_to_tenant(
            db,
            tenant_id=membership.tenant_id,
            store_id=payload.store_id,
        )

    create_data = payload.model_dump()
    _validate_profile_fields(create_data)
    if create_data.get("rtw_status") in {"verified", "expired"}:
        create_data["rtw_checked_at"] = datetime.now(timezone.utc)
        create_data["rtw_checked_by_user_id"] = membership.user_id

    existing = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == membership.tenant_id,
            StaffProfile.user_id == payload.user_id,
        )
    )
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="STAFF_PROFILE_EXISTS",
            message="Staff profile already exists for user in active tenant",
        )

    profile = StaffProfile(tenant_id=membership.tenant_id, **create_data)
    db.add(profile)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="create",
            entity_type="staff_profile",
            entity_id=str(profile.id),
        )
    )
    db.commit()
    db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.get("/directory", response_model=list[StaffDirectoryItem])
def list_staff_directory(
    store_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[StaffDirectoryItem]:
    query = (
        select(StaffProfile, User.email, Store.name)
        .join(User, User.id == StaffProfile.user_id)
        .outerjoin(
            Store,
            and_(
                Store.id == StaffProfile.store_id,
                Store.tenant_id == membership.tenant_id,
            ),
        )
        .where(StaffProfile.tenant_id == membership.tenant_id)
    )
    if store_id is not None:
        query = query.where(StaffProfile.store_id == store_id)
    if is_active is not None:
        query = query.where(StaffProfile.is_active == is_active)

    rows = db.execute(query.order_by(StaffProfile.created_at.desc())).all()
    staff_ids = [profile.id for profile, _, _ in rows]

    roles_by_staff_id: dict[uuid.UUID, list[str]] = {staff_id: [] for staff_id in staff_ids}
    if staff_ids:
        role_rows = db.execute(
            select(StaffRole.staff_id, StaffRole.role)
            .where(
                StaffRole.tenant_id == membership.tenant_id,
                StaffRole.staff_id.in_(staff_ids),
            )
            .order_by(StaffRole.role.asc())
        ).all()
        for staff_id, role in role_rows:
            roles_by_staff_id.setdefault(staff_id, []).append(role)

    return [
        StaffDirectoryItem(
            id=profile.id,
            user_id=profile.user_id,
            display_name=profile.display_name,
            email=email,
            job_title=profile.job_title,
            phone=profile.phone,
            store_id=profile.store_id,
            store_name=store_name,
            roles=roles_by_staff_id.get(profile.id, []),
            is_active=profile.is_active,
            created_at=profile.created_at,
        )
        for profile, email, store_name in rows
    ]


@router.get("/{staff_id}", response_model=StaffProfileOut)
def get_staff_profile(
    staff_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: TenantUser = Depends(require_tenant_member),
    db: Session = Depends(get_db),
) -> StaffProfileOut:
    profile = _get_staff_profile_or_404(db, tenant_id=membership.tenant_id, staff_id=staff_id)

    if membership.role != "admin" and profile.user_id != current_user.id:
        raise ApiError(
            status_code=403,
            code="STAFF_PROFILE_FORBIDDEN",
            message="You can only view your own staff profile",
        )

    return StaffProfileOut.model_validate(profile)


@router.patch("/{staff_id}", response_model=StaffProfileOut)
def update_staff_profile(
    staff_id: uuid.UUID,
    payload: StaffProfileUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StaffProfileOut:
    profile = _get_staff_profile_or_404(db, tenant_id=membership.tenant_id, staff_id=staff_id)

    updates = payload.model_dump(exclude_unset=True)
    _validate_profile_fields(updates)

    if "store_id" in updates and updates["store_id"] is not None:
        _validate_store_belongs_to_tenant(
            db,
            tenant_id=membership.tenant_id,
            store_id=updates["store_id"],
        )

    if "rtw_status" in updates and updates["rtw_status"] in {"verified", "expired"}:
        updates["rtw_checked_at"] = datetime.now(timezone.utc)
        updates["rtw_checked_by_user_id"] = membership.user_id

    for field_name, value in updates.items():
        setattr(profile, field_name, value)

    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="update",
            entity_type="staff_profile",
            entity_id=str(profile.id),
        )
    )
    db.commit()
    db.refresh(profile)
    return StaffProfileOut.model_validate(profile)


@router.get("/{staff_id}/roles", response_model=list[StaffRoleOut])
def list_staff_roles(
    staff_id: uuid.UUID,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[StaffRoleOut]:
    profile = _get_staff_profile_or_404(db, tenant_id=membership.tenant_id, staff_id=staff_id)
    roles = db.scalars(
        select(StaffRole)
        .where(
            StaffRole.tenant_id == membership.tenant_id,
            StaffRole.staff_id == profile.id,
        )
        .order_by(StaffRole.role.asc())
    ).all()
    return [StaffRoleOut.model_validate(role) for role in roles]


@router.post("/{staff_id}/roles", response_model=StaffRoleOut)
def add_staff_role(
    staff_id: uuid.UUID,
    payload: StaffRoleCreate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StaffRoleOut:
    profile = _get_staff_profile_or_404(db, tenant_id=membership.tenant_id, staff_id=staff_id)
    normalized_role = _normalize_role(payload.role)

    existing = db.scalar(
        select(StaffRole).where(
            StaffRole.tenant_id == membership.tenant_id,
            StaffRole.staff_id == profile.id,
            StaffRole.role == normalized_role,
        )
    )
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="STAFF_ROLE_EXISTS",
            message="Role already exists for staff profile",
        )

    role = StaffRole(
        tenant_id=membership.tenant_id,
        staff_id=profile.id,
        role=normalized_role,
    )
    db.add(role)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="add_role",
            entity_type="staff_role",
            entity_id=str(role.id),
        )
    )
    db.commit()
    db.refresh(role)
    return StaffRoleOut.model_validate(role)


@router.delete("/{staff_id}/roles/{role}", status_code=204)
def delete_staff_role(
    staff_id: uuid.UUID,
    role: str,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> None:
    profile = _get_staff_profile_or_404(db, tenant_id=membership.tenant_id, staff_id=staff_id)
    normalized_role = _normalize_role(role)

    role_row = db.scalar(
        select(StaffRole).where(
            StaffRole.tenant_id == membership.tenant_id,
            StaffRole.staff_id == profile.id,
            StaffRole.role == normalized_role,
        )
    )
    if role_row is None:
        raise ApiError(
            status_code=404,
            code="STAFF_ROLE_NOT_FOUND",
            message="Staff role not found in active tenant",
        )

    entity_id = str(role_row.id)
    db.delete(role_row)
    db.add(
        AuditLog(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            action="remove_role",
            entity_type="staff_role",
            entity_id=entity_id,
        )
    )
    db.commit()
