# ForecourtOS / Anci Ops Suite — Implementation Status

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

