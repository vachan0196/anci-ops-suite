# ForecourtOS / Anci Ops Suite — Implementation Status

**Last updated:** 2026-07-20

## RecommendationUI.3 Completion — In-App Discard & Regenerate

RecommendationUI.3 has been implemented as a frontend-only recovery workflow for stale or empty recommendation drafts.

Commit:
- `12c698b feat: in-app discard and regenerate for recommendation drafts`

Scope:
- Surfaced the existing `POST /api/v1/rota-recommendations/{draft_id}/discard` endpoint as a "Discard draft" button in `/admin/rota`.
- Converted the stale/active-draft blue message into an actionable "Regenerate" block.
- Regenerate uses `discard -> create -> load` through existing HTTP contracts.
- Regenerate is intentionally non-atomic because `DraftCreate` uses `extra="forbid"` and the service-level `replace_existing_draft` parameter is not exposed over HTTP.
- Clearing a stale or empty draft no longer requires manual SQL.
- Generate, Apply, Discard, and Regenerate are mutually disabled while one recommendation action is in flight.
- No backend logic, schema, migration, permission matrix, apply flow, or publish logic was changed.

Files changed:
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/lib/api-client.ts`

Checks:
- `cd apps/web && npm run build`: passed.
- `cd apps/web && npx tsc --noEmit`: passed after the build generated `.next/types`.
- `git diff --check`: passed.
- Focused rota recommendation backend tests passed: `19 passed`.
- Full backend suite with `RATE_LIMIT_ENABLED=false` completed with unrelated employee-portal failures: `2 failed, 433 passed, 6 skipped`.

Known limitations:
- Regenerate is non-atomic; if create fails after discard succeeds, the manager is left with no active draft and the UI shows a safe error.
- A future dedicated atomic regenerate endpoint could close this partial-failure gap.

## RecommendationUI.2 Completion — Apply Recommendation Draft to Rota

RecommendationUI.2 has been implemented as a frontend-only apply workflow for loaded recommendation drafts.

Commit:
- `b9859e0 feat: apply rota recommendation draft to weekly rota grid`

Scope:
- Wired the Apply button to existing `POST /api/v1/rota-recommendations/{draft_id}/apply`.
- The backend apply endpoint only assigns proposed items, skips unfilled items, skips shifts already assigned by the time of apply, sets `draft.status = "applied"`, sets `applied_at`, and audit-logs shift updates plus the draft apply action.
- The weekly rota grid refreshes after apply so open/unassigned shifts flip into assigned shifts where recommendations were applied.
- The UI shows a partial-fill message for unfilled shifts that still need manual assignment.
- The Apply button locks after apply by using the refreshed draft status.
- Browser and database verification confirmed a draft with `items=21`, `proposed=21`, and `status=applied`.
- No backend change or migration was added.

Files changed:
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/lib/api-client.ts`

Checks:
- Frontend build/typecheck and browser round-trip were completed during the phase.

## Availability + Recommendation Cap Arc Completion

The availability and recommendation input chain is complete and covered by focused backend E2E tests.

Scope:
- Admin availability backend is complete via `PUT /api/v1/staff/{staff_user_id}/availability/week`.
- Admin availability UI is complete in the Staff Profile detail Availability section.
- Availability is Source 2 for rota recommendations and is person-scoped by `user_id`.
- Admin availability writes `source="admin"`; employee availability writes `source="employee"`.
- Admin replace-week is authoritative for the selected staff member/week and can overwrite employee-set rows for that week.
- Recommendation semantics are now documented and tested:
  - no availability row = unavailable/skipped
  - `available` / `available_extra` = eligible
  - `preferred_off` / `unavailable` / no row = skipped
  - leave remains separate in `shift_requests`
- The admin availability to recommendation chain is verified end to end in `apps/api/tests/test_rota_recommendations_e2e_availability.py`.
- `StaffProfile.weekly_working_hour_soft_cap` now behaves as a true soft recommendation signal: candidates remain eligible, receive `over_weekly_soft_cap`, and rank behind under-cap candidates.
- `HourTarget.max_hours` remains the hard weekly override/limit when present.

Next likely product phase:
- Recommendation UX polish: surface recommendation reasons such as `over_weekly_soft_cap` clearly in the admin recommendation workflow.

## StaffRules.1a Completion — Backend Standing Hours Soft Caps

StaffRules.1a has been implemented as a backend-only staff rules phase.

Scope:
- Added `weekly_working_hour_soft_cap` and `monthly_working_hour_soft_cap` to staff profile persistence.
- The new fields are nullable, fractional-capable operational scheduling data.
- Owner and Admin can read/write these soft-cap fields through the existing staff profile APIs.
- Admin-safe staff projections now include only these two new operational scheduling fields in addition to the existing safe staff fields.
- Existing Owner-only sensitive staff protections for `hourly_rate`, `pay_type`, and `rtw_status` are preserved.
- Admin/non-owner staff read projections continue to omit `hourly_rate`, `pay_type`, and `rtw_status` entirely.
- Staff directory remains trimmed and does not expose the new soft-cap fields.
- Soft caps are data only in this phase. No rota warning logic, scheduling enforcement, cap calculations, or frontend UI was added.
- `hour_targets` remains available as a weekly override/exception layer keyed by `week_start`; it was not changed in this phase.
- Pay-rules, overtime, NI numbers, documents, compliance storage, staff lifecycle actions, identity decoupling, H085 rota assignment rename, and manager-role behaviour remain future work.

Files changed:
- `apps/api/models/staff_profile.py`
- `apps/api/schemas/staff.py`
- `apps/api/routers/staff.py`
- `apps/api/alembic/versions/0031_staff_rules_soft_caps.py`
- `apps/api/tests/test_staff_rules_soft_caps.py`
- `IMPLEMENTATION_STATUS.md`

Checks:
- `python3 -m py_compile apps/api/models/staff_profile.py apps/api/schemas/staff.py apps/api/routers/staff.py apps/api/tests/test_staff_rules_soft_caps.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini downgrade -1 && alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/ -k staff -q -vv"`: 54 passed, 361 deselected.

Known limitations:
- The caps are soft standing rules only; future rota work must decide how and where warnings are shown.
- No Stage 1b frontend workflow was added.
- No changes were made to payroll/pay-rules or weekly `hour_targets` override behaviour.

Next recommended phase:
- StaffRules.1b — Owner/Admin UI for standing hours soft caps on the staff profile workflow.

## Rota.1 Completion — Multi-Site Admin Rota Selector

Rota.1 has been implemented as a frontend-focused stabilisation of the existing `/admin/rota` page.

Scope:
- Preserved the existing `/admin/rota` page and `RotaContent` in `apps/web/components/admin/admin-shell.tsx`.
- Added a proper site selector sourced from the existing `listStores` API client function.
- The selector renders active sites returned by `GET /api/v1/stores` for the current admin-side session.
- The initial selection keeps the previous behaviour by defaulting to the first active site.
- Single-site tenants see a selected-site label instead of an unnecessary selector.
- Tenants with no active sites keep the existing no-site/empty rota state.
- Site selection is held in component state only; no localStorage persistence was added.
- Changing site refetches:
  - `GET /api/v1/sites/{site_id}/rota/week?week_start=YYYY-MM-DD`
  - `GET /api/v1/stores/{store_id}/readiness`
  - safe staff directory data for the selected site
- Week navigation continues to refetch the selected site's weekly rota.
- Preserved Open shifts as a separate grid row.
- Clarified rota publication state as `Draft`, `Part published`, or `Published` based on backend weekly rota counts.
- Preserved existing create/edit/cancel draft shift and publish/unpublish flows.
- Did not enable generate week, AI recommendations, or export.
- No backend files, auth/session behaviour, localStorage behaviour, employee portal behaviour, or permission matrix rows were changed.

Gap H observation:
- The weekly rota frontend receives `assigned_employee_account_id` from `WeeklyRotaShift`.
- Current frontend staff lookup treats that value as `staff.user_id`.
- Rota.0 confirmed the backend site weekly rota maps `assigned_employee_account_id` from `Shift.assigned_user_id`, not from a true `employee_accounts.id`.
- Rota.1 did not change this contract. H085 tracks this as a before-EP.0 contract cleanup.

Files changed:
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `HARDENING_BACKLOG.md`
- `DECISIONS.md`

Checks:
- `cd apps/web && npx tsc --noEmit`: passed.
- `cd apps/web && npm run build`: passed.
- `git diff --check`: passed.
- Route smoke via Next dev server returned HTTP 200 for `/admin/rota`, `/admin/requests`, and `/admin/staff`.
- API smoke against the running local backend created an owner with two active sites, verified both sites appeared in `GET /api/v1/stores`, verified selected-site weekly rota/readiness endpoints for both sites, created an open shift, edited and cancelled draft shifts, and confirmed publish/unpublish still worked.

Manual browser verification:
- Full interactive browser verification was not completed because no local browser executable or Playwright binary is available in the workspace. Route/API smoke covered the implemented route and backend flows, but visual selector interaction still needs human browser review.

Known limitations:
- No full assigned-site RBAC scoping was added; the selector renders only what the existing stores API returns.
- `/admin/requests` remains separate from `/admin/rota`.
- Generate week, AI recommendations, export, drag/drop, and deeper editor redesign remain future work.
- Gap H remains open: `assigned_employee_account_id` is currently a user ID-shaped value in this rota API contract.

Next recommended phase:
- Rota.2 — Deeper manual editor polish and any approved rota editor UX improvements.

## Staff.1 Completion — Safe Staff Profile View/Edit UI

Staff.1 has been implemented as a frontend-only safe staff profile view/edit phase.

Scope:
- Added safe staff profile viewing/editing at `/admin/staff/[staffId]`.
- Staff directory links continue to open the staff detail/edit page.
- Staff detail/edit pre-fill now uses `GET /api/v1/staff/{staff_id}`.
- The edit page no longer uses `/api/v1/staff/directory` as the edit pre-fill source.
- Save uses `PATCH /api/v1/staff/{staff_id}`.
- Added a dedicated frontend safe edit payload containing only:
  - `job_title`
  - `phone`
  - `emergency_contact_name`
  - `emergency_contact_phone`
  - `contract_type`
  - `notes`
- The Staff.1 save payload does not send pay/RTW fields, lifecycle fields, identity/name-authority fields, document fields, or payroll-rule fields.
- Owner full staff detail responses are intentionally narrowed by the frontend payload builder; Staff.1 does not round-trip `hourly_rate`, `pay_type`, or `rtw_status` back into PATCH.
- Added visible notes warning copy: "Do not store NI numbers, right-to-work document details, passport/BRP/share-code details, medical information, payroll-sensitive data, or other sensitive personal data in notes."
- Preserved `/admin/staff/new`.
- Preserved `/admin/sites/new`.
- No backend files were changed.
- No auth/session/localStorage behaviour was changed.
- No employee portal behaviour was changed.

Explicitly excluded from Staff.1:
- `is_active`
- deactivate
- reactivate
- archive
- delete
- `hourly_rate`
- `pay_type`
- `rtw_status`
- NI number
- passport number
- BRP/share-code documents
- document upload
- base hours threshold
- overtime rate
- weekly hour cap
- payroll rules
- `display_name`

Files changed:
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/staff-profile-detail.tsx`

Checks:
- `cd apps/web && npx tsc --noEmit`: passed.
- `cd apps/web && npm run build`: passed.
- `git diff --check`: passed.

Known limitations:
- `display_name` editing remains deliberately deferred because of linked user/staff identity name-authority questions.
- Staff lifecycle actions remain separate future work.
- Pay/RTW remains a separate future Owner-only UI with 2FA/step-up/audit where applicable.
- NI/compliance document storage remains future secure design work.
- Payroll/pay-rules remain future model work.

Next recommended phase:
- Staff.1L — Staff deactivate/reactivate lifecycle design, or H083 Owner-only staff pay/RTW UI with step-up/audit if prioritised.

## Docs.1 Completion — Owner-Only Sensitive Staff Data Decision

Docs.1 has been completed as a documentation/source-of-truth update.

Scope:
- Added D043 to `DECISIONS.md` to lock Owner-only sensitive staff pay/right-to-work access for MVP.
- Recorded that Owner may read/write `hourly_rate`, `pay_type`, and `rtw_status`.
- Recorded that Admin/non-owner staff read responses must omit pay/RTW fields.
- Recorded that non-owner writes of non-null pay/RTW fields are rejected.
- Recorded that non-owner explicit `null` pay/RTW fields are stripped and must not clear Owner-set values.
- Recorded that normal staff edit UI must use safe-fields-only payloads.
- Recorded that NI number, passport/BRP/share-code documents, compliance document storage, weekly hour cap, base hours threshold, overtime rate, payroll rules, and conditional Admin/Manager grants remain future design work.
- Updated D007 to reflect that staff can be created during site setup or later through `/admin/staff/new`.
- Updated D009 to record the current multi-step staff creation flow and the temporary orphan-user consequence after Staff.2b.

Files changed:
- `DECISIONS.md`

Commit:
- `1e54e46 docs: record owner-only staff sensitive data decision`

Checks:
- `git diff --check`: passed.
- Documentation diff reviewed before commit.

Known limitations:
- This was documentation-only.
- No implementation status, backlog, README, permission matrix, backend, or frontend files were changed in this commit.
- `HARDENING_BACKLOG.md`, README, and permission matrix may still need separate review if stale.

Next recommended phase:
- Completed by Staff.1.

## Staff.2b Completion — Staff Pay/RTW Write Hardening

Staff.2b has been implemented.

Scope:
- Hardened staff write paths so only Owner can write non-null sensitive staff pay/right-to-work fields.
- Added backend rejection for non-owner attempts to write non-null:
  - `hourly_rate`
  - `pay_type`
  - `rtw_status`
- Preserved safe/basic staff writes for Admin where currently permitted.
- Treated explicit non-owner `null` values for pay/RTW as “not setting”.
- Stripped non-owner `null` sensitive fields before persistence so they cannot clear existing Owner-set sensitive values.
- Preserved tenant/resource visibility checks before sensitive write rejection.
- Updated the older T.2 matrix oracle from the old “admin can write pay/RTW” behaviour to the new Owner-only truth.
- Added targeted Staff.2b tests.

Files changed:
- `apps/api/routers/staff.py`
- `apps/api/tests/test_phase_t2_role_boundary_matrix.py`
- `apps/api/tests/test_staff2b_pay_rtw_write_hardening.py`

Commit:
- `0369773 fix: restrict staff pay and RTW writes to owners`

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_staff2b_pay_rtw_write_hardening.py -q -vv"`: 6 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_staff2_pay_rtw_read_hardening.py apps/api/tests/test_phase_t2_role_boundary_matrix.py apps/api/tests/test_phase_c_staff_setup_flow.py apps/api/tests/test_phase_t0_tenant_role_security_gate.py -q"`: 35 passed.
- `git diff --check`: passed.

Known limitations:
- Staff creation remains a multi-step frontend/backend flow: `create user → create staff → assign role`.
- If a non-owner creates a user first and then `POST /staff` is rejected for non-null sensitive pay/RTW fields, an orphan member user can remain.
- This is accepted temporarily and should be addressed by a future safer setup endpoint or by omitting/hiding sensitive fields for non-owner staff creation flows.
- No owner-only pay/RTW frontend UI was added.
- No NI/document/compliance storage was added.
- No payroll/pay-rules model was added.

Next recommended phase:
- Completed by Staff.1.

## Staff.2 Completion — Staff Pay/RTW Read-Model Hardening

Staff.2 has been implemented.

Scope:
- Hardened staff read models so Owner receives full staff profile data but non-owner staff reads receive a safe projection.
- Added `StaffProfileSafeOut`.
- Added role-gated staff serialization in the staff router.
- Owner receives:
  - `hourly_rate`
  - `pay_type`
  - `rtw_status`
- Admin/non-owner staff read responses omit those keys entirely; they are not returned as `null`.
- Member-accessible own-profile admin-style staff reads use the safe schema.
- `GET /api/v1/staff/directory` remains trimmed and does not expose pay/RTW fields.
- `/employee/me/profile` was left unchanged so the employee-facing projection remains separate from admin staff models.
- Added Staff.2 regression coverage.

Files changed:
- `apps/api/schemas/staff.py`
- `apps/api/routers/staff.py`
- `apps/api/tests/test_phase_t2_role_boundary_matrix.py`
- `apps/api/tests/test_staff2_pay_rtw_read_hardening.py`

Commit:
- `180cf71 fix: harden staff pay and RTW read exposure`

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed after rebuilding the API image so Docker could see the new test file.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_staff2_pay_rtw_read_hardening.py -q -vv"`: 6 passed.
- `git diff --check`: passed.

Known limitations:
- Staff.2 hardened read exposure only.
- Before Staff.2b, Admin write-side pay/RTW exposure still existed; Staff.2b later fixed it.
- No frontend pay/RTW UI was added.
- No NI/document/compliance storage was added.

Next recommended phase:
- Staff.2b — Staff pay/RTW write-side permission hardening.

## UX.2 Completion — Staff Creation for Existing Sites

UX.2 has been implemented as a frontend-only staff creation phase.

Scope:
- Added `/admin/staff/new`.
- Preserved `/admin/staff`.
- Preserved `/admin/staff/[staffId]`.
- Preserved `/admin/sites/new`.
- Updated the Staff page site filter so active zero-staff sites appear.
- Added staff creation for existing active sites.
- Staff creation targets an existing active site through the current backend three-call flow:
  - `POST /api/v1/admin/users`
  - `POST /api/v1/staff`
  - `POST /api/v1/staff/{staff_id}/roles`
- Credential mapping mirrors the existing site-setup staff flow.
- Partial-failure retry state is kept in component memory to avoid re-creating the user on retry.
- Password fields are cleared on success before returning to `/admin/staff`.
- No `localStorage` or `sessionStorage` was added.
- No backend files were changed.

Files changed:
- `apps/web/components/admin/staff-directory.tsx`
- `apps/web/components/admin/staff-create-form.tsx`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/app/admin/staff/new/page.tsx`

Commit:
- `a69eace feat: add staff creation for existing sites`

Checks:
- `cd apps/web && npx tsc --noEmit`: passed.
- `cd apps/web && npm run build`: passed.
- Route smoke via Next dev server:
  - `/admin/staff/new`: 200
  - `/admin/staff`: 200
  - `/admin/staff/[staffId]`: 200
  - `/admin/sites/new`: 200
- Local API smoke passed: created 3 stores, simulated user-created/staff-profile-failed partial save, retried using the same `user_id`, created staff profile + role, and confirmed staff appeared under selected site filter.
- `git diff --check`: passed.

Manual verification:
- Owner can add a new staff member from the Staff area.
- New staff appears under the selected site after creation.

Known limitations:
- Staff editing remains separate future work.
- Staff deactivation/reactivation remains future lifecycle work.
- Manager assignment remains out of scope.
- Staff identity decoupling remains future work.
- Compliance/payroll surfaces remain out of scope.

Next recommended phase:
- Staff.2 / Staff.2b security hardening and Staff.1 safe profile edit UI were completed after UX.2.

## UX.1 Completion — Admin Sites List and Edit UI

UX.1 has been implemented as a frontend-only sites management phase.

Scope:
- Added `/admin/sites` for existing Sites/Locations list.
- Added `/admin/sites/[id]` for existing site edit.
- Preserved `/admin/sites/new`.
- Updated the admin shell Sites nav to route to `/admin/sites`.
- Confirmed `GET /api/v1/stores/{id}` exists before building the edit flow.
- Wired the pages to existing real store APIs:
  - `GET /api/v1/stores`
  - `GET /api/v1/stores/{id}`
  - `PATCH /api/v1/stores/{id}`
- PATCH payload sends only normal site profile fields:
  - `code`
  - `name`
  - `timezone`
  - `address_line1`
  - `city`
  - `postcode`
  - `phone`
- Excluded lifecycle/destructive fields and sensitive fields:
  - `is_active`
  - lifecycle fields
  - `manager_user_id`
  - `tenant_id`
  - timestamps
  - destructive/lifecycle action fields
- No backend files were changed.

Files changed:
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/components/admin/sites-management.tsx`
- `apps/web/app/admin/sites/page.tsx`
- `apps/web/app/admin/sites/[id]/page.tsx`

Commit:
- `feb84af feat: add admin sites list and edit UI`

Checks:
- `cd apps/web && npx tsc --noEmit`: passed.
- `cd apps/web && npm run build`: passed.
- `git diff --check`: passed.
- Route smoke returned 200 for:
  - `/admin/sites`
  - `/admin/sites/new`
  - `/admin/sites/[id]`
- Local API smoke passed: created owner/site, loaded detail via `GET /stores/{id}`, patched only safe fields, then confirmed updated value appeared from `GET /stores`.

Manual verification:
- Owner can open Sites.
- Existing active sites are shown.
- Editing a site works.
- Edited site values reflect on the cards/list after save.

Known limitations:
- Opening hours editing remains future work.
- Site lifecycle actions remain future UI work.
- Manager assignment remains out of scope.
- No shell redesign was included.

Next recommended phase:
- UX.2 — Staff creation for existing sites.

## Phase T.2 Completion — Matrix-Backed Role Boundary Tests

Phase T.2 has been implemented as a focused backend security test phase.

Scope:
- Added matrix-backed role-boundary tests against corrected CURRENT-TRUTH.
- Covered owner/admin/member/employee-account boundaries for known gap areas.
- Added coverage for admin staff pay/RTW access, admin user creation boundaries, legacy employee route token boundaries, site request approval, store lifecycle PATCH protection after T.2a, and member/admin portal boundaries.
- Kept tests CURRENT-TRUTH only.
- Did not add TARGET permission assertions.
- Did not refactor role guards.
- Did not change endpoint design.
- Did not change identity coupling.

Files changed:
- `apps/api/tests/test_phase_t2_role_boundary_matrix.py`

Commit:
- `0f1395f test: add matrix-backed role boundary tests`

Checks:
- T.2 targeted tests: 14 passed.
- Q.5.2a / T.0 / employee portal regression bundle: passed.
- `git diff --check`: passed.

Known limitations:
- T.2 was test-only.
- It did not fix staff pay/RTW read/write exposure by itself.
- Staff.2 and Staff.2b later hardened those gaps.
- It did not implement target manager role behaviour.
- It did not decouple staff identity from admin-auth users.

Next recommended phase:
- Short gap triage, then UX.1 / Staff security hardening as needed.

## Phase T.2a Completion — Store Lifecycle PATCH Bypass Fix

Phase T.2a has been implemented as a narrow backend security fix.

