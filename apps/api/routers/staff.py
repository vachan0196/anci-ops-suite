import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core.deps import get_current_user, require_tenant_member, require_tenant_role
from apps.api.core.errors import ApiError
from apps.api.db.deps import get_db
from apps.api.models.audit_log import AuditLog
from apps.api.models.staff_profile import StaffProfile
from apps.api.models.store import Store
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.schemas.staff import StaffProfileCreate, StaffProfileOut, StaffProfileUpdate

router = APIRouter()


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


@router.get("", response_model=list[StaffProfileOut])
def list_staff_profiles(
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> list[StaffProfileOut]:
    profiles = db.scalars(
        select(StaffProfile)
        .where(StaffProfile.tenant_id == membership.tenant_id)
        .order_by(StaffProfile.created_at.desc())
    ).all()
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

    member_row = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == membership.tenant_id,
            TenantUser.user_id == payload.user_id,
        )
    )
    if member_row is None:
        raise ApiError(
            status_code=400,
            code="STAFF_USER_NOT_TENANT_MEMBER",
            message="User is not a member of the active tenant",
        )

    if payload.store_id is not None:
        store = db.scalar(
            select(Store).where(
                Store.id == payload.store_id,
                Store.tenant_id == membership.tenant_id,
            )
        )
        if store is None:
            raise ApiError(
                status_code=404,
                code="STORE_NOT_FOUND",
                message="Store not found in active tenant",
            )

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

    profile = StaffProfile(tenant_id=membership.tenant_id, **payload.model_dump())
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


@router.patch("/{user_id}", response_model=StaffProfileOut)
def update_staff_profile(
    user_id: uuid.UUID,
    payload: StaffProfileUpdate,
    membership: TenantUser = Depends(require_tenant_role("admin")),
    db: Session = Depends(get_db),
) -> StaffProfileOut:
    profile = db.scalar(
        select(StaffProfile).where(
            StaffProfile.tenant_id == membership.tenant_id,
            StaffProfile.user_id == user_id,
        )
    )
    if profile is None:
        raise ApiError(
            status_code=404,
            code="STAFF_PROFILE_NOT_FOUND",
            message="Staff profile not found in active tenant",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "store_id" in updates and updates["store_id"] is not None:
        store = db.scalar(
            select(Store).where(
                Store.id == updates["store_id"],
                Store.tenant_id == membership.tenant_id,
            )
        )
        if store is None:
            raise ApiError(
                status_code=404,
                code="STORE_NOT_FOUND",
                message="Store not found in active tenant",
            )

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
