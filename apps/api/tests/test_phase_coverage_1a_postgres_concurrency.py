from concurrent.futures import ThreadPoolExecutor
from datetime import time
import os
from threading import Barrier
import uuid

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from apps.api.models.audit_log import AuditLog
from apps.api.models.coverage_template import CoverageTemplate
from apps.api.models.generation_run import GenerationRun
from apps.api.models.shift import Shift
from apps.api.models.store import Store
from apps.api.models.tenant import Tenant
from apps.api.models.tenant_user import TenantUser
from apps.api.models.user import User
from apps.api.routers.rota import generate_week_shifts
from apps.api.schemas.rota import GenerateWeekRequest


def test_postgresql_concurrent_generation_has_one_active_template_set() -> None:
    """SQLite coverage cannot prove this PostgreSQL advisory-lock boundary."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+")):
        pytest.skip("PostgreSQL-backed Coverage.1a concurrency integration test")

    engine = create_engine(database_url, poolclass=NullPool)
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-backed Coverage.1a concurrency integration test")
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    store_id = uuid.uuid4()
    template_id = uuid.uuid4()
    week_start = "2026-09-07"
    membership_id = uuid.uuid4()
    with session_local() as db:
        db.add(Tenant(id=tenant_id, name="Coverage.1a concurrency tenant"))
        db.flush()
        db.add(
            User(
                id=user_id,
                email=f"coverage-concurrency-{uuid.uuid4()}@example.com",
                hashed_password="not-used",
                active_tenant_id=tenant_id,
            )
        )
        db.add(
            Store(
                id=store_id,
                tenant_id=tenant_id,
                code=f"C1A-{uuid.uuid4().hex[:10]}",
                name="Coverage concurrency",
                timezone="UTC",
            )
        )
        db.flush()
        membership = TenantUser(
            id=membership_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role="admin",
        )
        db.add(membership)
        db.add(
            CoverageTemplate(
                id=template_id,
                tenant_id=tenant_id,
                store_id=store_id,
                day_of_week=0,
                start_time=time(9),
                end_time=time(17),
                required_headcount=1,
                required_role="crew",
                is_active=True,
            )
        )
        db.commit()

    start_barrier = Barrier(2)

    def run_generation() -> dict:
        with session_local() as db:
            membership = db.get(TenantUser, membership_id)
            assert membership is not None
            start_barrier.wait(timeout=10)
            response = generate_week_shifts(
                GenerateWeekRequest(store_id=store_id, week_start=week_start),
                membership,
                db,
            )
            return response.model_dump()

    results: list[dict] = []
    errors: list[BaseException] = []
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_generation) for _ in range(2)]
            for future in futures:
                try:
                    results.append(future.result(timeout=30))
                except BaseException as exc:  # surfaced after cleanup
                    errors.append(exc)

        with session_local() as db:
            shifts = db.scalars(
                select(Shift).where(
                    Shift.tenant_id == tenant_id,
                    Shift.store_id == store_id,
                )
            ).all()
            assert len([shift for shift in shifts if shift.status == "scheduled"]) == 1
            assert len([shift for shift in shifts if shift.status == "cancelled"]) == 1
            assert db.query(GenerationRun).filter(GenerationRun.tenant_id == tenant_id).count() == 2
        assert not errors
        assert len(results) == 2
        assert sorted(result["replaced_count"] for result in results) == [0, 1]
    finally:
        with session_local() as db:
            db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
            db.execute(delete(Shift).where(Shift.tenant_id == tenant_id))
            db.execute(delete(GenerationRun).where(GenerationRun.tenant_id == tenant_id))
            db.execute(delete(CoverageTemplate).where(CoverageTemplate.tenant_id == tenant_id))
            db.execute(delete(TenantUser).where(TenantUser.tenant_id == tenant_id))
            user = db.get(User, user_id)
            if user is not None:
                user.active_tenant_id = None
                db.flush()
            db.execute(delete(Store).where(Store.tenant_id == tenant_id))
            db.execute(delete(User).where(User.id == user_id))
            db.execute(delete(Tenant).where(Tenant.id == tenant_id))
            db.commit()
        engine.dispose()