Scope:
- Confirmed `StoreUpdate` previously accepted `is_active`.
- Confirmed `PATCH /api/v1/stores/{store_id}` previously wrote all update fields with `setattr`, so ordinary PATCH could change `is_active`.
- Confirmed no dedicated reactivation endpoint exists; before T.2a, generic PATCH was the only apparent reactivation path.
- Removed `is_active` from `StoreUpdate` and made `StoreUpdate` reject extra fields, so `PATCH /api/v1/stores/{store_id}` now returns 422 for lifecycle-state fields such as `is_active`.
- Added `apps/api/tests/test_phase_t2a_store_lifecycle_bypass.py`.
- Tests assert lifecycle state remains unchanged after PATCH attempts, including deactivate attempts, reactivate attempts, mixed normal+lifecycle payloads, and cross-tenant attempts.
- Confirmed normal store PATCH fields still work.
- Confirmed protected `POST /api/v1/stores/{store_id}/deactivate` remains the deactivation path and still rejects admin/non-step-up attempts.
- Updated `apps/api/docs/forecourt_os_permission_matrix_current_v1.md` to reflect the T.2a current-truth state and mark the old StoreUpdate `is_active` bypass as resolved.

No frontend code, migrations, auth/session logic, broad lifecycle redesign, staff identity, employee portal, pay/RTW RBAC, admin-user RBAC, or rota/request policy changes were made.

Known limitations:
- Store deactivation remains one-way in current product behavior unless a future explicit reactivation workflow is designed and approved.

Checks so far:
- `python3 -m py_compile apps/api/routers/stores.py apps/api/schemas/store.py apps/api/tests/test_phase_t2a_store_lifecycle_bypass.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_t2a_store_lifecycle_bypass.py -q --durations=20"`: passed, 6 tests.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_2a_step_up.py apps/api/tests/test_phase_t0_tenant_role_security_gate.py -q --durations=20"`: passed, 12 passed, 1 skipped.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q --durations=20"`: passed, 378 passed, 6 skipped.

## Phase T.1 Completion — Reconciled Permission Matrix Current Truth

Phase T.1 has been implemented as a documentation/source-of-truth phase only.

Scope:
- Created `apps/api/docs/forecourt_os_permission_matrix_current_v1.md`.
- Confirmed the old/raw `forecourt_os_permission_matrix_v1.md` file is still not present in the local repo.
- Reconciled permissions into separate CURRENT-TRUTH, TARGET, and GAP/BACKLOG layers pinned to commit `5b79955`.
- Derived CURRENT-TRUTH from effective backend access: dependencies/guards, handler logic, tenant/site filters, response schemas, mutation schemas, and tests.
- Documented current roles and identities: `owner`, `admin`, `member`, `employee_account`, future/target `manager`, and future/target platform owner.
- Documented company, stores/sites, staff, admin users, employee portal, rota/shifts/requests, availability, hour targets, coverage templates, rota generation, and rota recommendations at current-truth level.
- Added field-level notes for staff sensitive fields including `hourly_rate`, `pay_type`, `rtw_status`, `rtw_checked_at`, `rtw_checked_by_user_id`, `employee_account_id`, and employee credential creation behavior.
- Recorded current-vs-target gaps for staff pay/RTW exposure, admin-user creation, member FK bridge, store deactivation bypass risk through `PATCH /stores/{id}`, employee route identity split, and operational RBAC target decisions.
- Updated H081 to track T.1/T.2 permission-matrix reconciliation and test expansion.

No backend code, frontend code, tests, migrations, auth/session logic, schemas, or endpoints were changed.

Checks:
- `git diff --check`: passed.
- Markdown grep checks for CURRENT-TRUTH, TARGET, GAP, UNVERIFIED, `member is not Admin Portal access`, and `5b79955`: passed.

## Phase T.0 Completion — Tenant Isolation + Role Boundary Security Gate

Phase T.0 has been implemented as a focused backend security test/reporting gate.

Scope:
- Confirmed tenant isolation is enforced in application code through FastAPI dependencies and explicit `tenant_id` / site-store query filters.
- Confirmed PostgreSQL Row Level Security policies are not used in the current backend, so SQLite tests exercise the implemented isolation mechanism but do not provide any database-layer RLS assurance.
- Added `apps/api/tests/test_phase_t0_tenant_role_security_gate.py`.
- Covered high-risk router families:
  - `company.py`: `GET /api/v1/company/profile`, `PATCH /api/v1/company/profile`
  - `stores.py`: `GET /api/v1/stores`, `GET /api/v1/stores/{store_id}`, `PATCH /api/v1/stores/{store_id}`, `GET /api/v1/stores/{store_id}/readiness`
  - `staff.py`: `GET /api/v1/staff`, `GET /api/v1/staff/directory`, `GET /api/v1/staff/{staff_id}`, `PATCH /api/v1/staff/{staff_id}`
  - `employee.py`: `GET /api/v1/employee/me/availability`, `POST /api/v1/employee/me/availability`, `DELETE /api/v1/employee/me/availability/{entry_id}`, `GET /api/v1/employee/me/requests`, `POST /api/v1/employee/me/requests`
- Enforced cross-tenant denial/not-found behavior for company active-tenant profile state, stores, store readiness, staff list/directory/detail/update, and staff pay/right-to-work mutation attempts.
- Enforced token boundary checks: employee tokens cannot call representative admin APIs, admin tokens cannot call employee-only availability APIs, and `member` users still cannot obtain Admin Portal tokens after R.2d.
- Enforced employee self-only behavior for availability and request lists, plus same-site and cross-tenant store denial for employee availability.

Permission matrix note:
- `forecourt_os_permission_matrix_v1.md` was not present in the local repo, and no complete local equivalent was found.
- T.0 therefore uses only absolute tenant isolation rules and explicit local decisions as role-boundary oracles, especially D041 company owner-only and member-not-admin behavior.
- Broader role-boundary assertions against a full permission matrix were not invented.

Known limitations / T.1:
- Add the missing permission matrix or local equivalent, then expand role-boundary checks from that oracle.
- Add matrix-backed coverage for admin-user creation, staff pay/right-to-work field-level policy, and operational endpoints such as rota, shifts, shift requests, availability admin APIs, hour targets, coverage templates, and rota recommendations.
- T.0 did not change authorization architecture, auth/session design, frontend code, endpoints, migrations, or staff identity coupling.

Checks:
- `python3 -m py_compile apps/api/tests/test_phase_t0_tenant_role_security_gate.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_t0_tenant_role_security_gate.py -q --durations=20"`: passed, 5 tests.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q --durations=20"`: passed, 372 passed, 6 skipped.

## Phase R.2d Completion — Block Member Admin Portal Access

Phase R.2d has been implemented.

Scope:
- Confirmed `member` is not a full Admin Portal role in the current product model; it remains a temporary staff-profile FK/tenant-membership bridge while staff identity decoupling is deferred.
- Added an admin-auth-specific role guard so only `owner` and `admin` tenant roles can receive or continue admin portal sessions.
- Blocked `member` admin token/session issuance through:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh` for `portal=admin`
  - `POST /api/v1/auth/2fa/verify`
  - `POST /api/v1/auth/2fa/step-up`
- Kept employee portal login through `employee_accounts` unchanged.
- Kept current staff setup compatibility: authorized owners/admins can still create `member` users through `POST /api/v1/admin/users`, and `POST /api/v1/staff` can still use that `user_id`.
- Tightened `GET /api/v1/company/profile` and `PATCH /api/v1/company/profile` to owner-only as defense-in-depth.

Files changed:
- `apps/api/routers/auth.py`
- `apps/api/routers/company.py`
- `apps/api/tests/test_phase_r2d_member_admin_access.py`
- `DECISIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Known limitations:
- R.2d does not decouple `staff_profiles.user_id` from admin-auth `users`.
- R.2d does not remove the current staff setup ability to create `member` records.
- Existing short-lived legacy member access tokens are not mass-revoked by migration; admin refresh/session continuation is blocked.
- `manager` is still a future target role and is not implemented in the current backend tenant-role set.
- No frontend changes, employee credential redesign, step-up UX, migrations, or new endpoints were added.

Next recommended phase:
- Phase R.2e — Staff identity decoupling or resumed staff profile persistence migration using the hardened member-admin boundary.

## Phase R.1 Completion — Site Setup localStorage Cleanup / Backend Persistence Alignment

Phase R.1 has been implemented.

Scope:
- Confirmed normal site/store setup uses the backend store contract, not PRD-only site field names.
- Confirmed backend normal setup endpoints:
  - `POST /api/v1/stores`
  - `GET /api/v1/stores`
  - `GET /api/v1/stores/{store_id}`
  - `PATCH /api/v1/stores/{store_id}`
- Confirmed `/api/v1/sites` is currently the site-scoped rota/request/shift API family, not the normal store setup CRUD target.
- Removed the obsolete `forecourt_first_site` localStorage helper used for prototype first-site setup state.
- Kept the existing site setup form on the authenticated API client path and preserved its backend `createStore` flow.
- Preserved backend-backed admin dashboard readiness behavior through company profile, store list, and store readiness calls.

Files changed:
- `apps/web/components/admin/site-setup-form.tsx`
- `apps/web/lib/site-profile.ts`
- `DECISIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Checks:
- `cd apps/web && npm run build`: passed.
- `cd apps/web && npx tsc --noEmit`: passed after the build regenerated `.next/types`.
- `git diff --check`: passed.
- `grep -R "localStorage" -n apps/web/app apps/web/components apps/web/lib | head -100`: passed; no site setup localStorage source-of-truth helper remains.

Known limitations:
- Browser runtime save/reload verification remains human-only before commit.
- No backend API changes, migrations, auth/session changes, new dependencies, or new endpoint wiring were added.
- Store deactivation/archiving UI and step-up UX were not added.
- Opening-hours and staff setup remain broader nested setup surfaces; R.1 did not expand or redesign them.
- Staff frontend persistence migration remains a future phase.

Next recommended phase:
- Phase R.2 — Staff frontend real API migration.

## Phase R.0 Completion — Frontend Company Profile Real API Migration

Phase R.0 has been implemented.

Scope:
- Migrated the admin Company Setup/Profile form to use the existing backend company profile contract as its UI truth.
- Confirmed backend endpoints:
  - `GET /api/v1/company/profile`
  - `PATCH /api/v1/company/profile`
- Confirmed backend response fields: `tenant_id`, `company_name`, `owner_name`, `business_email`, `phone_number`, `registered_address`, `company_setup_completed`, and `company_setup_completed_at`.
- Confirmed backend update fields: `company_name`, `owner_name`, `business_email`, `phone_number`, and `registered_address`.
- Removed prototype-only company form fields that were not persisted by the backend contract.
- Removed the obsolete company profile mapper that filled non-persisted prototype defaults.
- Preserved the existing frontend authenticated API client path and did not change auth/session/token storage behavior.
- Kept admin dashboard setup progress backend-backed through company profile, store list, and store readiness calls.

Files changed:
- `apps/web/components/admin/company-setup-form.tsx`
- `apps/web/lib/company-profile.ts`
- `DECISIONS.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Checks:
- `cd apps/web && npx tsc --noEmit`: passed.
- `cd apps/web && npm run build`: passed.
- `git diff --check`: passed.
- `grep -R "localStorage" -n apps/web/app apps/web/components apps/web/lib | head -100`: passed; no company profile/setup localStorage truth remains.

Known limitations:
- Existing frontend auth/session handling still uses the current memory access-token plus refresh-cookie recovery path in `apps/web/lib/api-client.ts`; R.0 did not change it.
- Remaining localStorage usage is limited to auth cleanup of legacy keys and the pending site setup migration helper.
- Sites and staff frontend persistence migration remain future phases.
- No 2FA/step-up frontend UX was added.
- No backend API changes, migrations, tests, new dependencies, or auth/session architecture changes were made.

Next recommended phase:
- Phase R.1 — Sites frontend real API migration.

## Phase Q.5.2b Completion — Sensitive-Action Rollout Inspection Close-Out

Phase Q.5.2b has been completed as a documentation-only close-out after the sensitive-action endpoint inspection.

Scope:
- Recorded the Q.5.2b rollout boundary after inspecting currently-built backend endpoints.
- Kept the Q.5.2a step-up mechanism active and limited to the first protected sensitive endpoint, `POST /api/v1/stores/{store_id}/deactivate`.
- Documented that no additional currently-built endpoint should be wired in Q.5.2b.
- Documented that 2FA lifecycle endpoints remain protected by action-level factor proof rather than an extra step-up gate.
- Documented that admin-user creation remains a future Tier 1 candidate tied to onboarding/frontend 2FA and step-up UX.
- Documented that staff pay/compliance fields require future conditional field-level gating or dedicated pay/compliance endpoints.
- Documented that routine operational endpoints remain protected by RBAC, tenant/site isolation, validation, and audit logging rather than fresh step-up.

Files changed:
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Decision summary:
- Q.5.2a delivered the reusable session-bound step-up mechanism and protected store deactivation.
- Q.5.2b intentionally adds no new endpoint guard wiring.
- `POST /api/v1/auth/2fa/disable` and `POST /api/v1/auth/2fa/recovery-codes/regenerate` are not step-up gated now because they already require live action-level factor proof.
- `POST /api/v1/admin/users` remains a future governance/privilege step-up candidate once admin onboarding/user-management frontend flow supports owner 2FA enrolment and step-up.
- `POST /api/v1/staff` and `PATCH /api/v1/staff/{staff_id}` remain future pay/compliance gating candidates, but should not be blanket-gated while they are mixed-purpose staff profile endpoints.
- Routine store setup, company profile, coverage template, hour target, rota, shift, availability, request, hot food, rota recommendation, normal read, and staff job-tag metadata endpoints are not Q.5.2b step-up targets.

Checks:
- `git diff --check`: passed.
- `git status --short`: showed only the expected documentation changes before commit.
- `grep -n "Q.5.2b" IMPLEMENTATION_STATUS.md README.md HARDENING_BACKLOG.md DECISIONS.md || true`: passed.
- `grep -n "H060\|H073" HARDENING_BACKLOG.md`: passed.

Known limitations:
- No new endpoint guard wiring was added in Q.5.2b.
- H060 remains partial until future governance/pay/compliance/billing/export/erasure sensitive actions are either protected or explicitly build-time gated.
- H073 remains partial because email-verification enforcement currently applies only through protected sensitive actions, with store deactivation covered.
- No frontend step-up UI yet.
- No admin user-management frontend step-up flow yet.
- No dedicated staff pay/compliance endpoint split yet.
- No billing, payroll, compliance document, sensitive export, sensitive audit-log, or erasure modules yet.

Next recommended phase:
- Frontend/API migration or the next agreed product/security phase.

## Phase Q.5.2a Completion — Step-Up Auth Mechanism + Store Deactivation Gate

Phase Q.5.2a has been implemented.

Scope:
- Added server-side step-up freshness storage on `auth_sessions`.
- Added additive access-token `sid` claim for newly issued admin and employee access tokens so protected actions can resolve the current server-side session.
- Added `POST /api/v1/auth/2fa/step-up`.
- Added route-level SlowAPI limiting for step-up verification.
- Added reusable sensitive admin action dependency with owner role, email verification, active 2FA, and fresh step-up gates.
- Applied the sensitive-action dependency to `POST /api/v1/stores/{store_id}/deactivate`.
- Store deactivation is now owner-only and requires verified email, active 2FA, and fresh 2FA step-up.
- Added Q.5.2a auth security event vocabulary for step-up and sensitive-action blocking.
- Added focused Q.5.2a tests for step-up, recovery-code step-up, replay, rate limiting, store deactivation gates, owner-only behavior, tenant isolation, audit logging, and event leakage safety.

Files changed:
- `apps/api/alembic/versions/0030_phase_q5_2a_step_up_auth.py`
- `apps/api/core/deps.py`
- `apps/api/core/security.py`
- `apps/api/core/settings.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/models/auth_session.py`
- `apps/api/routers/auth.py`
- `apps/api/routers/stores.py`
- `apps/api/schemas/auth.py`
- `apps/api/tests/test_operational_domain.py`
- `apps/api/tests/test_phase_q5_2a_step_up.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Migration/model summary:
- Added Alembic migration `0030_phase_q5_2a_step_up_auth`.
- Added nullable `auth_sessions.last_2fa_step_up_at`.
- Extended auth security event constraints for `auth.2fa.step_up_succeeded`, `auth.2fa.step_up_failed`, `auth.sensitive_action.blocked`, and `auth.sensitive_action.allowed`.

Step-up behavior:
- Step-up freshness is stored on the current server-side `auth_sessions` row, not on the user.
- Step-up TTL is `TWO_FACTOR_STEP_UP_TTL_MINUTES=5`.
- Step-up endpoint is rate-limited by `RATE_LIMIT_2FA_STEP_UP=5/minute`.
- Step-up accepts exactly one current TOTP code or valid recovery code.
- Recovery codes used for step-up are consumed.
- TOTP replay protection still uses `totp_last_used_time_step`.

Sensitive-action behavior:
- `require_sensitive_admin_action("store.deactivate")` checks owner role, verified email, active 2FA, and fresh session-bound step-up.
- Store deactivation now rejects unverified owners, owners without active 2FA, owners without fresh step-up, admins, members, employee tokens, stale sessions, and cross-tenant store IDs.
- Existing store deactivation audit logging remains in place on success.

Known limitations:
- Q.5.2a only wires the sensitive-action dependency to store deactivation.
- H073 remains open/partial after Q.5.2b because only store deactivation is currently protected; future sensitive modules and approved Tier 1 flows must use the sensitive-action dependency at build time.
- No frontend step-up UI yet.
- No employee 2FA.
- No WebAuthn/passkeys, SMS/email OTP, tenant-wide 2FA policy, disaster recovery bypass, KMS/key rotation, or session revocation changes.

Checks:
- `python3 -m py_compile apps/api/core/security.py apps/api/core/settings.py apps/api/core/deps.py apps/api/models/auth_session.py apps/api/models/auth_security_event.py apps/api/routers/auth.py apps/api/routers/stores.py apps/api/schemas/auth.py apps/api/alembic/versions/0030_phase_q5_2a_step_up_auth.py apps/api/tests/test_phase_q5_2a_step_up.py apps/api/tests/test_operational_domain.py`: passed.
- Docker validation is pending because Docker daemon/API calls stopped responding in this environment during Q.5.2a validation.

Next recommended phase:
- Phase Q.5.2b — Sensitive-action rollout inspection close-out.

## Phase Q.5.1c Completion — Auth Test Runtime Profiling + Full Regression Gate

Phase Q.5.1c has been implemented as test-runtime and regression-gate work only.

Scope:
- Profiled the Q.5.1/Q.5.1b 2FA test file with `--durations=20` before changing code.
- Identified repeated production-cost bcrypt hashing and file-backed SQLite test engines as the practical runtime bottlenecks.
- Added explicit test-only bcrypt fast mode with `BCRYPT_TEST_FAST=true` set only by test infrastructure.
- Preserved production bcrypt cost by default with `BCRYPT_TEST_FAST=false` and production rounds fixed at 12.
- Added a guard test proving production bcrypt rounds remain the default when test fast mode is off.
- Added test-only SQLite engine normalization so file-backed SQLite test URLs use isolated in-memory engines during pytest.
- Kept product auth behavior, API contracts, production crypto, migrations, runtime dependencies, and feature scope unchanged.
- Ran the full backend regression suite as the Q.5.1c acceptance gate.

Files changed:
- `apps/api/core/settings.py`
- `apps/api/core/security.py`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_phase_q0_hardening_baseline.py`
- `apps/api/tests/test_phase_q5_1_totp_2fa.py`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Profiling summary:
- Initial focused Q.5.1/Q.5.1b profile before optimization: 19 passed, 3 skipped in 925.45s (0:15:25).
- Initial slowest entries were mostly test setup, with repeated 35-54 second setup durations across `test_phase_q5_1_totp_2fa.py`.
- A representative `test_auth.py::test_login_returns_access_token` run before the global SQLite fixture optimization spent 36.22s in setup and took 44.13s total.
- After optimization, the focused Q.5.1/Q.5.1b file ran in 18.76s and the full backend suite ran in 303.18s.

Checks:
- `python3 -m py_compile apps/api/core/settings.py apps/api/core/security.py apps/api/tests/conftest.py apps/api/tests/test_phase_q0_hardening_baseline.py apps/api/tests/test_phase_q5_1_totp_2fa.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q --durations=20"`: 19 passed, 3 skipped in 18.76s.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=true api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q -k rate_limit"`: 3 passed, 19 deselected in 9.70s.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q --durations=20"`: 354 passed, 5 skipped in 303.18s (0:05:03).

Known limitations:
- No production auth behavior changed.
- No step-up auth yet.
- H073 sensitive-action email-verification enforcement is not implemented yet.
- No frontend 2FA UI yet.
- No employee 2FA.
- No SMS OTP, email OTP, WebAuthn/passkeys, or tenant-wide require-2FA-for-all-admins policy.
- No disaster-recovery bypass process.
- No production KMS/key rotation implementation.

Next recommended phase:
- Phase Q.5.2 — Step-up auth + H073 sensitive-action enforcement.

## Phase Q.5.1b Completion — Disable 2FA + Recovery-Code Regeneration Backend

Phase Q.5.1b has been implemented.

Scope:
- Added backend lifecycle endpoints for active admin-side 2FA:
  - `POST /api/v1/auth/2fa/disable`
  - `POST /api/v1/auth/2fa/recovery-codes/regenerate`
- Added explicit SlowAPI route limits for both endpoints with defaults of `5/minute`.
- Added request/response schemas for disable and recovery-code regeneration.
- Added authenticated admin-side factor verification for lifecycle actions using current TOTP or a valid recovery code.
- Added current-password verification for disable 2FA.
- Added recovery-code consumption for lifecycle actions when a recovery code is used.
- Added unused recovery-code invalidation on disable and regeneration.
- Added Q.5.1b auth security events with safe metadata only.
- Added focused Q.5.1b tests for disable, regeneration, recovery-code consumption, state wiping, not-enabled guards, employee-token blocking, rate limiting, and event leakage safety.

