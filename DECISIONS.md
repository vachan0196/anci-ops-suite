# ForecourtOS / Anci Ops Suite — Decisions Log

**Last updated:** 2026-04-29
**Purpose:** Record deliberate product/technical decisions, especially where current implementation diverges from PRDs. Future AI agents must read this before modifying auth, onboarding, company/site/staff setup, or persistence.

---

## Decision Status Legend

| Badge | Meaning |
|---|---|
| Active | Current project decision to follow |
| Temporary | Accepted for prototype/MVP speed, must be revisited |
| Target | Future desired state, not current implementation |
| Needs decision | Not settled yet |

---

## D001 — Current Register Contract Differs From API PRD

**Status:** Temporary  
**Area:** Auth / onboarding  
**Date recorded:** 2026-04-26

### Current implementation

`POST /api/v1/auth/register` currently accepts:

```json
{
  "full_name": "string",
  "email": "string",
  "password": "string"
}
```

It returns a flat user object with:

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

### PRD target

API PRD target expects:

```json
{
  "full_name": "string",
  "work_email": "string",
  "password": "string",
  "confirm_password": "string",
  "accepted_terms": true
}
```

Target response includes `user_id`, `tenant_id`, `role`, and `email_verification_required`.

### Why accepted temporarily

The simpler endpoint already works and unblocked frontend register/login development.

### Risk

Future Codex/AI agents reading the API PRD may build frontend/backend work against the target contract and break the current working implementation.

### Revisit when

Before external user testing or before replacing localStorage setup with real backend onboarding.

### Future direction

Move toward the PRD target by adding:

- `work_email` naming or an aliasing strategy,
- confirm-password validation,
- terms acceptance storage,
- email verification status,
- clearer Owner role response.

---

## D002 — Current Login Uses `/auth/login`, Not `/auth/admin/login`

**Status:** Temporary  
**Area:** Auth  
**Date recorded:** 2026-04-26

### Current implementation

Login endpoint:

```text
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded
username=<email>&password=<password>
```

Response:

