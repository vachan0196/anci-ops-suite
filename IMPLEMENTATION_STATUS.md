# ForecourtOS / Anci Ops Suite — Implementation Status

**Last updated:** 2026-04-27

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