Files changed:
- `apps/api/alembic/versions/0029_phase_q5_1b_2fa_lifecycle_events.py`
- `apps/api/core/settings.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/routers/auth.py`
- `apps/api/schemas/auth.py`
- `apps/api/tests/test_phase_q5_1_totp_2fa.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Migration/model summary:
- Added Alembic migration `0029_phase_q5_1b_2fa_lifecycle_events`.
- Extended the `auth_security_events.event_type` database CHECK constraint and model allowlist for `auth.2fa.disabled` and `auth.2fa.recovery_codes_regenerated`.
- No new tables were added.

Disable 2FA behavior:
- Requires an authenticated admin-side session, current password, and exactly one current TOTP code or valid recovery code.
- Recovery codes used for disable are consumed.
- Successful disable clears active encrypted TOTP fields, replay state, and pending enrolment state; sets `disabled_at`; invalidates unused recovery codes; and allows future enrolment to begin again.
- Disable returns `409 AUTH_2FA_NOT_ENABLED` when active 2FA is not enabled.
- Wrong password or wrong factor returns generic `400 AUTH_2FA_VERIFICATION_FAILED`.
- Employee tokens are blocked.
- Active session revocation on disable remains out of scope.

Recovery-code regeneration behavior:
- Requires an authenticated admin-side session and exactly one current TOTP code or valid recovery code.
- Recovery codes used for regeneration are consumed first.
- Regeneration invalidates old unused recovery codes, issues exactly 10 new recovery codes, returns them once, and keeps active encrypted TOTP state unchanged.
- Regeneration returns `409 AUTH_2FA_NOT_ENABLED` when active 2FA is not enabled.
- Wrong factor returns generic `400 AUTH_2FA_VERIFICATION_FAILED`.
- Employee tokens are blocked.

Security event summary:
- Added `auth.2fa.disabled` and `auth.2fa.recovery_codes_regenerated`.
- Verification failures reuse `auth.2fa.verification_failed`.
- Event metadata does not include passwords, TOTP codes, recovery codes, token hashes, raw secrets, encrypted secrets, `manual_secret`, `otpauth_url`, or challenge tokens.

Checks:
- `python3 -m py_compile apps/api/routers/auth.py apps/api/core/settings.py apps/api/schemas/auth.py apps/api/tests/test_phase_q5_1_totp_2fa.py apps/api/models/auth_security_event.py apps/api/alembic/versions/0029_phase_q5_1b_2fa_lifecycle_events.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q"`: 19 passed, 3 skipped.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=true api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q -k rate_limit"`: 3 passed, 19 deselected.

Known limitations:
- No step-up auth yet.
- H073 sensitive-action email-verification enforcement is not implemented yet.
- No frontend 2FA UI yet.
- No employee 2FA.
- No SMS OTP, email OTP, WebAuthn/passkeys, or tenant-wide require-2FA-for-all-admins policy.
- No owner transfer/demotion workflows.
- No disaster-recovery bypass process.
- No production KMS/key rotation implementation.
- Disable 2FA does not revoke all active sessions.
- Auth test runtime remains high and may need a focused profiling/hygiene phase.

Next recommended phase:
- Decide between a small Q.5.1c auth test runtime profiling/hygiene phase and Phase Q.5.2 — Step-up auth + H073 sensitive-action enforcement.

## Phase Q.5.1a Completion — 2FA Verify Rate Limiting

Phase Q.5.1a has been implemented as a small post-Q.5.1 hardening follow-up.

Scope:
- Added explicit SlowAPI route limiting for `POST /api/v1/auth/2fa/verify`.
- Added `RATE_LIMIT_2FA_VERIFY` setting with default `5/minute`.
- Added a focused rate-limit spot test that runs only when `RATE_LIMIT_ENABLED=true`.
- Kept normal Q.5.1 functional tests compatible with `RATE_LIMIT_ENABLED=false`.

Files changed:
- `apps/api/core/settings.py`
- `apps/api/routers/auth.py`
- `apps/api/tests/test_phase_q5_1_totp_2fa.py`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `HARDENING_BACKLOG.md`

Checks:
- `python3 -m py_compile apps/api/routers/auth.py apps/api/core/settings.py apps/api/tests/test_phase_q5_1_totp_2fa.py`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=true api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q -k rate_limit"`: passed.
- `git diff --check`: passed.

Known limitations:
- No 2FA disable endpoint yet.
- No recovery-code regeneration endpoint yet.
- No step-up auth yet.
- H073 sensitive-action email-verification enforcement is not implemented yet.
- No frontend 2FA UI yet.
- No employee 2FA.

Next recommended phase:
- Phase Q.5.1b — Disable 2FA + regenerate recovery codes backend.

## Phase Q.5.1 Completion — TOTP Enrolment + Login Verification + Recovery Codes Backend

Phase Q.5.1 has been implemented.

Scope:
- Added pinned direct `pyotp` and `cryptography` API dependencies for TOTP and AES-256-GCM.
- Added `TOTP_ENCRYPTION_KEY` setting and AES-256-GCM TOTP secret encryption/decryption utilities with 32-byte base64 key validation and key-version support.
- Added admin-side 2FA persistence with separate pending and active TOTP secret fields.
- Added server-side 2FA login challenges with hashed challenge tokens, five-minute expiry, single-use consumption, and failed-attempt locking.
- Extended `auth_tokens` for hash-only, single-use `recovery_code` tokens with nullable expiry for recovery codes.
- Added `/api/v1/auth/2fa/status`, `/api/v1/auth/2fa/totp/enrol/begin`, `/api/v1/auth/2fa/totp/enrol/confirm`, and `/api/v1/auth/2fa/verify`.
- Updated admin login so active 2FA users receive only a short-lived 2FA challenge until TOTP or recovery-code verification succeeds.
- Preserved existing password-only login/session behavior for users without active 2FA.
- Added Q.5.1 auth security events with safe metadata only.
- Added focused Q.5.1 backend tests for encryption, enrolment, login challenge, TOTP verification, recovery-code use, replay/lockout, role compatibility, employee-token blocking, and leakage checks.

Files changed:
- `apps/api/alembic/versions/0028_phase_q5_1_totp_2fa.py`
- `apps/api/core/settings.py`
- `apps/api/models/__init__.py`
- `apps/api/models/admin_user_2fa.py`
- `apps/api/models/auth_2fa_challenge.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/models/auth_token.py`
- `apps/api/requirements.txt`
- `apps/api/routers/auth.py`
- `apps/api/schemas/auth.py`
- `apps/api/services/totp_crypto.py`
- `apps/api/tests/test_phase_q5_1_totp_2fa.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Migration/model summary:
- Added Alembic migration `0028_phase_q5_1_totp_2fa`.
- Added `admin_user_2fa` with pending and active encrypted TOTP secret storage, enrolment timestamps, key-version fields, replay tracking, and disable placeholder timestamp.
- Added `auth_2fa_challenges` with stored challenge hashes only, expiry, failed-attempt count, lock timestamp, request context, and tenant/user binding.
- Extended `auth_tokens.token_type` to include `recovery_code` and made `auth_tokens.expires_at` nullable for recovery codes.
- Extended `auth_security_events` constraints for Q.5.1 2FA event names and safe failure reasons.

Login/auth behavior:
- Users without active 2FA continue to receive normal access token, refresh token, and refresh cookie from `/api/v1/auth/login`.
- Users with active 2FA no longer receive access/refresh tokens or a refresh cookie from `/api/v1/auth/login`; they receive `requires_2fa`, `two_factor_challenge_token`, and `token_type = "2fa_pending"`.
- `/api/v1/auth/2fa/verify` accepts exactly one TOTP code or recovery code with the challenge token, then issues the normal access/refresh tokens and refresh cookie on success.
- 2FA challenge tokens are opaque server-side challenges, not access tokens, not refresh tokens, and cannot access admin APIs.
- Employee tokens are blocked from admin-side 2FA status/enrolment endpoints.

Recovery-code behavior:
- `enrol/confirm` generates 10 high-entropy recovery codes after a valid first TOTP code.
- Recovery codes are shown once, stored only as SHA-256 hashes in `auth_tokens`, and consumed atomically with `used_at`.
- Recovery-code reuse is rejected.
- Recovery-code values and hashes are not logged.

Security event summary:
- Added safe Q.5.1 event coverage for enrolment started/completed, verification succeeded/failed, and recovery-code use.
- Failure reasons include `invalid_code`, `code_reused`, `rate_limited`, `challenge_expired`, and `challenge_invalid` where used by Q.5.1.
- Event metadata does not include TOTP secrets, TOTP codes, recovery codes, recovery-code hashes, challenge tokens, challenge-token hashes, passwords, cookies, Authorization headers, raw emails, `otpauth_url`, or `manual_secret`.

Checks:
- `python3 -m py_compile apps/api/core/settings.py apps/api/services/totp_crypto.py apps/api/models/admin_user_2fa.py apps/api/models/auth_2fa_challenge.py apps/api/models/auth_token.py apps/api/models/auth_security_event.py apps/api/schemas/auth.py apps/api/routers/auth.py apps/api/tests/test_phase_q5_1_totp_2fa.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed; installed `pyotp==2.9.0` and `cryptography==42.0.8`.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q5_1_totp_2fa.py -q"`: 13 passed.

Known limitations:
- No 2FA disable endpoint yet.
- No recovery-code regeneration endpoint yet.
- No step-up auth yet.
- H073 sensitive-action email-verification enforcement is not implemented yet.
- No frontend 2FA UI yet.
- No employee 2FA.
- No SMS OTP, email OTP, WebAuthn/passkeys, or tenant-wide require-2FA-for-all-admins policy.
- No owner transfer/demotion workflows.
- No disaster-recovery bypass process.
- H075 production KMS/key rotation hardening remains future work.

Next recommended phase:
- Phase Q.5.1b — Disable 2FA + regenerate recovery codes backend.

## Phase Q.5.0 Completion — 2FA Design Decisions

Phase Q.5.0 has been implemented as a design-only phase.

Scope:
- Added D039 for Owner 2FA, TOTP, recovery codes, login verification, and future sensitive-action step-up auth design.
- Selected TOTP using RFC 6238 as the default 2FA method for Q.5.1, with `pyotp` as the implementation target after Q.5.1 dependency verification.
- Rejected email OTP and SMS OTP for primary 2FA.
- Deferred WebAuthn/passkeys to a later phase.
- Chose AES-256-GCM encrypted TOTP secret storage with runtime `TOTP_ENCRYPTION_KEY` for Q.5.1, with no real keys committed.
- Chose single-use hashed recovery codes generated after enrolment confirmation.
- Chose owner-required enrolment with existing-owner action-gated grace before sensitive actions.
- Designed the 2FA login challenge-token flow, enrolment begin/confirm handshake, challenge lifecycle, replay protection, brute-force controls, disable/regeneration policies, and Q.5.2 step-up/H073 relationship.
- Added H075-H079 backlog items for TOTP key management hardening, tenant-wide admin 2FA policy, employee 2FA, WebAuthn/passkeys, and disaster recovery.

Files changed:
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Design summary:
- Q.5.0 adds no code, migrations, endpoints, dependencies, frontend UI, real secrets, auth behavior changes, RBAC behavior changes, employee auth changes, or tests beyond documentation/grep validation.
- Q.5.1 is scoped to TOTP enrolment, login verification, recovery codes backend, and encrypted TOTP secret storage.
- Q.5.2 is scoped to step-up auth plus H073 sensitive-action email-verification enforcement.
- Q.5.3 or later may handle frontend 2FA UI wiring if not included elsewhere.

Checks:
- `git status --short`: showed only Q.5.0 documentation files changed.
- `git diff --name-only`: showed only `DECISIONS.md`, `HARDENING_BACKLOG.md`, `IMPLEMENTATION_STATUS.md`, `README.md`, and `apps/api/docs/phase17_employee_api_contract.md`.
- `git diff --check`: passed.
- `grep -n "D039" -A220 DECISIONS.md`: passed.
- `grep -n "Q.5.0" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "Q.5.1" README.md IMPLEMENTATION_STATUS.md`: passed.
- `grep -n "H075" -A30 HARDENING_BACKLOG.md`: passed.
- `grep -n "H076" -A30 HARDENING_BACKLOG.md`: passed.
- `grep -n "H077" -A30 HARDENING_BACKLOG.md`: passed.
- `grep -n "H078" -A30 HARDENING_BACKLOG.md`: passed.
- `grep -n "H079" -A30 HARDENING_BACKLOG.md`: passed.
- `grep -n "TOTP_ENCRYPTION_KEY" README.md DECISIONS.md HARDENING_BACKLOG.md`: passed with placeholder/planning references only.
- `grep -R "TOTP_ENCRYPTION_KEY=.*[A-Za-z0-9+/=]\{20,\}" -n . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.next || true`: no matches.
- No backend/frontend tests were run because Q.5.0 is documentation-only.

Known limitations:
- 2FA not implemented yet.
- No TOTP endpoints yet.
- No recovery code endpoints yet.
- No frontend 2FA UI yet.
- No step-up auth yet.
- H073 not enforced yet.
- No tenant-level admin-wide 2FA policy yet.
- No employee 2FA yet.
- `pyotp` not installed yet.
- TOTP encryption/key management not implemented yet.

Next recommended phase:
- Phase Q.5.1 — TOTP enrolment + login verification + recovery codes backend.

## Phase Q.4.4 Completion — Owner/Admin Role Split

Phase Q.4.4 has been implemented.

Scope:
- Introduced `owner` as the tenant/business-owner role before Q.5 2FA work.
- Preserved existing `admin` and `member` tenant-role compatibility.
- Updated registration so a newly registered tenant's first membership is `owner`.
- Updated `/api/v1/auth/me` response typing so `active_tenant_role` may be `owner`.
- Added centralized admin-capable tenant-role helpers so current admin-capable backend dependencies allow `owner` and `admin`.
- Updated direct read-scope permission checks so `owner` receives the same access as current `admin`.
- Added focused Q.4.4 tests covering registration/auth, admin-compatible RBAC, member restriction, employee-token rejection, owner backfill, existing-owner preservation, and zero-user tenant backfill behavior.

Files changed:
- `apps/api/alembic/versions/0027_phase_q4_4_owner_role.py`
- `apps/api/core/deps.py`
- `apps/api/routers/auth.py`
- `apps/api/routers/availability.py`
- `apps/api/routers/shift_requests.py`
- `apps/api/routers/shifts.py`
- `apps/api/routers/sites.py`
- `apps/api/routers/staff.py`
- `apps/api/schemas/auth.py`
- `apps/api/tests/test_auth.py`
- `apps/api/tests/test_phase14_onboarding_directory.py`
- `apps/api/tests/test_phase_k1_employee_identity_hardening.py`
- `apps/api/tests/test_phase_k2_employee_login_site_lookup.py`
- `apps/api/tests/test_phase_q4_4_owner_role.py`
- `apps/web/lib/api-client.ts`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Migration/model summary:
- Added Alembic migration `0027_phase_q4_4_owner_role`.
- `tenant_users.role` has no database CHECK constraint in the current schema, so `owner` is enabled at the application/RBAC layer.
- Existing tenants with no owner are backfilled to one owner.
- Backfill selection uses earliest admin by associated `users.created_at`, then `tenant_users.id`; if no admin exists, it uses earliest tenant membership by the same ordering.
- The current `tenant_users` table has no `created_at`, so `users.created_at` is the available deterministic timestamp.
- Tenants that already have an owner are left unchanged.
- Tenants with zero `tenant_users` are skipped safely.

Registration/auth behavior:
- New tenant registration now creates the initial membership as `owner` instead of `admin`.
- `/api/v1/auth/me` can return `active_tenant_role = "owner"`.
- Existing login, refresh, session-family, password reset, and email verification behavior is otherwise unchanged.

RBAC compatibility summary:
- `owner` can access endpoints currently guarded by `require_tenant_role("admin")`.
- Existing `admin` role access continues to work.
- Existing `member` restrictions remain in place for admin-only mutations.
- Employee tokens remain rejected from admin APIs.
- Direct router/core permission comparisons against `role == "admin"` and `role != "admin"` were removed in favor of the shared admin-role helper.

Checks:
- `python3 -m py_compile apps/api/core/deps.py apps/api/routers/auth.py apps/api/routers/availability.py apps/api/routers/shift_requests.py apps/api/routers/shifts.py apps/api/routers/sites.py apps/api/routers/staff.py apps/api/schemas/auth.py apps/api/alembic/versions/0027_phase_q4_4_owner_role.py apps/api/tests/test_auth.py apps/api/tests/test_phase14_onboarding_directory.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_k2_employee_login_site_lookup.py apps/api/tests/test_phase_q4_4_owner_role.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q4_4_owner_role.py -q"`: 4 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_auth.py apps/api/tests/test_phase_q4_4_owner_role.py apps/api/tests/test_phase_q4_3_email_verification.py apps/api/tests/test_phase_q4_2_password_reset.py apps/api/tests/test_phase_q4_1_email_service.py apps/api/tests/test_phase_q3_3_session_family_reuse.py apps/api/tests/test_phase_q3_2_1_auth_security_events.py apps/api/tests/test_phase_q3_1_auth_csrf.py apps/api/tests/test_phase_q2_auth_sessions.py -q"`: 99 passed, 1 skipped.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_company_profile.py apps/api/tests/test_phase_c_staff_setup_flow.py apps/api/tests/test_phase_d1_staff_directory.py apps/api/tests/test_phase_f_store_settings.py -q"`: 34 passed.
- `cd apps/web && npm run build`: passed.
- `cd apps/web && npx tsc --noEmit`: passed.
- `git diff --check`: passed.
- `grep -rn "role *== *['\"]admin['\"]" apps/api/routers apps/api/core || true`: no matches.
- `grep -rn "role *!= *['\"]admin['\"]" apps/api/routers apps/api/core || true`: no matches.
- Full backend suite not run for Q.4.4 because the targeted owner-role suite, auth/RBAC regression bundle, business-RBAC bundle, Alembic validation, and frontend checks passed, and H072 tracks backend suite runtime hardening.

Known limitations:
- No 2FA yet.
- No step-up authentication yet.
- No owner transfer workflow.
- No owner downgrade/promotion UI.
- No full manager role implementation.
- Zero-user/orphan tenants are skipped by the owner backfill and may require manual remediation.
- H073 sensitive-action email-verification enforcement remains future/pre-launch.
- Q.5.0 must design TOTP, recovery, and step-up rules before implementation.

Next recommended phase:
- Phase Q.5.0 — 2FA Design Decisions.

## Phase Q.4.3 Completion — Admin Email Verification Backend

Phase Q.4.3 has been implemented.

Scope:
- Added `users.email_verified_at` for admin-side email verification state.
- Added authenticated admin-side `POST /api/v1/auth/email-verification/request`.
- Added public admin-side `POST /api/v1/auth/email-verification/confirm`.
- Implemented the `email_verification` token flow using the Q.4.2 `auth_tokens` table/model.
- Added high-entropy raw token generation with `secrets.token_urlsafe(32)` and SHA-256 token hashing.
- Added 24-hour email verification expiry.
- Added Q.4.1 `EmailService` usage with `email_verification` template ID.
- Added atomic single-use token consumption for confirm.
- Added second read-only token lookup for internal rejection classification after failed atomic consumption.
- Added already-verified request handling without token creation or email sending.
- Added safe stale-token handling for already verified users without overwriting the original verification timestamp.
- Added safe auth security events for requested, completed, token rejected, and already verified states.
- Added the existing SlowAPI route/IP-level email verification request limiter at `RATE_LIMIT_EMAIL_VERIFICATION_REQUEST=10/hour`.

Files changed:
- `apps/api/alembic/versions/0026_phase_q4_3_email_verified_at.py`
- `apps/api/models/user.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/core/settings.py`
- `apps/api/routers/auth.py`
- `apps/api/schemas/auth.py`
- `apps/api/tests/test_phase_q4_3_email_verification.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Migration/model summary:
- Added nullable `users.email_verified_at` with no backfill.
- Existing users remain unverified until they complete verification or a later explicit admin/migration process updates them.
- Extended `auth_security_events` constraints/model vocabulary for Q.4.3 email verification events and token rejection reasons.
- Reused the existing `auth_tokens` token type allowance for `email_verification`.

Endpoint summary:
- `POST /api/v1/auth/email-verification/request`: authenticated admin-side verification request/resend endpoint.
- `POST /api/v1/auth/email-verification/confirm`: public admin-side verification confirmation endpoint returning `{"success": true}` on successful verification.

Security behavior:
- Raw verification tokens are sent only once through the email service and are never stored.
- Token hashes are stored only in `auth_tokens` and are not logged.
- Request/resend identity comes from the authenticated admin token, not from request body email/user fields.
- Employee tokens cannot request admin email verification.
- Already verified request attempts return a safe message, create no token row, send no email, and log `auth.email_verification.already_verified`.
- Failed token consumption is classified internally with a read-only SELECT as `invalid`, `expired`, `used`, or `wrong_type`; the client receives a generic token failure.
- Successful email verification consumes the token, sets `users.email_verified_at` if needed, logs `auth.email_verification.completed`, and does not revoke active admin sessions.
- Valid tokens for already verified users are consumed safely without overwriting the original `email_verified_at`.
- Unverified admin users can still log in, per D038.

