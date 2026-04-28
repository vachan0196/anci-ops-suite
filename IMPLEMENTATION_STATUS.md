# ForecourtOS / Anci Ops Suite — Implementation Status

**Last updated:** 2026-04-28

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