```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

### PRD target

API PRD target expects:

```text
POST /api/v1/auth/admin/login
```

with JSON body:

```json
{
  "email": "string",
  "password": "string"
}
```

and response containing `refresh_token`, `requires_2fa`, and user summary.

### Why accepted temporarily

The current backend uses FastAPI OAuth2PasswordRequestForm and works reliably.

### Risk

Frontend prompts based on PRD will call the wrong endpoint and fail with 404.

### Revisit when

Before formalising employee login separation or adding refresh tokens/2FA.

### Future direction

Either:

1. keep `/auth/login` as a generic OAuth2 login and add `/auth/admin/login` as a wrapper/alias, or
2. migrate frontend and backend fully to `/auth/admin/login` once employee login is introduced.

---

## D003 — Current `/auth/me` Shape Differs From API PRD

**Status:** Temporary  
**Area:** Auth/session frontend integration  
**Date recorded:** 2026-04-26

### Current implementation

`GET /api/v1/auth/me` returns:

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

Phase K.1 update, 2026-04-28:

The same endpoint now also accepts employee JWT subjects in the form `employee:{employee_account_id}` and returns a safe employee session shape:

```json
{
  "portal": "employee",
  "employee_account_id": "uuid",
  "tenant_id": "uuid",
  "site_id": "uuid",
  "display_name": "string"
}
```

The admin response shape above is preserved for compatibility. Admin-only dependencies still reject employee tokens, and employee-only dependencies still reject admin tokens.

### PRD target

API PRD target expects admin response:

```json
{
  "portal": "admin",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "role": "owner|admin|manager",
  "assigned_sites": []
}
```

### Why accepted temporarily

The frontend admin shell now maps the current backend fields and works.

### Risk

Any future frontend built against the PRD target shape will treat valid users as unauthenticated unless the mapping is handled.

### Revisit when

When role model is upgraded from `admin/member` to `owner/admin/manager/employee` and employee portal auth is introduced.

### Future direction

Add an auth/session response model that explicitly returns portal, role, tenant, and site assignments.

---

## D004 — First Registered User Currently Gets `admin`, But PRD Wants Owner/Tenant

**Status:** Needs decision  
**Area:** Roles / tenant authority  
**Date recorded:** 2026-04-26

### Current implementation

The first registered user receives tenant membership role:

```text
admin
```

### PRD target

The first user should be the Owner/Tenant with highest authority.

### Risk

Using `admin` for the first user blurs the distinction between owner governance and operational admin roles.

### Recommended decision

Migrate first registered user role to:

```text
owner
```

Then use:

```text
admin
manager
employee
```

for later created users.

### Revisit when

Before implementing billing, company settings, site lifecycle actions, sensitive staff data, or permission matrix enforcement.

---

## D005 — Company Setup Currently Uses localStorage

**Status:** Temporary  
**Area:** Frontend setup / persistence  
**Date recorded:** 2026-04-26

### Current implementation

`/admin/company` stores profile data in browser localStorage key:

```text
forecourt_company_profile
```

### Why accepted temporarily

It allowed fast UI development and setup-flow validation before backend company profile endpoint existed.

### Risk

Data disappears across browsers/devices and is not safe as product persistence. Dashboard progress relies on client-side prototype data.

### Revisit when

Immediately before building further product modules that depend on company details.

### Future direction

Create backend company profile persistence, preferably by extending `tenants` for MVP or adding `company_profiles` if a cleaner separation is needed.

Recommendation for MVP:

```text
Extend tenants table with company profile fields.
```

---

## D006 — Site Setup Currently Uses localStorage Despite Existing Stores API

**Status:** Temporary  
**Area:** Frontend setup / persistence  
**Date recorded:** 2026-04-26

### Current implementation

`/admin/sites/new` stores setup data in localStorage key:

```text
forecourt_first_site
```

### Backend reality

A backend stores API already exists:

```text
POST /api/v1/stores
GET /api/v1/stores
GET /api/v1/stores/{store_id}
PATCH /api/v1/stores/{store_id}
POST /api/v1/stores/{store_id}/deactivate
```

Current `StoreCreate` supports:

```text
code
name
timezone
address_line1
city
postcode
phone
manager_user_id
```

### Current frontend captures extra fields not yet supported by StoreCreate

```text
site email
opening hours type
opening time
closing time
status
notes
manager name/email/phone
staff members
employee portal credentials
sensitive staff fields
```

### Risk

Frontend UI may imply data is saved when it is only stored locally and/or not supported by backend schema.

### Future direction

Choose one:

1. Wire only supported fields to existing `/stores` API.
2. Extend stores schema with extra fields.
3. Build a dedicated setup wizard endpoint that handles site + manager + staff together.

Recommended next step:

```text
Wire minimal site fields to existing stores API, then decide whether to extend schema.
```

---

## D007 — Staff Setup Is Folded Into Site Setup

**Status:** Active  
**Area:** Product flow / onboarding UX  
**Date recorded:** 2026-04-26

### Decision

The setup dashboard now has two steps:

```text
1. Complete company setup
2. Create your first site
```

The separate setup card “Add your staff” was removed. Staff setup now lives inside the site setup page.

### Why

Staff members need a site context. A standalone “Add Staff” setup card before a site exists has no meaningful action path.

### Risk

The site setup page can become too large if staff, pay, right-to-work, and portal access are all handled at once.

### Mitigation

Use cards and progressive disclosure. Staff section starts with an Add Staff Member button rather than showing all fields by default.

### Future direction

After first site exists, the Staff sidebar page should become a real staff directory and management area.

---

## D008 — Sensitive Staff Data Must Not Be Stored in localStorage

**Status:** Active  
**Area:** Security / frontend prototype  
**Date recorded:** 2026-04-26

### Decision

The UI may show sensitive fields for design/prototype purposes, but these must not be persisted to localStorage.

Do not persist:

```text
National Insurance number
BRP/passport/share-code data
document uploads
temporary passwords
confirm passwords
right-to-work document files
compliance document files
```

### Why

localStorage is not appropriate for sensitive staff/compliance/password data.

### Current approach

Sensitive fields are UI-only in the frontend prototype. Staff preview list should store only non-sensitive fields such as name, email, phone, roles, weekly hour cap, and account status label.

### Revisit when

When backend staff compliance and employee account persistence are implemented.

### Future direction

Persist sensitive staff/compliance data only through secure backend endpoints with:

- Owner-only or explicitly permissioned access,
- audit logging,
- 2FA where applicable,
- no document storage until file handling is properly designed.

---

## D009 — Staff Creation Backend Requires Existing Tenant User

**Status:** Active / needs UX reconciliation  
**Area:** Staff backend integration  
**Date recorded:** 2026-04-26

### Current backend flow

Staff creation currently requires:

```text
1. POST /api/v1/admin/users
2. POST /api/v1/staff
3. POST /api/v1/staff/{staff_id}/roles
```

### Why

`StaffProfileCreate` expects an existing `user_id`; staff profiles are linked to users.

### Frontend mismatch

The `/admin/sites/new` Add Staff Member form currently behaves like a single staff creation form, but backend requires multiple steps.

### Risk

Naively connecting the staff form to `/staff` will fail unless a tenant user is created first.

### Future direction

Choose one:

1. Use the existing three-call flow from the frontend.
2. Create a backend setup wizard endpoint that performs user + staff profile + roles creation transactionally.

Recommended for future MVP polish:

```text
Create a setup wizard endpoint for first site + initial staff.
```

Recommended immediate practical step:

```text
Wire site creation first, then staff persistence separately.
```

---

## D010 — Frontend Auth Token Uses localStorage Temporarily

**Status:** Temporary  
**Area:** Auth/session frontend  
**Date recorded:** 2026-04-26

### Current implementation

Frontend stores access token in localStorage key:

```text
forecourt_access_token
```

### Why accepted temporarily

It allows local MVP preview and protected page testing quickly.

### Risk

localStorage token storage is not the intended production auth/session strategy.

### Revisit before

- external user testing,
- staging deployment,
- production deployment.

### Future direction

Move to a more secure token/session strategy, likely involving:

- short-lived access tokens,
- refresh token handling,
- HTTP-only cookies or equivalent secure storage,
- logout/revocation support,
- proper refresh flow.

---

## D011 — Dashboard Setup Progress Is Currently Derived From Frontend Prototype State

**Status:** Temporary  
**Area:** Frontend setup dashboard  
**Date recorded:** 2026-04-26

### Current implementation

Setup progress uses:

```text
forecourt_company_profile
forecourt_first_site
```

in localStorage.

### Why accepted temporarily

It gives a good visual onboarding MVP quickly.

### Risk

Setup progress is browser-specific and not real tenant readiness.

### Future direction

Dashboard progress should come from backend readiness endpoints, likely:

```text
GET /api/v1/company/profile
GET /api/v1/stores
GET /api/v1/sites/{id}/readiness
```

or a dedicated:

```text
GET /api/v1/setup/status
```

---

## D012 — Do Not Build More Major Operational UI Against localStorage

**Status:** Active  
**Area:** Roadmap / technical discipline  
**Date recorded:** 2026-04-26

### Decision

No further major operational modules should be built on top of localStorage prototype data.

This includes:

```text
real Staff directory
rota generation UI
payroll/compensation UI
reports
hot food operations
employee portal workflows
```

### Why

Every additional UI built against localStorage increases later refactor cost and risks lying to users about persistence.

### Allowed exception

Small visual placeholders are acceptable if clearly marked as not functional.

### Next recommended work

Move setup data to backend persistence, beginning with:

```text
1. Company Profile backend
2. Company frontend integration
3. Site frontend integration with stores API
4. Staff persistence design/integration
```

---

## D013 — PRDs Are Target Architecture Unless Marked Current

**Status:** Active  
**Area:** Documentation / AI agent safety  
**Date recorded:** 2026-04-26

### Decision

Existing PRDs should be treated as target architecture, not guaranteed current implementation.

### Why

Several PRDs describe planned contracts, roles, billing, AI, employee portal, permissions, and security behaviours that are not yet implemented or have diverged.

### Required documentation pattern

Each updated PRD should include:

```text
Implementation Status
Current Implementation
Target Contract / Target Architecture
Known Divergences
```

### Next documentation work

Update PRDs in this priority order:

```text
1. API contracts
2. Database schema
3. Frontend pages
4. Permission matrix
5. Technical architecture
6. Security checklist
7. Testing strategy
8. Billing / AI / data retention / incident response banners
```

---

## D014 — CORS Requires JSON-Array String Format in Docker Environment

**Status:** Active  
**Area:** Local development / environment  
**Date recorded:** 2026-04-26

### Decision

For local Docker Compose, `CORS_ORIGINS` must be passed as a JSON-array string.

Example:

```yaml
CORS_ORIGINS: '["http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001"]'
```

### Why

Pydantic settings parses `CORS_ORIGINS` as `list[str]`. A plain string like `http://localhost:3000` may not parse correctly.

### Risk

If CORS is misconfigured, frontend requests fail in the browser even though backend works via curl.

### Revisit when

When formal dev/staging/prod environment configuration is cleaned up.

---

## D022 — Employee Login Uses Site Code Lookup Before Site-Scoped Login

**Status:** Active
**Area:** Employee auth / login UX
**Added:** Phase K.2

### Decision

Employee Portal login should not require employees to paste raw site UUIDs.

The login flow uses:

```text
site_code -> site_id lookup -> site-scoped username/password login
```

### Rules

- Lookup response is public but minimal.
- Lookup must not expose tenant ID, staff data, billing data, readiness, or operational details.
- Public site lookup must return minimal non-sensitive data only.
- Employee credential validation remains generic.
- Existing `site_id` employee login remains supported for API compatibility.

### Reason

This improves employee usability while preserving site-scoped employee identity.