Checks:
- `python3 -m py_compile apps/api/core/settings.py apps/api/models/user.py apps/api/models/auth_security_event.py apps/api/routers/auth.py apps/api/schemas/auth.py apps/api/tests/test_phase_q4_3_email_verification.py apps/api/alembic/versions/0026_phase_q4_3_email_verified_at.py`: passed.
- `git status --short`: showed the expected Q.4.3 changed files before validation.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q4_3_email_verification.py -q"`: 18 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q4_3_email_verification.py apps/api/tests/test_phase_q4_2_password_reset.py apps/api/tests/test_phase_q4_1_email_service.py apps/api/tests/test_phase_q3_3_session_family_reuse.py apps/api/tests/test_phase_q3_2_1_auth_security_events.py apps/api/tests/test_phase_q3_1_auth_csrf.py apps/api/tests/test_phase_q2_auth_sessions.py apps/api/tests/test_auth.py -q"`: 95 passed, 1 skipped.
- Full backend suite not rerun for Q.4.3 because the targeted email verification suite and key auth regression set passed, the full suite is slow in this environment, and H072 now tracks backend suite runtime hardening.
- `git diff --check`: passed.
- `grep -n "Q.4.3" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "Q.5" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "H059" HARDENING_BACKLOG.md`: passed; H059 is Done.
- `grep -n "H060" HARDENING_BACKLOG.md`: passed; H060 remains Open.
- `grep -n "H072" HARDENING_BACKLOG.md`: passed; H072 was Open at the time of Q.4.3 validation.
- `grep -n "H073" HARDENING_BACKLOG.md`: passed; H073 is Open.
- `grep -n "H074" HARDENING_BACKLOG.md || true`: passed; H074 is Open.
- `grep -n "auth.email_verification" DECISIONS.md apps/api/models/auth_security_event.py`: passed.
- `grep -n "email_verified_at" apps/api/models/user.py apps/api/alembic/versions/*.py`: passed.

Known limitations:
- The backend email verification flow is implemented, but the frontend verification page `/admin/verify-email?token=...` is not implemented in Q.4.3.
- The verification URL may point to a future frontend route until a dedicated frontend account-recovery/auth wiring phase.
- Unverified admin users can still log in, per D038.
- Sensitive-action enforcement until email verified remains deferred to H073.
- 2FA remains deferred to Q.5.
- Real email provider integration remains deferred.
- H072 slow backend suite remained open at the time of Q.4.3 and was resolved later in Q.5.1c.
- Q.4.3 implements the existing SlowAPI route/IP-level email verification request limiter at `RATE_LIMIT_EMAIL_VERIFICATION_REQUEST=10/hour`. The D038 target of 3 per user per hour remains H074 future hardening because implementing identifier-specific limits safely requires a repo-consistent rate-limit storage strategy and must not add Redis/new infrastructure in Q.4.3.

Next recommended phase:
- Phase Q.5 — Owner and sensitive-action 2FA.

## Phase Q.4.2 Completion — Admin Password Reset Backend

Phase Q.4.2 has been implemented.

Scope:
- Added the generic `auth_tokens` table/model foundation chosen in D038.
- Implemented the `password_reset` token type only.
- Added public admin-side `POST /api/v1/auth/password-reset/request`.
- Added public admin-side `POST /api/v1/auth/password-reset/confirm`.
- Added high-entropy raw token generation with `secrets.token_urlsafe(32)` and SHA-256 token hashing.
- Added 1-hour password reset expiry.
- Added generic 202 request behavior for known, unknown, and disabled users.
- Added safe dummy token/hash work for unknown and disabled reset requests.
- Added Q.4.1 `EmailService` usage with `password_reset` template ID.
- Added atomic single-use token consumption for confirm.
- Added second read-only token lookup for internal rejection classification after failed atomic consumption.
- Added active admin session revocation after successful password reset.
- Added safe auth security events for requested, completed, token rejected, and session revoked states.
- Added the existing SlowAPI route/IP-level password reset request limiter at `RATE_LIMIT_PASSWORD_RESET_REQUEST=10/hour`.

Files changed:
- `apps/api/alembic/versions/0025_phase_q4_2_auth_tokens.py`
- `apps/api/models/auth_token.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/models/__init__.py`
- `apps/api/core/settings.py`
- `apps/api/routers/auth.py`
- `apps/api/schemas/auth.py`
- `apps/api/tests/test_phase_q4_2_password_reset.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Migration/model summary:
- Added `auth_tokens` with `id`, `token_type`, `user_id`, `token_hash`, `expires_at`, `used_at`, `created_at`, `created_ip`, `consumed_ip`, `created_user_agent`, `consumed_user_agent`, `request_id`, and `metadata_json`.
- Added allowed token types `password_reset` and `email_verification` at the table/model level.
- Added unique index on `token_hash`.
- Added indexes on `user_id + token_type + created_at` and `token_type + expires_at`.
- Extended `auth_security_events` constraints/model vocabulary for Q.4.2 password reset events and token rejection reasons.

Endpoint summary:
- `POST /api/v1/auth/password-reset/request`: public admin-side reset request endpoint returning generic 202 for all email states.
- `POST /api/v1/auth/password-reset/confirm`: public admin-side reset confirmation endpoint returning `{"success": true}` on successful password reset.

Security behavior:
- Raw reset tokens are sent only once through the email service and are never stored.
- Token hashes are stored only in `auth_tokens` and are not logged.
- Unknown and disabled email reset attempts return generic 202, log `auth.password_reset.requested` with `user_id=NULL`, do not include raw email in metadata, do not create token rows, and do not send email.
- Failed token consumption is classified internally with a read-only SELECT as `invalid`, `expired`, `used`, or `wrong_type`; the client receives a generic token failure.
- Successful password reset consumes the token, updates the user password hash, revokes active admin sessions for the user, and logs one session-revoked event per revoked session.

Checks:
- `python3 -m py_compile apps/api/core/settings.py apps/api/models/auth_token.py apps/api/models/auth_security_event.py apps/api/models/__init__.py apps/api/schemas/auth.py apps/api/routers/auth.py apps/api/tests/test_phase_q4_2_password_reset.py apps/api/alembic/versions/0025_phase_q4_2_auth_tokens.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q4_2_password_reset.py -q"`: 16 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q4_1_email_service.py apps/api/tests/test_phase_q3_3_session_family_reuse.py apps/api/tests/test_phase_q3_2_1_auth_security_events.py apps/api/tests/test_phase_q3_1_auth_csrf.py apps/api/tests/test_phase_q2_auth_sessions.py apps/api/tests/test_auth.py -q"`: 60 passed, 1 skipped.
- Full backend suite not rerun for Q.4.2 because the targeted password reset suite and key auth regression set passed, and the full suite is slow in this environment.
- `git diff --check`: passed.
- `grep -n "Q.4.2" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "Q.4.3" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "H058" HARDENING_BACKLOG.md`: passed; H058 is Done.
- `grep -n "H059" HARDENING_BACKLOG.md`: passed; H059 remains Open.
- `grep -n "H060" HARDENING_BACKLOG.md`: passed; H060 remains Open.
- `grep -n "H070" HARDENING_BACKLOG.md`: passed; H070 is Open.
- `grep -n "H071" HARDENING_BACKLOG.md || true`: passed; H071 is Open.
- `grep -n "auth.password_reset" DECISIONS.md`: passed.

Known limitations:
- The backend password reset flow is implemented, but the frontend reset page `/admin/reset-password?token=...` is not implemented in Q.4.2.
- The reset URL may point to a future frontend route until a dedicated frontend account-recovery/auth wiring phase.
- Email verification remains deferred to Q.4.3.
- 2FA remains deferred to Q.5.
- Password reuse/history enforcement remains deferred to H070.
- Q.4.2 implements the existing SlowAPI route/IP-level password reset request limiter at `RATE_LIMIT_PASSWORD_RESET_REQUEST=10/hour`. The D038 target of 3 per email per hour remains H071 future hardening because implementing identifier-specific limits safely requires a repo-consistent rate-limit storage strategy and must not add Redis/new infrastructure in Q.4.2.
- Real email provider integration remains deferred.

Next recommended phase:
- Phase Q.4.3 — Admin email verification backend.

## Phase Q.4.1 Completion — Email Service Abstraction + Local/Test Email Backend

Phase Q.4.1 has been implemented.

Scope:
- Added a small internal email service foundation for future Q.4.2 password reset and Q.4.3 email verification work.
- Added an `EmailService` protocol accepting `to`, `template_id`, and optional context.
- Added `LocalLogEmailService`, which logs only a safe email-send event and never sends real email.
- Added recipient email redaction for local logs using `***@domain (lp:<4-char-sha256-prefix>)`.
- Added allowlist-based context logging for local logs, with unknown keys redacted by default.
- Added hard redaction for sensitive context keys including tokens, token hashes, passwords, cookies, auth headers, reset URLs, verification URLs, and verification codes.
- Added `TestCaptureEmailService`, which captures payloads in memory for tests without logging or persisting them.
- Added `EMAIL_BACKEND` setting with explicit Q.4.1 values `local_log` and `test_capture`.
- Added `get_email_service` factory with deterministic failure for unknown backend values.

Files changed:
- `apps/api/core/settings.py`
- `apps/api/services/email/__init__.py`
- `apps/api/services/email/base.py`
- `apps/api/services/email/local.py`
- `apps/api/services/email/capture.py`
- `apps/api/tests/test_phase_q4_1_email_service.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Checks:
- `git status --short`: showed the expected Q.4.1 changed files before validation.
- `python3 -m py_compile apps/api/core/settings.py apps/api/services/email/__init__.py apps/api/services/email/base.py apps/api/services/email/local.py apps/api/services/email/capture.py apps/api/tests/test_phase_q4_1_email_service.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q4_1_email_service.py -q"`: 7 passed.
- `git diff --check`: passed.
- `grep -n "Q.4.1" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "Q.4.2" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "H058" HARDENING_BACKLOG.md`: passed; H058 remains Open.
- `grep -n "H059" HARDENING_BACKLOG.md`: passed; H059 remains Open.
- `grep -n "H060" HARDENING_BACKLOG.md`: passed; H060 remains Open.
- Full backend suite not run for Q.4.1 because the targeted email-service test and Alembic validation passed and the full suite is slow in this environment.

Known limitations:
- Q.4.1 adds no real email provider.
- Q.4.1 adds no password reset endpoints.
- Q.4.1 adds no email verification endpoints.
- Q.4.1 adds no `auth_tokens` table or migrations.
- Q.4.1 adds no frontend changes and no auth/session behavior changes.
- H058 password reset remains open.
- H059 email verification remains open.
- H060 Owner/sensitive-action 2FA remains open.

Next recommended phase:
- Phase Q.4.2 — Admin password reset backend.

## Phase Q.4.0 Completion — Email/Auth Token Infrastructure Design

Phase Q.4.0 has been completed as a documentation/design-only phase.

Scope:
- Added D038 to define the shared email/auth token infrastructure for H058 password reset and H059 email verification.
- Chose admin-side users only for Q.4 password reset and email verification.
- Deferred employee account recovery because employees authenticate through site-scoped employee credentials.
- Chose one generic future `auth_tokens` table with a `token_type` discriminator for `password_reset` and `email_verification`.
- Chose high-entropy single-use raw tokens generated with `secrets.token_urlsafe(32)`, with only SHA-256 token hashes stored.
- Chose initial expiry windows of 1 hour for password reset and 24 hours for email verification.
- Defined account enumeration defences, generic response wording, email service abstraction shape, email verification login policy, password-reset session revocation expectation, planned auth security event vocabulary, planned rate limits, and Q.4 implementation split.

Guardrails:
- Documentation/design only.
- No backend code changes.
- No frontend code changes.
- No migrations.
- No tests added.
- No dependencies added.
- No auth behavior changes.
- No password reset endpoints.
- No email verification endpoints.
- No email service code.
- No token model/table implementation.
- H058 password reset remains open.
- H059 email verification remains open.
- H060 Owner/sensitive-action 2FA remains open.

Files changed:
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Checks:
- `git diff --name-only`: reviewed; changed files are documentation only.
- `git diff --check`: passed.
- `grep -n "D038" DECISIONS.md`: passed.
- `grep -n "Q.4.0" README.md IMPLEMENTATION_STATUS.md HARDENING_BACKLOG.md`: passed.
- `grep -n "H058" HARDENING_BACKLOG.md`: passed; H058 remains Open.
- `grep -n "H059" HARDENING_BACKLOG.md`: passed; H059 remains Open.
- `grep -n "H060" HARDENING_BACKLOG.md`: passed; H060 remains Open.

Next recommended phase:
- Phase Q.4.1 — Email service abstraction + local/test email backend.

## Phase Q.3.3 Completion — Refresh-Token Reuse Detection / Session Family Hardening

Phase Q.3.3 has been implemented.

Scope:
- Implemented H066 refresh-token reuse detection using a session-family pattern.
- Added nullable `session_family_id`, nullable `parent_session_id`, and nullable `reuse_detected_at` to `auth_sessions`.
- Migration 0024 revokes pre-existing active auth sessions instead of backfilling fake family IDs.
- New login-created admin and employee sessions create non-null root session family IDs.
- Refresh-created child sessions reuse the parent family and set `parent_session_id` to the rotated session.
- Reuse of an already-rotated refresh token revokes every session in the affected family and returns the existing generic refresh failure.
- Later refresh attempts from a family already revoked for reuse log `auth.session.rejected` with `rejection_reason=family_revoked`.
- Extended D037 vocabulary with `auth.session.reuse_detected`, `auth.session.revoked_by_family_reuse`, and `family_revoked`.
- Preserved D036 cookie-backed refresh CSRF behavior and bearer-token compatibility.
- No frontend files, new endpoints, password reset, email verification, 2FA, all-sessions logout, or bearer-removal work was added.
- `apps/api/docs/phase17_employee_api_contract.md` did not need an update because public auth response shapes and endpoint contracts are unchanged.

Files changed:
- `apps/api/alembic/versions/0024_phase_q3_3_session_family.py`
- `apps/api/models/auth_session.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/routers/auth.py`
- `apps/api/tests/test_phase_q3_3_session_family_reuse.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Migration/model summary:
- Added nullable `auth_sessions.session_family_id`, `auth_sessions.parent_session_id`, and `auth_sessions.reuse_detected_at`.
- Added `ix_auth_sessions_session_family_id`.
- Added nullable `parent_session_id` self-FK with `ON DELETE SET NULL`.
- Revokes all pre-existing active `auth_sessions` during upgrade without assigning fake family IDs.
- Updates the existing `auth_security_events` CHECK constraints only to allow the D037 Q.3.3 vocabulary extension required by the new events.

Checks:
- `python3 -m py_compile apps/api/routers/auth.py apps/api/models/auth_session.py apps/api/models/auth_security_event.py apps/api/tests/test_phase_q3_3_session_family_reuse.py apps/api/alembic/versions/0024_phase_q3_3_session_family.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini downgrade 0023_phase_q3_2_1_auth_security_events && alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q3_3_session_family_reuse.py -q"`: 19 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q3_2_1_auth_security_events.py apps/api/tests/test_phase_q3_1_auth_csrf.py apps/api/tests/test_phase_q2_auth_sessions.py -q"`: 29 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q"`: 288 passed, 2 skipped.
- Frontend build/typecheck not run because Q.3.3 made no frontend or package changes.

Known limitations:
- `session_family_id` remains nullable at the database level so old/null rows can age out safely; application code requires a family ID for new sessions.
- Retention enforcement for `auth_security_events` remains deferred to a later operational phase.
- H058 password reset remains open for Q.4.
- H059 email verification remains open for Q.4.
- H060 Owner/sensitive-action 2FA remains open for Q.5.
- H067 all-sessions logout remains future hardening.
- H068 same-origin deployment/session routing validation remains future hardening.
- H069 bearer-token deprecation/removal remains future hardening.

Next recommended phase:
- Phase Q.4 — Password reset and email verification foundation.

## Phase Q.3.2.1 Completion — Auth/Session Audit Logging With Dedicated Auth Security Events Storage

Phase Q.3.2.1 has been implemented.

Scope:
- Added dedicated `auth_security_events` storage for auth/session/security audit events.
- Preserved the existing tenant/user-scoped `audit_logs` table for business-action audit events.
- Added audit logging for refresh/session issuance, refresh rotation, logout/session revocation, refresh rejection reasons, disabled admin user refresh blocks, disabled employee account refresh blocks, and inactive linked staff profile refresh blocks.
- Added nullable subject/session references for unresolved auth/security events.
- Added safe request context fields for request ID, IP address, and user agent.
- Locked event vocabulary and metadata safety rules in D037.
- Confirmed raw tokens, token hashes, passwords, cookies, authorization headers, and secret material are not written to auth security events.
- Kept H066 refresh-token reuse detection/session family out of scope for Q.3.3.

Files changed:
- `apps/api/alembic/versions/0023_phase_q3_2_1_auth_security_events.py`
- `apps/api/models/auth_security_event.py`
- `apps/api/models/__init__.py`
- `apps/api/routers/auth.py`
- `apps/api/tests/test_phase_q3_2_1_auth_security_events.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Migration/model summary:
- Added `auth_security_events` with nullable tenant, admin user, employee account, and auth session references so unresolved security events do not need fake subject values.
- Added constrained `event_type`, `rejection_reason`, and `portal` values matching D037.
- Added raw nullable `ip_address`, raw nullable `user_agent`, nullable `request_id`, and nullable safe `metadata_json`.
- Added indexes for tenant, user, employee account, event/rejection reason, IP address, and auth session lookup patterns.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q3_2_1_auth_security_events.py -q"`: 12 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q"`: 269 passed, 2 skipped.
- Frontend build/typecheck not run because Q.3.2.1 made no frontend or package changes.

Known limitations:
- Retention enforcement for `auth_security_events` is deferred to a later operational phase.
- H066 refresh-token reuse detection/session family remains open for Q.3.3.
- H067 all-sessions logout remains future hardening.
- H068 same-origin production deployment/session routing validation remains future hardening.
- H069 bearer-token deprecation/removal remains future hardening.
- H058 password reset remains Q.4.
- H059 email verification remains Q.4.
- H060 Owner/sensitive-action 2FA remains Q.5.

Next recommended phase:
- Phase Q.3.3 — Refresh-token reuse detection / session family hardening.

## Phase Q.3.2 Completion — Auth Security Event Audit Storage Design

Phase Q.3.2 has been completed as a design/scoping phase.

Scope:
- Confirmed the existing `audit_logs` table cannot safely store unresolved auth/security events because it requires non-null `tenant_id` and `user_id`.
- Chose dedicated `auth_security_events` storage for auth/session/security audit events.
- Designed nullable subject/session fields for unresolved events such as invalid refresh tokens.
- Chose raw nullable IP address and user-agent storage for security investigation with a 365-day retention expectation and UK GDPR privacy-notice follow-up.
- Defined safe `metadata_json` rules and forbidden secret/token/header/cookie/password values.
- Kept H066 refresh-token reuse detection/session-family handling out of scope for Q.3.3.

Guardrails:
- Design/scoping only.
- No code changes.
- No migrations.
- No tests added.
- No auth behavior changes.

Next recommended phase:
- Phase Q.3.2.1 — Auth/session audit logging with dedicated auth security events storage.

## Phase Q.3.1.1 Completion — Backlog Numbering and Phase Split Documentation Cleanup

Phase Q.3.1.1 has been completed as a documentation-only cleanup before Q.3.2.

Scope:
- Corrected backlog numbering documentation so H058 is password reset flow and remains Open.
- Corrected frontend auth cookie/session migration references to H062 and kept H062 Done.
- Split the next auth hardening work into Q.3.2 for H065 audit logging and Q.3.3 for H066 refresh-token reuse detection/session-family hardening.
- Updated README Current Focus and phase table to show Q.3.2 and Q.3.3 as separate phases.
- Updated H065 suggested phase to Phase Q.3.2 and H066 suggested phase to Phase Q.3.3.

Files changed:
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `DECISIONS.md`

Guardrails:
- Documentation-only cleanup.
- No backend code changes.
- No frontend code changes.
- No tests added.
- No migrations added.
- Q.3.2 audit logging was not implemented.
- Q.3.3 refresh-token reuse detection was not implemented.

Validation:
- Documentation grep checks for stale H058/H062 wording were run.
- Backend/frontend tests were not run because Q.3.1.1 is documentation-only.

Next recommended phase:
- Phase Q.3.2 — Auth/session audit logging.

## Phase Q.3.1 Completion — Frontend Cookie/Session Migration + CSRF Protection

Phase Q.3.1 has been implemented.

Scope:
- Implemented D036 cookie-backed browser session migration for Admin Portal and Employee Portal.
- Added backend CSRF/custom-header enforcement for cookie-backed `POST /api/v1/auth/refresh` and `POST /api/v1/auth/logout`.
- Preserved body refresh-token compatibility and bearer-token compatibility during the D036 deprecation window.
- Migrated active frontend access-token handling to memory-only state.
- Added cookie-backed session restoration on admin and employee portal load.
- Added refresh-on-401 behaviour with one retry and shared in-flight refresh per portal.
- Wired logout to call backend session revocation, clear local auth state, and clear legacy localStorage token keys.
- Preserved employee site-code login UX and admin/employee portal separation.

Files changed:
- `apps/api/routers/auth.py`
- `apps/api/tests/test_phase_q2_auth_sessions.py`
- `apps/api/tests/test_phase_q3_1_auth_csrf.py`
- `apps/web/lib/api-client.ts`
- `apps/web/lib/auth-token.ts`
- `apps/web/lib/employee-auth-token.ts`
- `apps/web/components/admin/admin-login-form.tsx`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/app/employee/login/page.tsx`
- `apps/web/app/employee/page.tsx`
- `apps/web/app/employee/availability/page.tsx`
- `apps/web/app/employee/requests/page.tsx`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`

Backend changes:
- Added `X-Requested-With: ForecourtOS` enforcement only when refresh/logout uses the configured HTTP-only refresh cookie.
- Kept request-body refresh-token refresh/logout compatibility where currently supported.
- Kept bearer-token protected endpoints outside broad CSRF enforcement.
- Changed refresh-cookie SameSite from `lax` to `strict`.
- Kept refresh-token hashing, rotation, revocation, disabled-user blocking, employee/admin portal boundaries, and safe error responses intact.

Frontend changes:
- `forecourt_access_token` and `forecourt_employee_access_token` are no longer used for active token reads/writes.
- Active admin and employee access tokens are stored in module memory only.
- Legacy localStorage token keys are cleared during login, migration/session restoration paths, and logout.
- Admin and employee sessions restore via `/api/v1/auth/refresh` with `credentials: "include"` and `X-Requested-With: ForecourtOS`.
- API requests that receive `401` attempt one portal-aware refresh, share the in-flight refresh across parallel failures, and retry the original request once.
- Refresh failure clears in-memory auth state and routes users back to the correct login surface.
- Admin and employee logout call `/api/v1/auth/logout` with `credentials: "include"` and `X-Requested-With: ForecourtOS`.

Cookie attribute verification:
- `HttpOnly`: actual refresh cookie is set with `httponly=True`.
- `Secure`: actual refresh cookie uses `secure=True` unless `ENV` is `dev`, `test`, or `local`; local Docker/dev remains compatible with non-HTTPS.
- `SameSite`: actual refresh cookie is `strict`, matching D036.
- `Path`: actual refresh cookie path is `/api/v1/auth`, matching D036.
- `Domain`: no Domain is set, so the cookie is host-only, matching D036.
- `Max-Age` / TTL: actual Max-Age is `REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60`; current default is 14 days, matching the server-side refresh/session expiry.
- Deltas vs D036: none for the implemented cookie attributes.

Hardening backlog updates:
- H056 marked Done because active frontend localStorage access-token dependency has been removed.
- H062 marked Done because frontend auth cookie/session migration completion criteria are met.
- H061 marked Done because cookie-backed refresh/logout CSRF/header enforcement is implemented and tested.
- H067 all-sessions logout remains future hardening.
- H068 same-origin deployment/session routing validation remains future deployment hardening.
- H069 bearer-token deprecation/removal remains post-migration hardening.

Checks:
- `python3 -m py_compile apps/api/routers/auth.py apps/api/tests/test_phase_q2_auth_sessions.py apps/api/tests/test_phase_q3_1_auth_csrf.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q3_1_auth_csrf.py -q"`: 8 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q2_auth_sessions.py -q"`: 9 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_auth.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_q2_auth_sessions.py apps/api/tests/test_phase17_employee_portal.py apps/api/tests/test_main.py -q"`: 39 passed, 1 skipped.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q"`: 257 passed, 2 skipped.
- `cd apps/web && npx tsc --noEmit`: passed.
- `cd apps/web && npm run build`: passed.

Known limitations:
- Bearer-token compatibility remains during the D036 deprecation window.
- Auth/session lifecycle audit logging remains open as H065.
- Refresh-token reuse detection/session-family handling remains open as H066.
- All-sessions logout remains future hardening as H067.
- Same-origin production deployment/session routing validation remains open as H068.
- Bearer-token deprecation/removal follow-up remains open as H069.
- Password reset/email verification remain Q.4.
- Owner 2FA remains Q.5.

Next recommended phase:
- Phase Q.3.2 — Auth/session audit logging.
- Phase Q.3.3 — Refresh-token reuse detection / session family hardening.

## Phase Q.3.0.1 Completion — D036 Documentation Cleanup

Phase Q.3.0.1 has been completed as a documentation-only cleanup before Q.3.1 implementation.

Scope:
- Fixed D036 Markdown hierarchy so all eight decisions use `### Decision N` headings.
- Converted D036 internal labels such as rejected options, rationale, and Q.3.1 implementation implication from headings into bold labels.
- Confirmed current repo uses H062 for frontend auth cookie/session migration; H058 remains password reset flow and is still Open.
- Fixed the truncated README wording for "CSRF protection" if present.
- Fixed README Commercial Hardening Checks code fence rendering without changing command text.

Files changed:
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Guardrails:
- No code changes.
- No backend changes.
- No frontend changes.
- No migrations.
- No tests added.
- No new decisions.
- No new backlog items.
- No backlog renumbering beyond correcting the H058/H062 documentation drift.
- No changes to D036 decision content beyond Markdown structure.

Validation:
- D036 decision heading grep confirms eight h3 decision headings.
- No `## Rejected options` headings remain inside D036.
- README keeps H062 as the frontend auth cookie/session migration backlog reference.
- README no longer contains truncated `protec`.
- Changed files are limited to the three allowed documentation files.
- Backend/frontend tests not run because Q.3.0.1 is documentation-only and no code files changed.

Next recommended phase:
- Phase Q.3.1 — Implement frontend cookie/session migration and CSRF protection.

## Phase Q.3.0 Completion — Frontend Auth Cookie/Session + CSRF Design Decisions

Phase Q.3.0 has been completed as a decision-only phase.

Scope:
- Added D036 to lock frontend cookie/session migration and CSRF architecture before Q.3.1 implementation.
- Confirmed repo source-of-truth legacy localStorage keys are `forecourt_access_token` and `forecourt_employee_access_token`.
- Recorded that stale key `employee_access_token` must not be used as an active migration key.
- Updated hardening backlog items for CSRF protection and frontend auth cookie/session migration.
- Added follow-up hardening items for all-sessions logout, same-origin deployment/session routing validation, and bearer-token deprecation/removal.

Files changed:
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Decision-only guardrails:
- No code changes.
- No frontend changes.
- No backend auth changes.
- No migrations.
- No tests added.
- No endpoints added.

D036 decisions captured:
- CSRF strategy: SameSite=Strict refresh cookie plus required custom header `X-Requested-With: ForecourtOS`.
- Refresh cookie attributes: HTTP-only, Secure in production, SameSite=Strict, path `/api/v1/auth`, host-only Domain omitted, Max-Age tied to `REFRESH_TOKEN_EXPIRE_DAYS`.
- Access-token storage: in-memory only after Q.3.1; refresh cookie restores sessions after reload.
- Bearer-token deprecation: 30/60/90 day timeline after Q.3.1 ships.
- localStorage migration: force re-login and clear `forecourt_access_token` plus `forecourt_employee_access_token`.
- Refresh-on-401: one refresh attempt, shared across parallel 401s, retry original request once, route to the correct login page on refresh failure.
- Logout scope: Q.3.1 uses existing single-session `POST /api/v1/auth/logout`; all-sessions logout is future hardening.
- Deployment target: same-origin MVP production deployment with API path-proxied under the app origin where practical.

Documentation changes:
- Added D036 to `DECISIONS.md`.
- Updated H061 and H062 in `HARDENING_BACKLOG.md` with D036 references and Q.3.1 acceptance criteria.
- Added H067, H068, and H069 for deferred all-sessions logout, same-origin deployment validation, and bearer-token deprecation/removal.
- Updated README phase status and current focus to mark Q.3.0 done and Q.3.1 next.
- README Commercial Hardening Checks code fences were already rendering correctly; command text was left unchanged.

Validation performed:
- `git status --short`: clean before Q.3.0 edits.
- `git status --short`: changed files limited to the four allowed documentation files after edits.
- `git diff --stat`: documentation-only diff reviewed.
- `git diff --name-only`: changed files limited to `DECISIONS.md`, `HARDENING_BACKLOG.md`, `IMPLEMENTATION_STATUS.md`, and `README.md`.
- Prompt artifact grep checks for known prompt-artifact phrases and markdown prompt-fence markers: no matches in `DECISIONS.md` or `IMPLEMENTATION_STATUS.md`.
- D036, Q.3.0, H061, H062, and localStorage key grep checks performed.
- Backend/frontend tests not run because Q.3.0 is documentation-only and no code files changed.
- Last known full backend suite: 249 passed, 2 skipped.

Known limitations:
- Frontend still stores localStorage tokens until Q.3.1 implementation.
- Correct legacy localStorage keys are `forecourt_access_token` and `forecourt_employee_access_token`.
- Stale key `employee_access_token` must not be used as an active key.
- CSRF is not implemented until Q.3.1.
- All-sessions logout remains future hardening.
- Password reset/email verification remain Q.4.
- Owner 2FA remains Q.5.
- D010/D034 formatting drift, if any, was intentionally left unchanged for a future documentation-only cleanup phase.

Next recommended phase:
- Phase Q.3.1 — Implement frontend cookie/session migration and CSRF protection.

## Phase Q.2.2 Completion — Supply Chain / Slopsquat Hardening

Phase Q.2.2 has been implemented.

Scope:
- Added supply-chain hardening against slopsquat and hallucinated package risk before Q.3 frontend auth migration.
- Added a durable LLM-suggested dependency verification policy.
- Added baseline CI dependency checks for pull request dependency review, Python dependency auditing, and high-severity npm auditing.
- Added README supply-chain hardening commands and clarified that these are baseline controls, not complete slopsquat prevention.
- Verified small documentation drift checks for D034 prompt artifacts, unclosed markdown prompt blocks, and the implementation status title typo.

Files changed:
- `.github/workflows/ci.yml`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Supply-chain changes:
- Added H064 for slopsquat / hallucinated package hardening and marked it Partially Done.
- Added D035 for manual verification of new dependencies suggested by LLMs, generated code, tutorials, or blog posts.
- Added GitHub Dependency Review Action on pull requests with high-severity blocking.
- Added CI `pip-audit` for API requirements.
- Added CI `npm audit --audit-level=high` for frontend dependencies.
- Added README commands for local `pip-audit`, high-severity npm audit, and dependency/workflow diff review.

Checks:
- `git status`: showed Q.2.2 documentation/CI edits only.
- Prompt artifact grep check in `DECISIONS.md`: no matches.
- Implementation status title typo check: no matches.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q2_auth_sessions.py -q"`: 9 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q"`: 249 passed, 2 skipped.
- `cd apps/web && npm run build`: passed.
- `cd apps/web && npx tsc --noEmit`: passed.
- `gitleaks detect --source . --log-opts="--all"`: not run locally; `gitleaks` is not installed in this environment.
- `git ls-files | grep -iE '(^|/)\.env|\.pem$|\.key$|credentials|secret' || true`: found only `apps/web/.env.local.example`.
- Hardcoded secret string scan for common production keys: no matches.
- `pip-audit -r apps/api/requirements.txt`: not run locally; `pip-audit` is not installed in this environment. CI now installs and runs it.
- `cd apps/web && npm audit --audit-level=high`: passed with no high-severity findings; npm reported existing moderate PostCSS/Next advisories.
- `git diff -- apps/api/requirements.txt apps/web/package.json apps/web/package-lock.json .github/workflows`: showed only `.github/workflows/ci.yml` changes; no Python or npm dependency file changes.

Known limitations:
- These controls reduce known-vulnerability and dependency-review risk but do not fully prevent slopsquatting.
- Python dependencies are not yet hash-locked.
- Dependency approval automation remains future work.
- Existing moderate npm advisories remain outside the high-severity Q.2.2 gate.
- Frontend localStorage auth-token migration is still pending for Q.3.
- CSRF protection, auth/session audit logging, and refresh-token reuse detection remain follow-up hardening items.

Next recommended phase:
- Phase Q.3.0 — Frontend cookie/session and CSRF design.

## Phase Q.2.1 Completion — Auth Session Test + Documentation Hardening

Phase Q.2.1 has been implemented.

Scope:
- Backfilled focused Q.2 refresh/session edge-case tests before starting Q.3 frontend cookie migration.
- Verified D034 contains durable architecture content only; no prompt artifact was present.
- Fixed implementation/documentation date drift for the latest completed auth phases.
- Added follow-up hardening backlog items for CSRF protection, auth/session audit logging, and refresh-token reuse detection.
- Verified token TTL defaults and lowered default access-token lifetime from 60 minutes to 15 minutes.

Files changed:
- `apps/api/core/settings.py`
- `apps/api/tests/test_phase_q2_auth_sessions.py`
- `DECISIONS.md`
- `HARDENING_BACKLOG.md`
- `IMPLEMENTATION_STATUS.md`
- `README.md`

Tests added/verified:
- Refresh rotation returns a new refresh token and rejects the old one.
- Refresh token cannot be reused after logout.
- Admin refresh token is rejected for employee portal refresh.
- Employee refresh token is rejected for admin portal refresh.
- Expired refresh token is rejected without token leakage.
- Expired access token can recover through a valid refresh session.
- Refresh-cookie flow works when request body token is omitted.
- Logout clears the configured refresh cookie.
- Invalid refresh token errors do not echo token values.
- Existing Q.2 coverage already verifies disabled admin refresh blocking, disabled employee refresh blocking, inactive linked staff profile refresh blocking, employee token rejection on admin APIs, and admin token rejection on employee-only APIs.

TTL defaults:
- `ACCESS_TOKEN_EXPIRE_MINUTES`: 15.
- `REFRESH_TOKEN_EXPIRE_DAYS`: 14.

Documentation changes:
- Updated D034 with the Q.2.1 TTL clarification and confirmed no prompt artifact remained.
- Added H061, H065, and H066 to `HARDENING_BACKLOG.md`.
- Updated README phase status/current focus and access-token TTL default.

Checks:
- `python3 -m py_compile apps/api/core/settings.py apps/api/tests/test_phase_q2_auth_sessions.py`: passed.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q2_auth_sessions.py -q"`: 9 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_auth.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_q2_auth_sessions.py apps/api/tests/test_phase17_employee_portal.py apps/api/tests/test_main.py -q"`: 39 passed, 1 skipped.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q"`: 249 passed, 2 skipped.

Known limitations:
- Frontend still stores admin and employee access tokens in localStorage during the compatibility window.
- CSRF protection is not implemented yet and must block Q.3 cookie migration completion.
- Auth/session lifecycle audit logging remains a follow-up hardening item.
- Refresh-token reuse detection/session-family handling remains a follow-up hardening item.
- No password reset, email verification, or 2FA yet.

Next recommended phase:
- Phase Q.3 — Frontend auth cookie migration and account recovery scoping.

## Phase Q.2 Completion — Authentication/Session Hardening Foundation

Phase Q.2 has been implemented.

Scope:
- Added a backend refresh/session foundation without breaking existing bearer-token login flows.
- Added portal-aware refresh sessions for admin and employee identities.
- Added refresh-token hashing, rotation, revocation, and logout invalidation.
- Added additive HTTP-only refresh cookie support for the future frontend migration.
- Tightened employee-token dependencies so inactive linked staff profiles block already-issued employee sessions.
- Documented remaining frontend localStorage risk and next migration phase.

Files changed:
- `apps/api/models/auth_session.py`
- `apps/api/alembic/versions/0022_phase_q2_auth_sessions.py`
- `apps/api/models/__init__.py`
- `apps/api/core/security.py`
- `apps/api/core/settings.py`
- `apps/api/core/deps.py`
- `apps/api/routers/auth.py`
- `apps/api/schemas/auth.py`
- `apps/api/tests/test_phase_q2_auth_sessions.py`
- `apps/api/docs/phase17_employee_api_contract.md`
- `HARDENING_BACKLOG.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added `auth_sessions` table for hashed refresh/session tokens.
- Admin login and employee login now return existing access tokens plus refresh tokens.
- Added `POST /api/v1/auth/refresh` for portal-aware refresh-token rotation.
- Added `POST /api/v1/auth/logout` for refresh/session revocation.
- Added HTTP-only refresh cookie setting/clearing as additive migration support.
- Preserved existing `/api/v1/auth/login`, `/api/v1/auth/employee/login`, `/api/v1/auth/me`, and `/api/v1/auth/employee/me` compatibility.
- Preserved employee/admin token separation and tenant/site isolation.

Frontend changes:
- None. Current frontend access-token localStorage usage remains temporary and is documented for the next migration.

Documentation changes:
- Added D034 for the Q.2 backend refresh-session model.
- Updated D010 to mark frontend localStorage auth as still temporary after backend session foundation work.
- Updated H056/H057/H062 hardening backlog items.
- Updated README phase status and session environment variables.
- Updated employee API contract with the auth refresh/logout reality.

Checks:
- `python3 -m py_compile ...`: passed for changed Python modules.
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_q2_auth_sessions.py -q"`: 4 passed.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_auth.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_q2_auth_sessions.py apps/api/tests/test_phase17_employee_portal.py apps/api/tests/test_main.py -q"`: 34 passed, 1 skipped.
- `docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest apps/api/tests -q"`: 244 passed, 2 skipped.

Known limitations:
- Frontend still stores admin and employee access tokens in localStorage during the compatibility window.
- No password reset yet.
- No email verification yet.
- No 2FA yet.
- No frontend Sentry setup yet.
- No Redis-backed distributed rate limiter yet.

Next recommended phase:
- Phase Q.3 — Frontend auth cookie migration and account recovery scoping.

## Phase Q.0 Completion — Commercial SaaS Hardening Baseline

Phase Q.0 has been implemented.

Scope:
- Cleaned stale Phase 17 API contract P.4/P.5 summary.
- Investigated and resolved the recurring passlib `crypt` deprecation warning.
- Added baseline backend observability/error tracking support when configured.
- Verified the auth/public endpoint rate-limit foundation.
- Added commercial hardening commands/documentation.
- Expanded `HARDENING_BACKLOG.md` with Q.0 hardening items.

Backend changes:
- Replaced active passlib password hashing with direct `bcrypt` hashing and verification.
- Preserved bcrypt hash format, 72-byte password limit handling, admin login, and employee login behavior.
- Added optional backend Sentry initialization via `SENTRY_DSN`.
- Added Sentry request header, cookie, and sensitive body-field redaction.
- Added Q.0 hardening tests for password hashing and Sentry sanitization.

Frontend changes:
- None.

Documentation changes:
- Added `HARDENING_BACKLOG.md`.
- Updated `README.md` with commercial hardening environment variables and checks.
- Updated `apps/api/docs/phase17_employee_api_contract.md` planned-after-P.5 summary.
- Updated Phase Q.0 status in `README.md`.

Checks:
- API build: passed.
- Alembic upgrade: passed.
- Q.0/auth regression tests: 27 passed, 1 skipped.
- Request workflow regression bundle: 79 passed.
- Rate-limit-enabled auth spot check: 1 passed.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.
- `gitleaks`: not run; CLI is not installed in this environment.
- passlib warning: resolved; no passlib `crypt` deprecation warning appeared in Q.0, auth, or request workflow test runs.

Known limitations:
- No refresh-token/cookie migration yet.
- No 2FA yet.
- No full CI/CD production pipeline yet.
- No frontend Sentry setup yet.
- No Redis-backed distributed rate limiter yet.
- No Stripe/billing hardening yet.
- No AI/RAG hardening yet.
- No production backup/restore validation yet.

Next recommended phase:
- Phase Q.1 — CI/CD and observability hardening.

## Pre-Q.0 Documentation Cleanup — Commercial SaaS Standard

Pre-Q.0 documentation cleanup has been completed.

Documentation changes:
- Framed Anci Ops Suite as a commercial multi-tenant SaaS product, not a portfolio/prototype.
- Added the Phase Q.0 next-phase marker for commercial SaaS hardening baseline.
- Added D033 to lock in production-oriented documentation and implementation standards.
- Clarified that backend source-of-truth, tenant/site isolation, RBAC, auditability, deterministic errors, and employee/admin token separation are production requirements.
- Clarified that browser-only/localStorage behavior is not production persistence for commercial workflows.
- Added commercial API contract guardrails for current and future employee/admin API work.

Checks:
- Documentation-only change; backend/frontend tests were not run.

Next recommended phase:
- Phase Q.0 — Commercial SaaS hardening baseline.

## Phase P.5 Completion — Swap Approval Rota Application

Phase P.5 has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/tests/test_phase_p5_swap_approval_rota_application.py`
- `apps/api/tests/test_phase_p4_swap_target_shift_modelling.py`
- `apps/api/tests/test_phase_p3_cover_approval_rota_application.py`
- `apps/api/tests/test_phase_o_approved_request_rota_application.py`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Extended admin approval so target-accepted swap requests apply safe rota reassignment.
- Approved target-accepted swap requests exchange assignments between requester shift and target shift.
- Preserved shift times, published state, and scheduled status for both shifts.
- Blocked swap rota mutation unless the target employee accepted first.
- Blocked swap mutation when requester/target shift validation fails.
- Kept leave approval behaviour from Phase O unchanged.
- Kept cover approval behaviour from Phase P.3 unchanged.
- Preserved tenant/site isolation and admin RBAC.
- Added audit logging for swap approval and both shift reassignments.
- Added Phase P.5 tests.

Frontend changes:
- Updated admin request queue copy and target-acceptance error handling for swap rota application.

Documentation changes:
- Added D032 for target-accepted swap approval rota reassignment.
- Updated Phase 17 employee API contract with Phase P.5 swap approval behaviour.
- Updated README phase table with Phase P.5 complete.
- Added this Phase P.5 implementation status entry.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p5_swap_approval_rota_application.py -q"`: 21 passed, 1 existing passlib `crypt` deprecation warning.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p4_swap_target_shift_modelling.py apps/api/tests/test_phase_p3_cover_approval_rota_application.py apps/api/tests/test_phase_p2_target_accept_decline.py apps/api/tests/test_phase_p1_employee_request_targets.py apps/api/tests/test_phase_o_approved_request_rota_application.py apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py -q"`: 58 passed, 1 existing passlib `crypt` deprecation warning.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- No request retargeting after decline yet.
- No request history hide/restore yet.
- No notifications.
- No payroll/earnings recalculation.
- No AI Help request actions.

## Phase P.4 Completion — Swap Target-Shift Modelling Foundation

Phase P.4 has been implemented.

Files changed:
- `apps/api/models/shift_request.py`
- `apps/api/alembic/versions/0021_phase_p4_swap_target_shift.py`
- `apps/api/routers/employee.py`
- `apps/api/routers/sites.py`
- `apps/api/schemas/employee.py`
- `apps/api/schemas/site_request.py`
- `apps/api/tests/test_phase_p4_swap_target_shift_modelling.py`
- `apps/api/tests/test_phase_m_employee_requests.py`
- `apps/api/tests/test_phase_o_approved_request_rota_application.py`
- `apps/api/tests/test_phase_p2_target_accept_decline.py`
- `apps/api/tests/test_phase_p3_cover_approval_rota_application.py`
- `apps/web/app/employee/requests/page.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added target-shift modelling for swap requests.
- Added employee-token target shift discovery endpoint.
- Extended swap request creation to require and store target shift.
- Validated requester shift, target employee, and target shift are same-site/same-tenant and published scheduled shifts.
- Added safe target shift summaries to inbound/admin request views where applicable.
- Preserved tenant/site isolation and employee/admin token separation.
- Kept swap approval decision-only with no rota mutation.
- Added Phase P.4 tests.

Frontend changes:
- Added target shift selection to swap request UI.
- Updated inbound swap request UI to show both shift summaries.

Documentation changes:
- Added D031 for target-shift modelling.
- Updated Phase 17 employee API contract with target shift endpoint and swap request body.
- Updated README phase table with Phase P.4 done and Phase P.5 next.
- Added this Phase P.4 implementation status entry.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p4_swap_target_shift_modelling.py -q"`: 16 passed, 1 existing passlib `crypt` deprecation warning.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p3_cover_approval_rota_application.py apps/api/tests/test_phase_p2_target_accept_decline.py apps/api/tests/test_phase_p1_employee_request_targets.py apps/api/tests/test_phase_o_approved_request_rota_application.py apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py -q"`: 42 passed, 1 existing passlib `crypt` deprecation warning.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- Swap approval does not update rota yet.
- No swap rota mutation until Phase P.5.
- No request retargeting after decline yet.
- No notifications.
- No payroll/earnings recalculation.
- No AI Help request actions.

Next recommended phase:
- Phase P.5 — Swap approval rota application.

## Phase P.3 Completion — Cover Approval Rota Application

Phase P.3 has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/tests/test_phase_p3_cover_approval_rota_application.py`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Extended admin approval so target-accepted cover requests apply safe rota reassignment.
- Approved target-accepted cover requests reassign the affected published scheduled shift from requester to target employee.
- Preserved shift time, published state, and scheduled status.
- Blocked cover rota mutation unless the target employee accepted first.
- Kept swap approval decision-only.
- Kept leave approval behavior from Phase O unchanged.
- Preserved tenant/site isolation and admin RBAC.
- Added audit logging for cover approval and shift reassignment.
- Added Phase P.3 tests.

Frontend changes:
- Updated admin request queue UI to show cover rota application result.
- Updated request queue copy to clarify that target-accepted cover can reassign after manager approval while swap remains decision-only.

Documentation changes:
- Added D030 to `DECISIONS.md` for target-accepted cover approval rota reassignment.
- Updated the Phase 17 employee API contract with Phase P.3 cover approval behavior.
- Updated `README.md` phase status with Phase P.3 done and Phase P.4 next.
- Added this Phase P.3 implementation status entry.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p3_cover_approval_rota_application.py -q"`: 14 passed, 1 existing passlib `crypt` deprecation warning.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p2_target_accept_decline.py apps/api/tests/test_phase_p1_employee_request_targets.py apps/api/tests/test_phase_o_approved_request_rota_application.py apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py -q"`: 28 passed, 1 existing passlib `crypt` deprecation warning.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- Swap approval does not update rota yet.
- Untargeted cover approval does not auto-assign a replacement.
- No request retargeting after decline yet.
- No notifications.
- No payroll/earnings recalculation.
- No AI Help request actions.

Next recommended phase:
- Phase P.4 — Swap target-shift modelling foundation.

## Phase P.2 Completion — Target Co-worker Accept/Decline Workflow

Phase P.2 has been implemented.

Files changed:
- `apps/api/routers/employee.py`
- `apps/api/routers/sites.py`
- `apps/api/schemas/employee.py`
- `apps/api/tests/test_phase_p2_target_accept_decline.py`
- `apps/web/app/employee/requests/page.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added employee-token inbound targeted request list endpoint under `/api/v1/employee/me/inbound-requests`.
- Added target accept endpoint.
- Added target decline endpoint.
- Restricted inbound visibility to targeted employee only.
- Preserved tenant/site isolation.
- Preserved employee/admin token separation.
- Target accept/decline changes request workflow status only.
- Target accept/decline does not mutate rota.
- Allowed targeted cover requests to store `target_employee_account_id`.
- Kept admin swap/cover approval decision-only, including after target acceptance.
- Added Phase P.2 tests.

Frontend changes:
- Added inbound request section to `/employee/requests`.
- Added accept/decline actions with safe explanatory copy.

Documentation changes:
- Updated the Phase 17 employee API contract with Phase P.2 endpoints.
- Updated `README.md` phase status with Phase P.2 done and Phase P.3 next.
- Added this Phase P.2 implementation status entry.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p2_target_accept_decline.py -q"`: 8 passed, 1 existing passlib `crypt` deprecation warning.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p1_employee_request_targets.py apps/api/tests/test_phase_o_approved_request_rota_application.py apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py -q"`: 20 passed, 1 existing passlib `crypt` deprecation warning.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- No swap/cover rota mutation yet.
- No notifications.
- No request retargeting after decline yet.
- No payroll/earnings recalculation.
- No AI Help request actions.

Next recommended phase:
- Phase P.3 — Cover approval rota application.

## Phase P.1 Completion — Employee-Safe Same-Site Target List

Phase P.1 has been implemented.

Files changed:
- `apps/api/routers/employee.py`
- `apps/api/schemas/employee.py`
- `apps/api/tests/test_phase_p1_employee_request_targets.py`
- `apps/web/app/employee/requests/page.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added employee-token same-site request target list endpoint under `/api/v1/employee/me/request-targets`.
- Returned only safe target fields: employee account ID, display name, role labels, and active state.
- Excluded requester, inactive accounts, inactive staff profiles, cross-site employees, and cross-tenant employees.
- Added optional shift-context validation for swap/cover target selection.
- Preserved employee/admin token separation.
- Preserved tenant/site isolation and Path A store fallback.
- Added Phase P.1 backend tests.

Frontend changes:
- Added target-list API client support.
- Added minimal swap target selection to `/employee/requests` using safe same-site display names only.
- Swap submission still uses the existing employee request create endpoint.

Documentation changes:
- Updated the Phase 17 employee API contract with the Phase P.1 target list endpoint.
- Updated `README.md` phase status with Phase P.1 done and Phase P.2 next.
- Added this Phase P.1 implementation status entry.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_p1_employee_request_targets.py -q"`: 3 passed, 1 existing passlib `crypt` deprecation warning.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_o_approved_request_rota_application.py apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py apps/api/tests/test_phase_l_employee_availability.py apps/api/tests/test_phase_k2_employee_login_site_lookup.py -q"`: 31 passed, 1 existing passlib `crypt` deprecation warning.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- No target accept/decline workflow yet.
- No swap/cover rota mutation yet.
- No notifications.
- No availability-based target filtering.
- No payroll/earnings recalculation.
- No AI Help request actions.

Next recommended phase:
- Phase P.2 — Target accept/decline workflow.

## Phase P.0 Completion — Swap/Cover Workflow Scoping + Decisions

Phase P.0 has been completed.

Files changed:
- `DECISIONS.md`
- `README.md`
- `apps/api/docs/phase17_employee_api_contract.md`
- `IMPLEMENTATION_STATUS.md`

Documentation changes:
- Added D027 to `DECISIONS.md` for the cover request state machine.
- Added D028 to `DECISIONS.md` for the swap request state machine and current target-shift modelling limitation.
- Added D029 to `DECISIONS.md` for breaking Phase P into smaller safe phases.
- Updated the Phase 17 employee API contract with a Phase P.0 scoping section.
- Updated `README.md` phase status with Phase P.0 done and Phase P.1 next.

Implementation changes:
- No backend rota mutation was added.
- No target accept/decline endpoints were added.
- No database migration was added.
- No frontend UI was added.
- Existing employee/admin request endpoints were not changed.

Checks:
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_o_approved_request_rota_application.py apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py -q"`: 17 passed, 1 existing passlib `crypt` deprecation warning.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- No employee-safe same-site target list yet.
- No target co-worker accept/decline workflow yet.
- Approved cover requests do not update rota yet.
- Approved swap requests do not update rota yet.
- No target shift modelling for true shift-for-shift swaps yet.
- No notifications.
- No payroll/earnings recalculation engine.
- No AI Help request actions.

Next recommended phase:
- Phase P.1 — Employee-safe same-site target list.

## Phase O Completion — Approved Leave Request Rota Application

Phase O has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/schemas/site_request.py`
- `apps/api/tests/test_phase_o_approved_request_rota_application.py`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Extended admin request approval so approved leave requests apply safe rota changes.
- Approved leave requests open/unassign affected published scheduled shifts for the requester within the approved leave date range.
- Swap and cover approvals remain decision-only and do not mutate rota.
- Rejection remains decision-only and does not mutate rota.
- Preserved tenant/site isolation and admin RBAC.
- Blocked employee-token access through existing admin-side token parsing.
- Added `affected_shift_count` to request decision responses.
- Added audit logging for request approval and affected shift updates.
- Added Phase O backend tests.

Frontend changes:
- Updated admin request queue UI to show whether approval updated rota and how many shifts were opened.
- Updated admin request queue copy to clarify that only leave approvals apply rota changes in Phase O.

Documentation changes:
- Added D026 to `DECISIONS.md` for approved leave request rota application.
- Updated the Phase 17 employee API contract with Phase O approval behaviour.
- Updated `README.md` phase status with Phase O done and Phase P next.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_o_approved_request_rota_application.py -q"`: 4 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_n_admin_request_queue.py apps/api/tests/test_phase_m_employee_requests.py apps/api/tests/test_phase_l_employee_availability.py apps/api/tests/test_phase_k2_employee_login_site_lookup.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_k_employee_portal.py apps/api/tests/test_phase_j_rota_publish.py -q"`: 48 passed.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- Approved swap requests do not update rota yet.
- Approved cover requests do not update rota yet.
- No target co-worker accept/decline workflow yet.
- No automatic replacement assignment.
- No payroll/earnings recalculation engine yet.
- No notifications.

Next recommended phase:
- Phase P — Swap/cover request application.

## Phase N Completion — Admin Request Approval Queue

Phase N has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/schemas/site_request.py`
- `apps/api/tests/test_phase_n_admin_request_queue.py`
- `apps/web/app/admin/requests/page.tsx`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added admin-side site-scoped request queue endpoints under `/api/v1/sites/{site_id}/requests`.
- Added request detail endpoint with safe request data and safe shift summary for shift-linked requests.
- Added approve/reject endpoints for pending employee leave, swap, and cover requests.
- Enforced site-scoped access for Owner/Admin and assigned-site Manager users.
- Blocked employee-token access through admin-side auth parsing.
- Preserved tenant/site isolation with safe `REQUEST_NOT_FOUND` for inaccessible request rows.
- Recorded approver, decision reason, `decided_at`, and `updated_at` on approval/rejection.
- Preserved rota immutability: approval/rejection does not update shifts or rota.
- Added audit logging for `request_approved` and `request_rejected`.
- Added Phase N backend tests.

Frontend changes:
- Added `/admin/requests` in the existing admin shell.
- Added an Operations nav link for Requests.
- Added minimal request queue UI for the first active site with pending request list, optional decision reason, approve/reject actions, empty state, and safe loading/error states.
- UI explicitly states that approval records the decision only and rota changes are not automatically applied in this phase.

Documentation changes:
- Added D025 to `DECISIONS.md` for approval/rejection without rota mutation.
- Updated the Phase 17 employee API contract with Phase N admin request queue endpoints.
- Updated `README.md` phase status with Phase N done and Phase O next.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_n_admin_request_queue.py -q"`: 6 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_m_employee_requests.py apps/api/tests/test_phase_l_employee_availability.py apps/api/tests/test_phase_k2_employee_login_site_lookup.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_k_employee_portal.py apps/api/tests/test_phase_j_rota_publish.py -q"`: 42 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed after fixing a nullable store capture in the new Requests panel; an earlier run failed during the Next type/lint worker with that TypeScript diagnostic.

Known limitations:
- Approved requests do not automatically update rota yet.
- No co-worker accept/decline workflow yet.
- No request notifications yet.
- No employee request history hide/restore yet.
- No AI Help request actions yet.
- Admin request UI uses the current first active site pattern; no full multi-site switching yet.

Next recommended phase:
- Phase O — Approved request rota application.

## Phase M Completion — Employee Request Workflows Foundation

Phase M has been implemented.

Files changed:
- `apps/api/alembic/versions/0020_employee_request_workflows.py`
- `apps/api/models/shift_request.py`
- `apps/api/routers/employee.py`
- `apps/api/schemas/employee.py`
- `apps/api/schemas/shift_request.py`
- `apps/api/tests/test_phase_m_employee_requests.py`
- `apps/web/app/employee/page.tsx`
- `apps/web/app/employee/requests/page.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Extended `shift_requests` with employee request workflow fields for site, requester employee account, target employee account, reason, date range, and cancellation metadata.
- Added employee-token self-only request list/create/cancel endpoints under `/api/v1/employee/me/requests`.
- Added support for leave, swap, and cover request creation as `pending` requests.
- Enforced tenant/site/employee self-only access using the employee account and linked active staff profile.
- Prevented employees from requesting changes for draft, cancelled, unpublished, unowned, cross-site, or cross-tenant shifts.
- Enforced same-site active target employee validation for swap requests.
- Preserved rota immutability: Phase M requests do not directly update shifts or rota.
- Added deterministic `REQUEST_DUPLICATE`, `REQUEST_NOT_FOUND`, and `REQUEST_NOT_PENDING` errors.
- Added Phase M backend tests.

Frontend changes:
- Added `/employee/requests` with own request list, empty state, leave request form, cover request form for own published shifts, and pending request cancellation.
- Linked Requests from the existing employee rota page.
- Swap request UI was not added because there is not yet an employee-safe same-site target employee list.
- Frontend uses the existing employee token helper only and does not store requests/profile data in localStorage.

Documentation changes:
- Added D024 to `DECISIONS.md` for reusing `shift_requests` without direct rota mutation.
- Updated the Phase 17 employee API contract with Phase M request endpoints and intentional omissions.
- Updated `README.md` phase status with Phase M done and Phase N next.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_m_employee_requests.py -q"`: 7 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_l_employee_availability.py apps/api/tests/test_phase_k2_employee_login_site_lookup.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_k_employee_portal.py apps/api/tests/test_phase_j_rota_publish.py -q"`: 35 passed.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- No admin approval queue yet.
- No request approval/rejection engine yet.
- No co-worker accept/decline workflow yet.
- No automatic rota update from approved requests yet.
- No request history hide/restore.
- No notifications.
- No AI Help request actions.
- No swap request UI yet.

Next recommended phase:
- Phase N — Admin request approval queue.

## Phase L Completion — Employee Availability Foundation

Phase L has been implemented.

Files changed:
- `apps/api/alembic/versions/0019_employee_availability_foundation.py`
- `apps/api/models/availability_entry.py`
- `apps/api/routers/availability.py`
- `apps/api/routers/employee.py`
- `apps/api/schemas/availability.py`
- `apps/api/schemas/employee.py`
- `apps/api/tests/test_phase_l_employee_availability.py`
- `apps/web/app/employee/page.tsx`
- `apps/web/app/employee/availability/page.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Extended availability persistence with employee-account and site-scoped fields while preserving the existing availability table.
- Added employee-token self-only availability list/create/delete behaviour under `/api/v1/employee/me/availability`.
- Enforced tenant/site/employee self-only access using the employee account and linked active staff profile.
- Added Monday week-start, date-in-week, time-range, notes length, and past-date validation.
- Blocked availability create/delete for weeks where the employee has a published scheduled shift in the selected site.
- Added duplicate protection with deterministic `409 AVAILABILITY_DUPLICATE`.
- Added deterministic `409 AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA` and `404 AVAILABILITY_NOT_FOUND` behaviours.
- Added Phase L backend tests.

Frontend changes:
- Added `/employee/availability` with week selection, availability list, create form, delete action, empty state, and locked/duplicate error messages.
- Linked the availability page from the existing employee rota page.
- Frontend uses the existing employee token helper only and does not store availability/profile data in localStorage.

Documentation changes:
- Added D023 to `DECISIONS.md` for extending the existing availability table with employee-account scope.
- Updated the Phase 17 employee API contract with implemented Phase L availability auth, locking, and validation notes.
- Updated `README.md` phase status with Phase L done.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_l_employee_availability.py -q"`: 7 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_k2_employee_login_site_lookup.py apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_k_employee_portal.py apps/api/tests/test_phase_j_rota_publish.py -q"`: 28 passed.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed.

Known limitations:
- No Owner override UI/API yet.
- No Admin/Manager availability management.
- No leave/swap/cover request workflow changes.
- No AI Help availability actions.
- No remembered-sites switching.

Next recommended phase:
- Phase M — Owner override / advanced employee workflows.

## Phase K.2 Completion — Employee Login Polish / Site Code Lookup

Phase K.2 has been implemented.

Files changed:
- `apps/api/main.py`
- `apps/api/routers/public.py`
- `apps/api/schemas/store.py`
- `apps/api/tests/test_phase_k2_employee_login_site_lookup.py`
- `apps/web/app/employee/login/page.tsx`
- `apps/web/lib/api-client.ts`
- `apps/api/docs/phase17_employee_api_contract.md`
- `DECISIONS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added public `GET /api/v1/public/sites/lookup?code=SITE_CODE`.
- Lookup returns only active sites and only minimal public fields: `site_id`, `site_code`, and `site_name`.
- Lookup does not expose tenant IDs, staff data, billing data, readiness, opening hours, or operational details.
- Unknown and inactive site codes return a safe generic not-found response.
- Duplicate active site codes across tenants return a safe ambiguity response because current store codes are tenant-scoped, not globally unique.
- Existing `POST /api/v1/auth/employee/login` with `site_id`, username, and password remains supported.
- Added Phase K.2 backend tests for lookup safety and existing auth compatibility.

Frontend changes:
- Employee login now asks for `Site code`, username, and password instead of a raw site UUID.
- Login flow resolves `site_code` to `site_id`, then calls the existing employee login endpoint.
- Safe lookup and credential error messages were added.
- Existing separate employee token behaviour is preserved.
- No employee profile data is stored in localStorage.

Documentation changes:
- Added D022 to `DECISIONS.md` for site-code lookup before site-scoped login.
- Updated `README.md` phase table with Phase K.2 done and Phase L next.
- Added current MVP API contract/security note for public site lookup.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed after backend route/test changes so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_k2_employee_login_site_lookup.py -q"`: 7 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_k1_employee_identity_hardening.py apps/api/tests/test_phase_k_employee_portal.py apps/api/tests/test_phase_j_rota_publish.py apps/api/tests/test_phase_i4_shift_update_cancel.py apps/api/tests/test_phase_i3_shift_create.py apps/api/tests/test_phase_i1_rota_week_read.py apps/api/tests/test_phase_f_store_settings.py -q"`: 46 passed.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed after `npm run build` regenerated `.next/types`; an earlier parallel run hit the known `.next/types` race.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed site-code lookup, existing employee login, employee `/auth/me`, admin `/auth/me`, safe unknown-site response, and generic wrong-password response.
- Route smoke confirmed `/employee/login`, `/employee`, `/admin`, `/admin/rota`, `/admin/staff`, and `/admin/sites/new` return HTTP 200 from a fresh Next dev server on port 3009.

Known limitations:
- No remembered-sites switching yet.
- No employee availability yet.
- No leave, swap, or cover request UI yet.
- No employee earnings UI yet.
- No employee AI help yet.
- Site-code lookup can be ambiguous if different tenants use the same active site code; the endpoint returns a safe contact-manager error in that case.

Next recommended phase:
- Phase L — Employee availability system.

## Phase K.1 Completion — Employee Auth + Identity Hardening

Phase K.1 has been implemented.

Files changed:
- `apps/api/routers/auth.py`
- `apps/api/tests/test_phase_k1_employee_identity_hardening.py`
- `DECISIONS.md`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- `GET /api/v1/auth/me` now supports employee-token session responses without breaking the existing admin response shape.
- `GET /api/v1/auth/employee/me` was retained.
- Employee/admin token separation is hardened: employee tokens still cannot satisfy admin-only dependencies, and admin tokens cannot satisfy employee-only rota access.
- Staff-to-employee-account consistency is covered by tests, including exactly one linked account per created staff profile.
- Duplicate employee usernames in the same tenant/site are rejected safely without returning raw database errors or password hashes.
- The same employee username remains allowed across different sites, matching the site-scoped employee account model.
- Inactive employee accounts cannot log in or call employee rota APIs.
- Inactive linked staff profiles cannot be used for employee login.
- Draft rota remains hidden from employee rota responses, while published assigned shifts remain visible.

Frontend changes:
- None.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: passed after backend test changes so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_k1_employee_identity_hardening.py -q"`: 7 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_k_employee_portal.py apps/api/tests/test_phase_j_rota_publish.py apps/api/tests/test_phase_i4_shift_update_cancel.py apps/api/tests/test_phase_i3_shift_create.py apps/api/tests/test_phase_i1_rota_week_read.py apps/api/tests/test_phase_f_store_settings.py -q"`: 39 passed.
- Staff regression `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_c_staff_setup_flow.py apps/api/tests/test_phase_d1_staff_directory.py -q"`: 18 passed.
- `npm run build`: passed.
- `npx tsc --noEmit`: passed after `npm run build` regenerated `.next/types`.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed admin `/auth/me`, employee `/auth/me`, employee `/auth/employee/me`, duplicate username rejection, employee draft hiding, admin rota API rejection for employee tokens, and published-shift visibility.
- Route smoke confirmed `/admin`, `/admin/rota`, `/admin/staff`, `/admin/sites/new`, `/employee/login`, and `/employee` return HTTP 200 from a fresh Next dev server on port 3008.

Known limitations:
- Employee login still uses site ID because there is no public site-code lookup/selector endpoint yet.
- Employee token storage temporarily follows the current frontend localStorage token pattern, using a separate employee token key and no stored employee profile data.
- No employee availability yet.
- No leave, swap, or cover request UI yet.
- No employee earnings UI yet.
- No remembered-sites switching yet.
- No employee AI help yet.
- Existing older `/api/v1/employee/me/*` endpoints still use admin-user staff identity; the new Phase K employee portal path remains `/auth/employee/*` and `/employee/rota/my`.

Next recommended phase:
- Phase K.2 — employee site-code lookup/login polish, or Phase L — employee availability foundation.

## Phase K Completion — Employee Portal Auth + Published Rota View

Phase K has been implemented.

Files changed:
- `apps/api/alembic/versions/0018_employee_accounts.py`
- `apps/api/core/deps.py`
- `apps/api/models/employee_account.py`
- `apps/api/models/staff_profile.py`
- `apps/api/models/__init__.py`
- `apps/api/routers/auth.py`
- `apps/api/routers/employee.py`
- `apps/api/routers/staff.py`
- `apps/api/schemas/auth.py`
- `apps/api/schemas/employee.py`
- `apps/api/schemas/staff.py`
- `apps/api/tests/test_phase_k_employee_portal.py`
- `apps/web/app/employee/login/page.tsx`
- `apps/web/app/employee/page.tsx`
- `apps/web/components/admin/site-setup-form.tsx`
- `apps/web/lib/api-client.ts`
- `apps/web/lib/employee-auth-token.ts`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added `employee_accounts` with site-scoped username/password login, hashed passwords, active state, last login timestamp, and unique tenant/site/username constraint.
- Added nullable `staff_profiles.employee_account_id` linking staff profiles to employee accounts.
- Added `POST /api/v1/auth/employee/login`.
- Added `GET /api/v1/auth/employee/me`.
- Added employee-token dependency using `employee:{employee_account_id}` JWT subjects so employee tokens cannot satisfy admin user auth dependencies.
- Added `GET /api/v1/employee/rota/my?week_start=YYYY-MM-DD`.
- Staff creation can now create/link an employee account when `employee_username` and `employee_password` are supplied.
- Employee rota returns only the linked employee's own assigned, published, scheduled shifts.
- Draft shifts, cancelled shifts, and co-worker shifts are excluded from the new employee rota endpoint.
- Employee tokens are rejected by admin weekly rota APIs.
- Passwords are hashed and password hashes are not returned.

Frontend changes:
- Added `/employee/login`.
- Added `/employee`.
- Employee login uses site ID, username, and password only.
- No employee email login or Google login was added.
- Added separate employee token helper using `forecourt_employee_access_token`; no employee profile details are stored in localStorage.
- Employee portal shows employee name, site ID, week selector, and own published rota list.
- Added safe loading, empty, sign-in, and error states.
- Admin site setup now sends employee username/password to staff creation so employee accounts are created with staff setup.
- No employee create/edit/cancel/admin rota actions are exposed.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: completed after backend model/migration/test changes so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_k_employee_portal.py -q"`: 6 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_j_rota_publish.py apps/api/tests/test_phase_i4_shift_update_cancel.py apps/api/tests/test_phase_i3_shift_create.py apps/api/tests/test_phase_i1_rota_week_read.py apps/api/tests/test_phase_f_store_settings.py -q"`: 33 passed.
- Additional staff regression `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_c_staff_setup_flow.py apps/api/tests/test_phase_d1_staff_directory.py -q"`: 18 passed.
- `npx tsc --noEmit`: passed after `npm run build` regenerated `.next/types`.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed employee login, draft rota hidden, admin rota API rejected for employee token, published assigned shift visible, and unpublished shift hidden again.
- Route smoke confirmed `/employee/login`, `/employee`, `/admin/rota`, `/admin/staff`, `/admin/sites/new`, and `/admin` return HTTP 200 from a fresh Next dev server on port 3007.

Known limitations:
- Employee login currently asks for site ID because there is no public site-code lookup/selector endpoint yet.
- Employee token storage temporarily follows the current frontend localStorage token pattern, using a separate employee token key and no stored employee profile data.
- No employee availability yet.
- No leave, swap, or cover request UI yet.
- No employee earnings UI yet.
- No remembered-sites switching yet.
- No employee AI help yet.
- Existing older `/api/v1/employee/me/*` endpoints still use admin-user staff identity; the new Phase K portal uses `/auth/employee/*` and `/employee/rota/my`.

Next recommended phase:
- Phase K.1 — employee site-code lookup/login polish, or Phase L — employee availability foundation.

## Phase J Completion — Publish / Unpublish Rota

Phase J has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/schemas/rota.py`
- `apps/api/tests/test_phase_j_rota_publish.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added `POST /api/v1/sites/{site_id}/rota/publish`.
- Added `POST /api/v1/sites/{site_id}/rota/unpublish`.
- Publish requires the current admin tenant role, tenant/site scope, an operationally ready site, and at least one active scheduled shift in the selected week.
- Publish sets `published_at` and `published_by_user_id` on active unpublished scheduled shifts for the selected Monday-start week.
- Unpublish clears `published_at` and `published_by_user_id` for active published scheduled shifts in the selected week.
- Cancelled shifts remain excluded from active weekly rota reads and are not published.
- Weekly rota reads now include `is_published`, `published_shift_count`, and `draft_shift_count`.
- Added audit logging for `rota_published` and `rota_unpublished`.
- No new tables, migrations, employee portal visibility, generation, AI, drag/drop, or payroll recalculation logic was added.

Frontend changes:
- Added publish/unpublish API client functions.
- `/admin/rota` now shows draft/published/no-shifts/not-ready/publishing/unpublishing status from backend weekly rota state.
- Publish button is enabled only when the selected site is operationally ready, the selected week has active shifts, and the rota is not already published.
- Published weeks show an Unpublish action instead of Publish.
- Publish and unpublish confirmation prompts were added.
- Weekly rota refetches after publish/unpublish and keeps the selected week.
- Safe success/error messages were added.
- Future Generate week, AI recommendations, and Export actions remain disabled.
- No employee portal visibility, localStorage rota persistence, or sensitive staff data exposure was added.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: completed after backend route/test changes so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_j_rota_publish.py -q"`: 8 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i4_shift_update_cancel.py apps/api/tests/test_phase_i3_shift_create.py apps/api/tests/test_phase_i1_rota_week_read.py apps/api/tests/test_phase_f_store_settings.py -q"`: 25 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed a readiness-complete site can publish one active draft shift, a cancelled shift is not published, and unpublish clears the published state.
- Route smoke confirmed `/admin/rota`, `/admin`, `/admin/staff`, and `/admin/sites/new` return HTTP 200 from a fresh Next dev server on port 3006.

Known limitations:
- No employee portal rota view yet.
- No rota generation yet.
- No drag and drop yet.
- No AI recommendations yet.
- No payroll/labour recalculation yet.
- No full multi-site switching yet; the page uses the first active backend store.

Next recommended phase:
- Phase K — Employee published rota visibility, or Phase J.1 — browser automation coverage for publish/unpublish.

## Phase I.4 Completion — Shift Edit / Cancel Foundation

Phase I.4 has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/schemas/rota.py`
- `apps/api/tests/test_phase_i4_shift_update_cancel.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added `PATCH /api/v1/sites/{site_id}/shifts/{shift_id}`.
- Added `POST /api/v1/sites/{site_id}/shifts/{shift_id}/cancel`.
- Tenant/site scope is enforced for update and cancel.
- Draft-only editing is enforced: cancelled shifts and published shifts are rejected with safe conflict errors.
- Shift update validates `end_time > start_time`.
- Assigned staff remains optional and, when provided, must be active staff at the selected tenant/site.
- Cancel is soft cancellation using existing `status = cancelled`; no hard delete was added.
- Weekly rota read continues to return only active scheduled shifts, so cancelled shifts are excluded from the grid.
- Added audit logging for `shift_updated` and `shift_cancelled`.
- No new tables or migrations were added.

Frontend changes:
- Shift cards in `/admin/rota` can be clicked to open an edit modal.
- The existing shift modal now supports create and edit modes.
- Existing shift details can be updated and saved through the backend.
- Shift cancellation is available from the edit modal with a confirmation prompt.
- Weekly rota refetches after update and cancel.
- Safe success/error messages were added for update and cancel.
- Existing readiness gating remains in place.
- Future actions remain disabled.
- No localStorage shift persistence was added.
- No sensitive staff data is displayed.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: completed after backend test changes so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i4_shift_update_cancel.py -q"`: 8 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i3_shift_create.py apps/api/tests/test_phase_i1_rota_week_read.py apps/api/tests/test_phase_f_store_settings.py -q"`: 17 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed draft shift creation, update, weekly rota refetch/read, soft cancel, and cancelled-shift exclusion from the active rota response.
- Route smoke confirmed `/admin/rota`, `/admin`, `/admin/staff`, and `/admin/sites/new` return HTTP 200 from a fresh Next dev server on port 3005; ports 3003 and 3004 were already in use.
- Source smoke confirmed no publish, unpublish, generation, AI, localStorage rota persistence, or employee portal draft visibility path was added.

Known limitations:
- No publish or unpublish action yet.
- No rota generation yet.
- No drag and drop yet.
- No AI recommendations yet.
- No employee rota visibility work was added.
- No full multi-site switching yet; the page uses the first active backend store.
- The shift notes field remains UI-only because the current `Shift` model has no notes column.
- Existing `Shift` model has no `updated_at` or `updated_by_user_id`, so update/cancel actor tracking is via audit logs only.

Next recommended phase:
- Phase J — Publish/unpublish readiness-gated flow, or Phase I.5 — small edit/cancel browser automation coverage.

## Phase I.3 Completion — Create Draft Shift Backend Mutation

Phase I.3 has been implemented.

Files changed:
- `apps/api/routers/sites.py`
- `apps/api/schemas/rota.py`
- `apps/api/tests/test_phase_i3_shift_create.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added `POST /api/v1/sites/{site_id}/shifts`.
- The endpoint treats `site_id` as the current store/site identifier, consistent with Phase I.1.
- Shift creation requires the current `admin` tenant role through the existing role dependency.
- Tenant/site scope is enforced before creating a shift.
- Request validation rejects invalid time ranges where `end_time <= start_time`.
- Assigned staff is optional for open shifts.
- Assigned staff must be active staff at the selected tenant/site when provided.
- Created shifts use existing `Shift` persistence with `status = scheduled` and `published_at = null`.
- Added audit logging with action `shift_created` on entity type `shift`.
- No new tables, migrations, publish, unpublish, edit, delete, generation, drag/drop, AI, or employee portal visibility changes were added.

Frontend changes:
- Create Shift modal now submits to the backend.
- The modal builds ISO datetimes from the selected Monday-start week, selected day, start time, and end time.
- The staff dropdown submits the safe staff directory `user_id` as `assigned_employee_account_id`.
- Open/unassigned shifts submit with `assigned_employee_account_id: null`.
- Save is enabled only when the local form is valid and is disabled while submitting.
- On success, the modal closes, the draft state resets, a `Draft shift created.` message is shown, and the weekly rota is refetched.
- On failure, a safe user-facing error is shown without exposing backend internals.
- Existing readiness gating remains in place.
- Future actions remain disabled.
- No localStorage shift persistence was added.
- No sensitive staff data is displayed.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: completed after backend route/test changes so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i3_shift_create.py -q"`: 7 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i1_rota_week_read.py -q"`: 2 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_f_store_settings.py -q"`: 8 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed open draft shift creation, assigned draft shift creation using safe staff `user_id`, and weekly rota refetch/read returning both created shifts.
- Route smoke confirmed `/admin/rota`, `/admin`, `/admin/staff`, and `/admin/sites/new` return HTTP 200 from a fresh Next dev server on port 3004; port 3003 was already in use.
- Source smoke confirmed no publish, unpublish, generation, AI, localStorage rota persistence, or employee portal draft visibility path was added.

Known limitations:
- No shift edit/delete flow yet.
- No publish or unpublish action yet.
- No rota generation yet.
- No drag and drop yet.
- No AI recommendations yet.
- No employee rota visibility work was added.
- No full multi-site switching yet; the page uses the first active backend store.
- The create-shift notes field remains UI-only because the current `Shift` model has no notes column.

Next recommended phase:
- Phase I.4 — Shift edit/delete foundation, or Phase J — Publish/unpublish readiness-gated flow.

## Phase I.2 Completion — Create Shift Modal UI Only

Phase I.2 has been implemented.

Files changed:
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Frontend changes:
- `/admin/rota` now has a Create shift action.
- Create shift is enabled only when the selected first active site is operationally ready.
- Create shift remains disabled when no site is selected or backend readiness is not operational.
- Added a local create-shift modal with day, start time, end time, assigned staff, required role, and optional notes fields.
- Day options follow the existing Monday-start week logic.
- Staff dropdown uses the already fetched safe staff directory data and displays staff display names only.
- The staff dropdown includes an `Unassigned / Open shift` option.
- Added client-side validation for required day, required start/end times, and end time after start time.
- The modal save action is disabled and labelled for Phase I.3 backend wiring.
- Existing weekly rota display, readiness gating, and future disabled rota actions remain in place.
- No backend shift creation, edit, delete, publish, unpublish, generation, drag/drop, or AI logic was added.
- No localStorage rota persistence was added.
- No sensitive staff data is displayed.

Backend changes:
- None.

Checks:
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_f_store_settings.py -q"`: 8 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i1_rota_week_read.py -q"`: 2 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- Source smoke confirmed no new shift create/edit/publish/generate API call was added.
- Route smoke confirmed `/admin/rota`, `/admin`, `/admin/staff`, and `/admin/sites/new` return HTTP 200 from a fresh Next dev server on port 3003.

Known limitations:
- Create shift does not submit yet.
- No edit/delete shift flow yet.
- No publish or unpublish action yet.
- No rota generation yet.
- No drag and drop yet.
- No AI recommendations yet.
- No employee rota visibility work was added.
- No full multi-site switching yet; the page uses the first active backend store.

Next recommended phase:
- Phase I.3 — Wire create shift submission to the backend, or Phase H.1 — multi-site selector for rota/readiness.

## Phase I.1 Completion — Fetch and Display Weekly Rota (Read Only)

Phase I.1 has been implemented.

Files changed:
- `apps/api/main.py`
- `apps/api/routers/sites.py`
- `apps/api/schemas/rota.py`
- `apps/api/tests/test_phase_i1_rota_week_read.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Backend changes:
- Added read-only `GET /api/v1/sites/{site_id}/rota/week?week_start=YYYY-MM-DD`.
- The endpoint is backed by existing `stores`/`shifts` data and treats `site_id` as the current store/site identifier.
- Weekly rota reads are tenant-scoped and site-scoped.
- Weekly rota reads return only scheduled shifts within the selected Monday-start week.
- Response shift fields include `assigned_employee_account_id`, `role_required`, `start_time`, and `end_time`.
- No tables, migrations, shift creation, shift editing, publish, unpublish, or generation logic was added.

Frontend changes:
- `/admin/rota` now fetches weekly rota data for the selected first active site and selected week.
- Week selector changes refetch the displayed weekly rota.
- Rota grid now renders real backend shifts into Monday-to-Sunday columns.
- Open/unassigned shifts render in the Open shifts row.
- Assigned shifts render in the Staff rota row.
- Assigned employee names are resolved from the safe staff directory response when available; otherwise the card shows `Unassigned`.
- Shift cards show employee/unassigned label, time range, and optional role label.
- Added weekly rota loading and safe error states.
- Empty weeks show `No shifts created for this week`.
- Existing readiness logic remains in place.
- No localStorage rota persistence was added.
- No sensitive staff data is displayed.
- No create, edit, publish, unpublish, drag/drop, or AI suggestion UI logic was added.

Checks:
- `docker compose -f infra/docker-compose.yml build api`: completed after adding the new backend test/route so the container image included new files.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_i1_rota_week_read.py -q"`: 2 passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_f_store_settings.py -q"`: 8 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed `GET /api/v1/sites/{site_id}/rota/week?week_start=2026-04-06` returns the real selected-site, selected-week shift and excludes a shift from the following week.
- Route smoke confirmed `/admin/rota` and `/admin` return HTTP 200 from a fresh Next dev server on port 3003.

Known limitations:
- Rota display is read-only.
- No manual shift creation or editing yet.
- No publish or unpublish action yet.
- No rota generation yet.
- No drag and drop yet.
- No AI recommendations yet.
- No employee rota visibility work was added.
- No full multi-site switching yet; the page uses the first active backend store.

Next recommended phase:
- Phase I.2 — Manual shift creation foundation, or Phase H.1 — multi-site selector for rota/readiness.

## Phase H Completion — Rota Page Foundation UI

Phase H has been implemented.

Files changed:
- `apps/web/app/admin/rota/page.tsx`
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Frontend changes:
- `/admin/rota` page added.
- Sidebar Rota navigation now opens `/admin/rota`.
- Rota page uses backend store/readiness truth from `GET /api/v1/stores` and `GET /api/v1/stores/{store_id}/readiness`.
- Rota page uses the first active backend store, matching the current dashboard readiness limitation.
- Added selected-site and current-week display.
- Added UK Monday-start week selector with previous week, current week, and next week controls.
- Added readiness checklist for site details, opening hours, staff added, and operational ready.
- Added clear readiness-blocked state when the selected site is not operationally ready.
- Added empty weekly rota grid placeholder with Monday-to-Sunday columns and open-shifts/staff-rota rows.
- Added safe active-staff count summary using `GET /api/v1/staff/directory`.
- Added pending requests and actions placeholder cards.
- Added disabled future-action buttons for create shift, publish rota, generate week, AI recommendations, and export.
- Added loading, error, and no-site states.
- No shift create/edit/publish/generate API calls were added.
- No localStorage readiness or rota persistence was added.
- No sensitive staff data is displayed.

Backend changes:
- None.

Checks:
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_f_store_settings.py -q"`: 8 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- Source smoke confirmed no frontend calls were added for rota generation, shift creation, shift publish, or shift unpublish endpoints.
- Route smoke confirmed `/admin/rota`, `/admin`, `/admin/sites/new`, and `/admin/staff` return HTTP 200 from a fresh Next dev server on port 3003.

Known limitations:
- No manual shift creation or editing yet.
- No publish or unpublish action yet.
- No rota generation yet.
- No AI recommendations yet.
- No employee rota visibility work was added.
- No full multi-site switching yet; the page uses the first active backend store.

Next recommended phase:
- Phase I — Manual shift creation/editing foundation, or Phase H.1 — multi-site selector for rota/readiness.

## Phase G Completion — Store Readiness Display / Dashboard Integration

Phase G has been implemented.

Files changed:
- `apps/web/components/admin/admin-shell.tsx`
- `IMPLEMENTATION_STATUS.md`

Frontend changes:
- Admin dashboard setup state now uses backend store readiness from `GET /api/v1/stores/{store_id}/readiness`.
- Dashboard setup progress now includes company details, first site, and site readiness.
- Added a site readiness card showing site details, opening hours, staff added, and operational ready status.
- Added loading, empty, and safe error states for readiness loading.
- Operations gate now requires backend `operational_ready` instead of only checking that a site exists.
- The next setup action routes to site setup when opening hours are missing and to staff when staff readiness is missing.
- Readiness display shows only booleans/status and does not expose staff details or sensitive staff data.
- No localStorage readiness source or new localStorage persistence was added.
- `/admin/sites/new` still redirects back to the dashboard after successful creation.

Backend changes:
- None.

Checks:
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_f_store_settings.py -q"`: 8 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed a new tenant starts with no stores, a store without hours/staff is not ready, opening hours make `opening_hours_configured` true while staff remains missing, and adding one active staff profile makes `operational_ready` true.
- Route smoke confirmed `/admin`, `/admin/sites/new`, and `/admin/staff` return HTTP 200 from a fresh Next dev server on port 3003.

Known limitations:
- Readiness is still minimal: opening hours configured, staff configured, and operational ready.
- Only the first active store is shown in the dashboard readiness card.
- No rota page yet.
- No rota generation or publishing yet.
- No payroll, reports, billing, AI, employee portal, document, compliance, or sensitive staff work was added.

Next recommended phase:
- Phase H — Rota readiness gating/scaffold, or Phase G.1 — multi-site readiness selection.

## Phase F.1 Completion — Per-Day Store Opening Hours UI Hardening

Phase F.1 has been implemented.

Files changed:
- `apps/web/components/admin/site-setup-form.tsx`
- `IMPLEMENTATION_STATUS.md`

Frontend changes:
- `/admin/sites/new` now supports per-day custom opening hours.
- Custom opening hours use the current backend day mapping: Monday `0` through Sunday `6`.
- Each custom day can be marked open or closed.
- Closed days persist as `is_closed: true` with `open_time: null` and `close_time: null`.
- Open days require opening and closing times.
- Open days validate that closing time is later than opening time.
- Active site creation requires at least one open day.
- The `24/7` shortcut is retained and still persists seven open rows using `00:00` to `23:59`.
- A helper applies Monday's hours to all currently open days.
- Existing partial-success protection is preserved: if the store exists but opening hours or staff persistence fails, retry is blocked to avoid duplicate stores.
- Staff persistence still runs after successful store creation and opening-hours persistence.
- No new localStorage persistence was added.

Backend changes:
- None.

Checks:
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "pytest apps/api/tests/test_phase_f_store_settings.py -q"`: failed in this container with `ModuleNotFoundError: No module named 'apps'`.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/test_phase_f_store_settings.py -q"`: 8 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed custom per-day hours persist with different Saturday hours, Sunday closed persists as `is_closed: true`, and invalid time payloads still return 422.
- `/admin/sites/new` route smoke returned HTTP 200 from a fresh Next dev server on port 3003.

Known limitations:
- No full settings UI yet.
- Readiness is intentionally minimal and not yet wired into dashboard setup completion.
- Browser click-through automation was not performed; UI validation was verified through TypeScript/build review and route smoke, while backend persistence was verified through API smoke.
- No rota, payroll, reports, billing, AI, employee portal, document, compliance, or sensitive staff work was added.

Next recommended phase:
- Phase G — Store settings/readiness display, or Phase F.2 — deeper browser automation coverage for site setup.

## Phase F Completion — Store Opening Hours / Store Settings Persistence

Phase F has been implemented.

Files changed:
- `apps/api/models/store_opening_hours.py`
- `apps/api/models/store_settings.py`
- `apps/api/models/__init__.py`
- `apps/api/alembic/versions/0017_store_opening_hours_settings.py`
- `apps/api/schemas/store.py`
- `apps/api/routers/stores.py`
- `apps/api/tests/test_phase_f_store_settings.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/site-setup-form.tsx`
- `IMPLEMENTATION_STATUS.md`

Models added:
- `store_opening_hours`
- `store_settings`

Migration added:
- `0017_store_opening_hours_settings`

Endpoints added:
- `GET /api/v1/stores/{store_id}/opening-hours`
- `PUT /api/v1/stores/{store_id}/opening-hours`
- `GET /api/v1/stores/{store_id}/settings`
- `PATCH /api/v1/stores/{store_id}/settings`
- `GET /api/v1/stores/{store_id}/readiness`

Backend behaviour:
- Opening hours are tenant-scoped and store-scoped.
- Opening hours support one row per `day_of_week` per tenant/store.
- Store settings persist `business_week_start_day`.
- Store readiness is minimal: opening hours configured, staff configured, and operational ready.
- Mutations require the current admin tenant role.
- Reads require authenticated tenant membership.
- Cross-tenant store access is rejected.
- Audit logs are written for `store_opening_hours_updated` and `store_settings_updated`.

Frontend behaviour changed:
- `/admin/sites/new` still creates the backend store first.
- After store creation, opening hours are saved with `PUT /api/v1/stores/{store_id}/opening-hours`.
- `24/7` creates seven open-day rows using `00:00` to `23:59`.
- Custom hours create seven open-day rows using the selected opening and closing times.
- Custom opening hours validate that both times are present and closing time is later.
- If opening hours fail after store creation, the page shows partial success and blocks repeat store creation.
- Staff persistence still runs after store creation and opening-hours persistence succeeds.
- No new localStorage persistence was added.

Checks:
- `docker compose -f infra/docker-compose.yml up -d --build`: completed.
- `docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"`: passed.
- `apps/api/tests/test_phase_f_store_settings.py`: 8 passed.
- Existing relevant backend tests: 31 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke confirmed opening hours persist, settings persist, readiness responds, and invalid time payloads return 422.
- `/admin/sites/new` route smoke returned HTTP 200 from a fresh Next dev server.

Known limitations:
- The frontend persists the same opening/closing window for all seven days in this phase.
- `24/7` is represented as `00:00` to `23:59` because the backend currently requires `close_time > open_time`.
- Store settings are API-backed, but no full settings UI was built.
- Readiness is intentionally minimal and not yet wired into dashboard setup completion.
- No payroll, rota generation, reports, billing, AI, employee login, document, compliance, or sensitive staff work was added.

Next recommended phase:
- Phase F.1 — Store opening-hours UI hardening/per-day hours, or Phase G — Store settings/readiness display.

## Phase E.1 Completion — Staff Profile Detail Hardening and Tests

Phase E.1 has been implemented.

Files changed:
- `apps/web/components/admin/staff-profile-detail.tsx`
- `apps/web/components/admin/staff-directory.tsx`
- `IMPLEMENTATION_STATUS.md`

Hardening completed:
- Staff profile detail continues to use only `GET /api/v1/staff/directory`.
- Staff profile rendering remains explicitly limited to safe directory fields.
- Empty or missing staff IDs now show the safe not-found state without fetching.
- API errors now show generic safe profile/directory messages instead of backend details.
- Staff Directory profile links now URL-encode staff IDs before navigation.
- The profile limitation copy no longer displays sensitive future-feature labels.
- Back to Staff navigation remains available on the profile and not-found states.

Tests added:
- No frontend tests were added because the web app does not currently have Vitest, Jest, Playwright, or an existing frontend test pattern.
- No backend tests were added because Phase D.1 already covers the safe staff directory read model, tenant isolation, unauthenticated rejection, and sensitive-field exclusion.

Fields confirmed visible:
- `display_name`
- `email`
- `job_title`
- `phone`
- `store_name`
- `roles`
- `is_active`
- `created_at`

Sensitive fields confirmed hidden:
- Passwords and password hashes.
- Temporary and confirm password fields.
- National Insurance number.
- Right-to-work status, document data, and document files.
- Compliance uploads/documents.
- Hourly rate, overtime rate, base hours threshold, and weekly hour cap.
- Raw tenant IDs and tokens.

Checks:
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- Backend migration command completed before smoke verification.
- API smoke created a store, staff user, staff profile, and role, then confirmed `GET /api/v1/staff/directory` includes email, `store_name`, and roles while excluding sensitive fields.
- `/admin/staff/{staffId}` route smoke returned HTTP 200 from a fresh Next dev server.
- Unknown staff detail route smoke returned HTTP 200 and is handled by the client not-found state.

Known limitations:
- Browser click-through automation was not performed; verification used API and route smoke checks.
- The profile page still fetches the directory and finds the staff row client-side.
- The page remains read-only.
- No staff editing, password reset, compliance, payroll, document, employee login, rota, reporting, billing, AI, or site settings work was added.

Next recommended phase:
- Phase F — Site opening hours / site settings persistence, or Phase E.2 — Add frontend test framework for admin pages.

## Phase E Completion — Staff Profile Detail Page, Basic Non-Sensitive View

Phase E has been implemented.

Files changed:
- `apps/web/app/admin/staff/[staffId]/page.tsx`
- `apps/web/components/admin/staff-profile-detail.tsx`
- `apps/web/components/admin/staff-directory.tsx`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/lib/api-client.ts`
- `IMPLEMENTATION_STATUS.md`

Route added:
- `/admin/staff/[staffId]`

Frontend behaviour changed:
- Staff names and View profile actions in `/admin/staff` now open `/admin/staff/{staffId}`.
- The Staff Profile page loads safe staff data through the existing directory read model.
- The profile page is read-only and includes Back to Staff navigation.
- Missing staff IDs show a safe not-found state.
- Loading and error states are present.

APIs used:
- `GET /api/v1/staff/directory`

Fields displayed:
- `display_name`
- `email`
- `job_title`
- `phone`
- `store_name`
- `roles`
- `is_active`
- `created_at`

Sensitive fields intentionally hidden:
- Passwords and password hashes.
- Temporary and confirm password fields.
- National Insurance number.
- Right-to-work status, document data, and document files.
- Compliance uploads/documents.
- Hourly rate, overtime rate, base hours threshold, and weekly hour cap.
- Raw tenant IDs and tokens.

Checks:
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- API smoke created a store, staff user, staff profile, and role, then confirmed `GET /api/v1/staff/directory` includes email, `store_name`, and roles while excluding sensitive fields.
- `/admin/staff/{staffId}` route smoke returned HTTP 200 from a fresh Next dev server.
- Unknown staff detail route smoke returned HTTP 200 and is handled by the client not-found state.

Known limitations:
- Browser click-through automation was not performed; verification used API and route smoke checks.
- The profile page fetches the directory and finds the staff row client-side.
- The page remains read-only.
- No staff editing, password reset, compliance, payroll, document, employee login, rota, reporting, billing, or AI work was added.

Next recommended phase:
- Phase E.1 — Staff Profile detail hardening and tests, or Phase F — Site opening hours / site settings persistence.

## Phase D.1 Completion — Staff Directory Backend Read Model + Hardening

Phase D.1 has been implemented.

Files changed:
- `apps/api/routers/staff.py`
- `apps/api/schemas/staff.py`
- `apps/api/tests/test_phase_d1_staff_directory.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/staff-directory.tsx`
- `IMPLEMENTATION_STATUS.md`

Endpoint added:
- `GET /api/v1/staff/directory`

Final response shape:
- Plain JSON array of staff directory rows.
- Each row includes `id`, `user_id`, `display_name`, `email`, `job_title`, `phone`, `store_id`, `store_name`, `roles`, `is_active`, and `created_at`.

Frontend behaviour changed:
- `/admin/staff` now uses `GET /api/v1/staff/directory`.
- Staff email is displayed when available.
- Store/location names and roles come directly from the directory read model.
- Frontend no longer calls `GET /api/v1/staff/{staff_id}/roles` once per staff profile for the directory.
- Location filter options are built from directory rows.
- Existing client-side search and status/location filters remain.

Sensitive fields excluded:
- Passwords and password hashes.
- Temporary and confirm password fields.
- National Insurance number.
- Right-to-work document data/files and `rtw_status`.
- Compliance uploads/documents.
- Hourly rate, overtime rate, base hours threshold, and weekly hour cap.
- Raw tenant IDs and tokens.

Tests added:
- Staff directory returns email, store name, roles, active status, and created date.
- Multiple roles are included and normalized.
- Unassigned staff are supported.
- Tenant isolation is enforced.
- `store_id` filtering is covered.
- Sensitive fields are not returned.
- Unauthenticated requests are rejected.

Checks:
- `apps/api/tests/test_phase_d1_staff_directory.py`: 8 passed.
- Existing relevant backend tests: 23 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- Backend migration command completed before smoke verification.
- API smoke confirmed `GET /api/v1/staff/directory` includes email, `store_name`, and roles, and excludes sensitive fields.
- `/admin/staff` route smoke returned HTTP 200 from a fresh Next dev server.

Known limitations:
- The directory remains read-only.
- No staff profile detail page, editing, password reset, compliance, payroll, document, employee login, rota, reporting, billing, or AI work was added.

Next recommended phase:
- Phase E — Staff Profile detail page, basic non-sensitive view only, or Phase D.2 — Staff Directory frontend polish / pagination.

**Last updated:** 2026-04-27

## Phase D Completion — Staff Directory / Staff Management Page

Phase D has been implemented.

Files changed:
- `apps/web/app/admin/staff/page.tsx`
- `apps/web/components/admin/staff-directory.tsx`
- `apps/web/components/admin/admin-shell.tsx`
- `apps/web/lib/api-client.ts`
- `IMPLEMENTATION_STATUS.md`

Route added:
- `/admin/staff`

Frontend behaviour changed:
- Admin sidebar Staff item now opens `/admin/staff` after a first site exists.
- `/admin/staff` loads backend staff profiles and backend stores for the current tenant.
- Location names are mapped from `staff.store_id` to `stores.name`.
- Staff roles are loaded with `GET /api/v1/staff/{staff_id}/roles` and displayed as chips.
- Loading, error, empty, and no-filter-results states are present.
- Search is client-side and matches staff name, job title, phone, role, and location.
- Filters are client-side for location and status.

APIs used:
- `GET /api/v1/staff`
- `GET /api/v1/staff/{staff_id}/roles`
- `GET /api/v1/stores`

Fields displayed:
- `display_name`
- `job_title`
- `roles`
- `store_id` mapped to location name
- `phone`
- `is_active`
- `created_at`

Sensitive fields intentionally hidden:
- Passwords and password hashes.
- Temporary and confirm password fields.
- National Insurance number.
- Right-to-work document data/files.
- Compliance uploads/documents.
- Hourly rate, overtime rate, base hours threshold, and weekly hour cap.
- Raw tenant IDs and tokens.

Checks:
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- Backend migration command completed before smoke verification.
- Local API smoke created stores/staff/roles and confirmed `GET /api/v1/staff?store_id=<store_id>` plus `GET /api/v1/staff/{staff_id}/roles`.
- `/admin/staff` route smoke returned HTTP 200 from the Next dev server.

Known limitations:
- Staff email is not displayed because the current staff list API does not return related user email.
- Role loading uses one request per visible staff profile for this MVP directory.
- The page is read-only; editing, deletion, password reset, compliance, payroll, and document flows remain future phases.

Next recommended phase:
- Phase D.1 — Staff Directory hardening/details, or Phase E — Staff Profile detail page.

**Last updated:** 2026-04-26 11pm

## Phase C.1 Completion — Staff Persistence Hardening and Tests

Phase C.1 has been implemented.

Files changed:
- `apps/api/tests/test_phase_c_staff_setup_flow.py`
- `IMPLEMENTATION_STATUS.md`

Backend tests added:
- Full three-call staff setup flow.
- Staff listing by `store_id` after creation.
- Audit entries for tenant user creation, staff profile creation, and staff role assignment.
- Password/sensitive credential fields are not returned in staff setup responses.
- Unauthenticated requests are rejected for staff setup endpoints.
- Tenant member cannot create tenant users through `POST /api/v1/admin/users`.
- Cross-tenant `store_id` is rejected when creating staff profiles.
- Duplicate email, duplicate staff profile, duplicate staff role, and empty role behaviours are covered.
- Unsupported sensitive frontend fields sent to `POST /api/v1/staff` are ignored by the current backend schema and are not returned.

Checks:
- `apps/api/tests/test_phase_c_staff_setup_flow.py`: 10 passed.
- Existing relevant backend tests: 13 passed.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run lint`: did not run to completion because `next lint` prompted interactively to configure ESLint.
- `git diff --check`: passed.

**Last updated:** 2026-04-26 10pm

## Phase C Completion — Staff Persistence Using Existing Three-Call Flow

Phase C has been implemented.

Files changed:
- `apps/web/lib/api-client.ts`
- `apps/web/components/admin/site-setup-form.tsx`

Frontend behaviour changed:
- `Create Location` still creates the store first with `POST /api/v1/stores`.
- If staff were added, it then runs:
  1. `POST /api/v1/admin/users`
  2. `POST /api/v1/staff`
  3. `POST /api/v1/staff/{staff_id}/roles` once per non-empty role
- No-staff location creation still works.
- `Save as Draft` creates only the store and does not create staff accounts.
- Submit/add-staff actions are disabled while saving.
- Partial staff failures show that the location was created but staff could not be fully added, including staff name and failure message.
- After partial staff failure, repeat submit is blocked to avoid duplicate stores/users.
- Temporary passwords are held only in component memory before submission and cleared after a partial staff persistence attempt.

Payload sent to `POST /api/v1/admin/users`:
```json
{
  "email": "staff@example.com",
  "password": "<temporaryPassword>",
  "full_name": "First Last",
  "role": "member"
}
```

**Last updated:** 2026-04-26 9pm
## Phase B Completion — Site Setup Frontend Backend Wiring



Phase B has been implemented.



Files changed:

- `apps/web/lib/api-client.ts`

- `apps/web/components/admin/admin-shell.tsx`

- `apps/web/components/admin/site-setup-form.tsx`

- `infra/docker-compose.yml`



CORS note:

- `infra/docker-compose.yml` was changed only to add local CORS support for port `3002`, because `3001` was already in use.



Frontend behaviour changed:

- `/admin/sites/new` now creates a real backend store using `POST /api/v1/stores`.

- Dashboard “Create your first site” completion now uses `GET /api/v1/stores`.

- `forecourt_first_site` is no longer used as setup completion truth.

- Staff UI remains visual/prototype-only.

- Staff data is not sent to the backend.

- Sensitive staff fields are not stored in localStorage.



API endpoints used:

- `POST /api/v1/stores`

- `GET /api/v1/stores`



Exact fields sent to `POST /api/v1/stores`:

```json
{
  "code": "string|null",
  "name": "string",
  "timezone": "Europe/London",
  "address_line1": "string|null",
  "city": null,
  "postcode": null,
  "phone": "string|null",
  "manager_user_id": null
}
```

**Last updated:** 2026-04-26 7pm
## Phase A.2 Completion — Company Setup Frontend Backend Wiring

Phase A.2 has been implemented.

Files changed:
- `apps/web/lib/api-client.ts`
- `apps/web/lib/company-profile.ts`
- `apps/web/components/admin/company-setup-form.tsx`
- `apps/web/components/admin/admin-shell.tsx`

Frontend behaviour changed:
- `/admin/company` now loads from `GET /api/v1/company/profile`.
- `/admin/company` now saves using `PATCH /api/v1/company/profile`.
- PATCH sends only:
  - `company_name`
  - `owner_name`
  - `business_email`
  - `phone_number`
  - `registered_address`
- It does not send `tenant_id`, `company_setup_completed`, or `company_setup_completed_at`.
- Save button disables while saving.
- Loading and error states were added without redesigning the page.
- Dashboard company completion now uses backend `company_setup_completed`.
- Site setup still uses `forecourt_first_site`.

LocalStorage:
- `forecourt_company_profile` is no longer referenced as the company setup source of truth.
- `forecourt_access_token` remains unchanged.
- `forecourt_first_site` remains unchanged.

Checks:
- `npx tsc --noEmit` passed.
- `npm run build` passed.
- `npm run lint` did not run because `next lint` prompted interactively to configure ESLint.
- Backend migration applied cleanly.
- API smoke test passed for register, login, GET company profile, PATCH company profile, and GET persisted profile again.
- `company_setup_completed` returned `true` after profile completion.

Dev server note:
- Port `3001` was already in use.
- Frontend dev server ran on `http://localhost:3002` during verification.

Important:
- No backend code was changed in Phase A.2.
- No staff persistence was added.
- No site/store persistence was added.
- Next planned phase is Phase B: connect `/admin/sites/new` to backend Stores API.

**Last updated:** 2026-04-26 6pm
## Phase A Completion — Backend Company Profile API

Phase A backend Company Profile API has been implemented.

Files changed:
- `apps/api/main.py`
- `apps/api/models/tenant.py`
- `apps/api/schemas/company.py`
- `apps/api/routers/company.py`
- `apps/api/alembic/versions/0016_company_profile_fields.py`
- `apps/api/tests/test_company_profile.py`

Endpoints added:
- `GET /api/v1/company/profile`
- `PATCH /api/v1/company/profile`

Migration:
- `0016_company_profile_fields`

Targeted tests:
- Company profile + auth tests passed: `13 passed, 1 skipped`.

Full suite:
- Full repo test suite currently fails due to existing rota/shift/employee test failures, not the new company profile tests.
- These failures should be investigated separately and not mixed into Phase A.2.

Important:
- No frontend changes were made in Phase A.
- Company setup page still needs to be connected to backend in Phase A.2.

**Last updated:** 2026-04-26 3pm  
**Purpose:** Single-page truth snapshot of what is actually built today versus what is planned. Use this before asking any AI coding agent to modify the project.

---

## Status Legend

| Badge | Meaning |
|---|---|
| ✅ | Implemented and working in current repo/database |
| 🟡 | Partially implemented, prototype-only, or not fully connected |
| ❌ | Not yet implemented |
| ⚠️ | Diverged from PRD / target contract |

---

## Current High-Level State

ForecourtOS currently has a working FastAPI/PostgreSQL backend with authentication, tenant foundation, stores, staff profiles, shifts, rota-related foundations, audit logs, and several workforce scheduling modules already present in the database and routers.

The frontend now has a working admin registration/login flow and protected admin shell. It also has frontend pages for Company Setup and Add New Location, but those setup forms currently use frontend/localStorage prototype storage rather than backend persistence.

**Most important current gap:** the frontend setup flow is not yet wired to the existing backend stores/staff APIs, and company profile persistence still needs a proper backend endpoint.

---

## Local Development Runtime

### Backend

```bash
cd /home/vachan/code/anci-ops-suite
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

### Frontend

```bash
cd /home/vachan/code/anci-ops-suite/apps/web
npm run dev -- --hostname 0.0.0.0 --port 3001
```

Frontend URL currently used during development:

```text
http://localhost:3001
```

### CORS Note

Backend CORS must allow the frontend dev port. In `infra/docker-compose.yml`, `CORS_ORIGINS` must be provided as a JSON-array string, for example:

```yaml
CORS_ORIGINS: '["http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001"]'
```

---

## Backend Implementation Snapshot

### Auth and Tenant Foundation — ⚠️ Implemented but diverged from PRD target

Implemented endpoints currently behave as follows:

#### Register

```text
POST /api/v1/auth/register
```

Actual request body:

```json
{
  "full_name": "string",
  "email": "string",
  "password": "string"
}
```

Actual response shape:

```json
{
  "id": "uuid",
  "email": "string",
  "is_active": true,
  "active_tenant_id": "uuid",
  "active_tenant_role": "admin",
  "created_at": "datetime"
}
```

Notes:

- Creates user, default tenant, and tenant membership.
- Sets `users.active_tenant_id`.
- Does **not** return access token.
- Does **not** currently use `work_email`, `confirm_password`, or `accepted_terms`.
- Does **not** currently trigger email verification.

#### Login

```text
POST /api/v1/auth/login
```

Actual request format:

```text
Content-Type: application/x-www-form-urlencoded
username=<email>&password=<password>
```

Actual response:

```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

Notes:

- Uses FastAPI OAuth2 form flow.
- No refresh token yet.
- No `/auth/admin/login` split yet.
- No 2FA yet.

#### Current User

```text
GET /api/v1/auth/me
```

Actual response:

```json
{
  "id": "uuid",
  "email": "string",
  "is_active": true,
  "active_tenant_id": "uuid",
  "active_tenant_role": "admin",
  "created_at": "datetime"
}
```

Notes:

- Flat current-user response.
- Does not yet return PRD target shape with `portal`, `user_id`, `tenant_id`, `role`, or `assigned_sites`.

---

## Database Tables Actually Present

Current local database contains the following tables:

```text
audit_logs
availability_entries
coverage_templates
hot_food_demand_inputs
hour_targets
rota_recommendation_drafts
rota_recommendation_items
shift_requests
shifts
staff_profiles
staff_roles
stores
tenant_users
tenants
users
alembic_version
```

This means the backend is already beyond basic auth/tenant foundation. Stores, staff, shifts, availability, rota recommendations, coverage templates, and audit logs exist.

---

## Backend Modules / Routers Present

Current router files include:

```text
auth.py
admin_users.py
stores.py
staff.py
shifts.py
shift_requests.py
availability.py
hour_targets.py
coverage_templates.py
rota.py
rota_recommendations.py
employee.py
hot_food.py
health.py
```

---

## Module Status

| Module | Status | Notes |
|---|---:|---|
| Auth register/login/me | ⚠️ | Works, but differs from PRD target contracts. |
| Tenant foundation | ✅ | `tenants`, `users`, `tenant_users`, active tenant pattern present. |
| Tenant isolation dependency | ✅ | Implemented via tenant membership/dependency pattern. |
| Audit logs | 🟡 | Table and writes exist for several actions; not yet wired to every sensitive action. |
| Stores / Locations | ✅/🟡 | Backend stores API exists. Frontend site setup is not yet wired to it. |
| Staff profiles | ✅/🟡 | Backend staff profile and role APIs exist. Frontend staff setup is not yet wired to them. |
| Admin user creation | ✅ | `/api/v1/admin/users` exists and creates users inside tenant. |
| Employee accounts / separate employee portal login | ❌/🟡 | Employee-facing API layer exists partially, but separate employee account model/login is not fully implemented. |
| Shifts | ✅ | Core shift model/router exists. |
| Shift requests | ✅ | Shift request workflow foundation exists. |
| Availability | ✅ | Availability entries exist. |
| Hour targets | ✅ | Hour targets exist. |
| Rota recommendations | ✅/🟡 | Draft/recommendation foundations exist; frontend not connected. |
| Coverage templates | ✅ | Coverage template model/router exists. |
| Company profile API | ❌ | Frontend company setup currently uses localStorage. Backend endpoint needed. |
| Frontend admin register/login | ✅ | Working. |
| Frontend protected admin shell | ✅ | Working with current `/auth/me` shape. |
| Frontend Company Setup page | 🟡 | UI works; stores `forecourt_company_profile` in localStorage. |
| Frontend Add New Location page | 🟡 | UI works; stores `forecourt_first_site` in localStorage. |
| Frontend Staff page/sidebar directory | ❌ | Sidebar placeholder exists; real staff directory not built. |
| Reports | ❌ | Not yet implemented. |
| Billing / Stripe | ❌ | Not yet implemented. |
| AI features | ❌ | Not yet implemented. |
| Notifications | ❌ | Not yet implemented. |
| 2FA | ❌ | Not yet implemented. |
| Email verification | ❌ | Not yet implemented. |
| Password reset | ❌ | Not yet implemented. |
| Refresh tokens | ❌ | Not yet implemented. |
| File uploads / documents | ❌ | Not yet implemented. |

---

## Frontend Pages Currently Built

```text
/admin/register
/admin/login
/admin
/admin/company
/admin/sites/new
```

### Working Flow

```text
Register → Login → Protected Admin Dashboard → Company Setup → Add New Location
```

### Current LocalStorage Keys

```text
forecourt_access_token
forecourt_company_profile
forecourt_first_site
```

### Critical Temporary Architecture Note

`forecourt_company_profile` and `forecourt_first_site` are prototype-only frontend storage. They are useful for visual MVP progress but must not be treated as production persistence.

No further major operational UI should be built on top of localStorage unless the storage is abstracted behind helper functions and has a clear backend replacement plan.

---

## Current Backend API Facts Relevant to Frontend Wiring

### Stores API

`POST /api/v1/stores` exists.

Actual `StoreCreate` fields:

```json
{
  "code": "string|null",
  "name": "string",
  "timezone": "string|null",
  "address_line1": "string|null",
  "city": "string|null",
  "postcode": "string|null",
  "phone": "string|null",
  "manager_user_id": "uuid|null"
}
```

The current frontend `/admin/sites/new` captures more fields than the backend store schema supports, including:

```text
site email
opening hours type
opening time
closing time
notes
manager name/email/phone
staff members
employee portal credentials
sensitive staff fields
```

These must either be mapped partially, extended in backend migrations, or handled by a future setup-wizard endpoint.

### Staff API

Current backend staff creation expects an existing tenant user.

Actual flow:

```text
1. POST /api/v1/admin/users
2. POST /api/v1/staff
3. POST /api/v1/staff/{staff_id}/roles
```

This means the frontend Add Staff section cannot simply POST staff form data directly to `/staff` unless it first creates or resolves a tenant user.

---

## Immediate Next Recommended Work

Do not build more major frontend pages against localStorage.

Recommended order:

1. Create/update documentation with truthful implementation status.
2. Build backend Company Profile persistence.
3. Connect `/admin/company` to backend and remove localStorage as source of truth.
4. Decide whether site setup should:
   - use existing `/stores` endpoint with limited supported fields, or
   - extend `stores` schema, or
   - create a dedicated setup wizard endpoint.
5. Connect `/admin/sites/new` to backend.
6. Design proper staff persistence path using `/admin/users`, `/staff`, and `/staff/{id}/roles`, or create a combined setup endpoint.
7. Build Staff sidebar page from backend data.
8. Then proceed toward rota UI.

---

## Known PRD Drift

The PRDs should be treated as target architecture unless marked current. Known divergences:

1. Register contract differs from API PRD.
2. Login path and body format differ from API PRD.
3. `/auth/me` response differs from API PRD.
4. First registered user currently behaves as `admin`; PRD wants Owner/Tenant as highest authority.
5. Company setup frontend exists, but backend company profile endpoint does not.
6. Site/staff setup frontend exists, but is localStorage prototype and richer than current backend store/staff APIs.
7. Employee portal login/account model is not yet fully implemented.
8. Billing, AI, reports, notifications, 2FA, email verification, refresh tokens, and password reset remain target features, not current implementation.
