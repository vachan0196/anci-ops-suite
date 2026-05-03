# ForecourtOS / Anci Ops Suite — Decisions Log

**Last updated:** 2026-05-02
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

---

## D023 — Employee Availability Reuses Existing Availability Table With Employee Account Scope

**Status:** Active
**Area:** Employee availability / persistence
**Added:** Phase L

### Decision

Phase L extends the existing `availability_entries` table instead of replacing it.

Employee portal availability rows are written with both:

- existing admin-era truth: `tenant_id`, `store_id`, `user_id`
- employee portal truth: `site_id`, `employee_account_id`

The Phase L duplicate rule is:

```text
tenant_id + site_id + employee_account_id + date + start_time + end_time + type
```

### Rules

- `/api/v1/employee/me/availability` requires employee tokens.
- Admin tokens cannot access employee availability endpoints.
- Employee availability list/create/delete is self-only and one-site scoped.
- Employee availability create/delete is locked when the employee has any published scheduled shift in that selected site/week.
- The older `/api/v1/availability` route remains untouched for current compatibility, but it is not the Phase L employee portal API.

### Reason

The table already existed from earlier availability work. Extending it avoids a risky table replacement while making employee-account scope explicit for the production employee portal.

---

## D024 — Employee Requests Reuse Shift Requests Without Rota Mutation

**Status:** Active
**Area:** Employee requests / rota governance
**Added:** Phase M

### Decision

Phase M extends the existing `shift_requests` table for employee leave, cover, and swap request creation.

Employee portal request rows are written with:

- existing request truth: `tenant_id`, `shift_id`, `requester_user_id`, `target_user_id`, `type`, `status`, `notes`
- employee portal truth: `site_id`, `requester_employee_account_id`, `target_employee_account_id`, `reason`, `start_date`, `end_date`, `cancelled_at`

### Rules

- `/api/v1/employee/me/requests` requires employee tokens.
- Admin tokens cannot access employee request endpoints.
- Employee request list/create/cancel is self-only and one-site scoped.
- Phase M creates only `pending` leave, cover, and swap requests.
- Employees can cancel only their own pending requester-side requests.
- Employee requests do not directly update shifts or rota.
- Admin approval, rejection, target accept/decline, and rota mutation remain outside Phase M.

### Reason

The project already had `shift_requests` and admin-side shift request machinery. Extending that table keeps one request source of truth while preserving the Phase M boundary: employee-side creation/list/cancel only.

---

## D025 — Admin Request Approval Records Decisions Without Rota Mutation

**Status:** Active
**Area:** Request workflow / rota safety
**Added:** Phase N

### Decision

Phase N allows Owner/Admin/Manager to approve or reject pending employee requests within authorised site scope.

Approval/rejection records the decision, approver, reason, and timestamp.

Phase N does not directly mutate shifts or rota.

### Why

Request approval needs to be visible and auditable before automatic rota mutation is introduced.

Automatic rota updates are deferred to Phase O to avoid unsafe side effects.

### Rules

- Admin request queue requires an admin-side token.
- Owner/Admin access is tenant/site scoped.
- Manager access is limited to sites where `stores.manager_user_id` matches the current user.
- Employee tokens cannot access admin request queue.
- Only pending requests can be approved or rejected.
- Approval/rejection must be audit logged.
- Approved requests do not update rota in Phase N.

---

## D026 — Approved Leave Requests Open Affected Published Shifts Without Replacement Assignment

**Status:** Active
**Area:** Request workflow / rota application
**Added:** Phase O

### Decision

Phase O applies approved leave requests to the rota by opening/unassigning affected published scheduled shifts for the requesting employee within the approved leave date range.

Swap and cover approvals do not mutate rota in Phase O.

### Why

Leave request application is the safest first rota mutation.

Automatic swap/cover reassignment requires target acceptance and replacement rules, so it is deferred.

### Rules

- Only approved leave requests trigger rota mutation in Phase O.
- Only shifts assigned to the requester can be changed.
- Only same-tenant and same-site shifts can be changed.
- Affected shifts are opened/unassigned, not deleted.
- Rota is not unpublished.
- No replacement employee is assigned automatically.
- Shift changes are audit logged.

---

## D027 — Cover Request State Machine

**Status:** Active
**Area:** Request workflow / cover requests
**Added:** Phase P.0

### Decision

A cover request means the requester wants another employee to take one of their published shifts.

Cover requests can be untargeted or targeted.

Target acceptance changes the request workflow state only. It does not mutate rota.

Owner/Admin/Manager approval is required before any cover request changes the rota.

### Rules

- Cover requests must remain tenant-scoped and site-scoped.
- Targeted cover requires a same-site active target employee.
- A targeted employee must be able to see enough safe shift detail before accepting or declining.
- Target acceptance does not update shifts or rota.
- Target decline does not update shifts or rota.
- Admin rejection does not update shifts or rota.
- Approved targeted cover reassigns the affected published shift from requester to target employee.
- Approved untargeted cover opens/unassigns the affected published shift for cover.
- Cover approval keeps the shift published and audit logs the request decision and shift update.

### Why

Cover is a one-shift reassignment workflow, but it still needs consent and admin approval before rota mutation. Keeping target acceptance separate from rota application preserves auditability and prevents employees from changing published rota directly.

---

## D028 — Swap Request State Machine

**Status:** Active
**Area:** Request workflow / swap requests
**Added:** Phase P.0

### Decision

A swap request means the requester wants to exchange shifts with another employee.

A true shift-for-shift swap requires all of the following to be represented explicitly:

- requester shift
- target employee
- target employee shift to exchange

The current `shift_requests` model stores one `shift_id` and one `target_employee_account_id`, but it does not store a target shift. Phase P must not fake a full two-way swap without explicit target-shift modelling.

Target acceptance changes the request workflow state only. It does not mutate rota.

Owner/Admin/Manager approval is still required before any swap request changes the rota.

### Rules

- Swap requests must remain tenant-scoped and site-scoped.
- Targeted employees can accept or decline the swap workflow.
- Target acceptance does not update shifts or rota.
- Target decline does not update shifts or rota.
- Admin rejection does not update shifts or rota.
- Full swap rota mutation is deferred until the data model explicitly supports target shift selection or another durable representation for the second side of the swap.
- Older one-shift reassignment semantics must not be treated as a full employee portal swap.

### Why

The current model can describe "requester shift plus target employee" but not "requester shift plus target employee shift." Applying a full swap without that data would create unsafe rota side effects and misleading audit history.

---

## D029 — Phase P Implementation Breakdown

**Status:** Active
**Area:** Request workflow / phase planning
**Added:** Phase P.0

### Decision

Phase P is split into smaller safe phases:

- Phase P.0 — workflow scoping and decisions.
- Phase P.1 — employee-safe same-site co-worker/target list if needed.
- Phase P.2 — target accept/decline workflow.
- Phase P.3 — cover approval rota application.
- Phase P.4 — swap approval rota application only after target shift modelling is confirmed.

### Rules

- Phase P.0 is documentation and scoping only.
- Phase P.1 must expose only employee-safe same-site target information.
- Phase P.2 target actions must update request workflow state only.
- Phase P.3 may apply cover rota changes after target/admin rules are implemented.
- Phase P.4 may apply swap rota changes only after target-shift modelling is explicit and tested.
- Notifications, payroll/earnings recalculation, AI actions, and request history hide/restore remain separate future work.

### Why

Swap and cover workflows mix employee consent, admin approval, site-scoped permissions, and published rota mutation. Splitting the work avoids turning Phase P into a broad workflow rewrite.

---

## D030 — Target-Accepted Cover Approval Reassigns Shift After Admin Approval

**Status:** Active
**Area:** Request workflow / rota application
**Added:** Phase P.3

### Decision

A targeted cover request can reassign the affected published scheduled shift only after the target employee accepts and an authorised Owner/Admin/Manager approves.

Target acceptance alone does not mutate rota.

Admin approval is the final authority that applies the shift reassignment.

### Rules

- Only target-accepted cover requests can reassign shifts.
- The shift must belong to the requester.
- The target employee must be active and same-site/same-tenant.
- The shift remains published and scheduled.
- The shift is reassigned, not duplicated or deleted.
- Swap requests remain decision-only in Phase P.3.
- Untargeted cover requests do not auto-assign a replacement.
- All request approval and shift reassignment actions are audit logged.

### Why

Cover approval is the safest next rota mutation after leave application because it changes one published shift from the requester to an accepted same-site target employee.

Keeping reassignment behind admin approval preserves the rule that employees cannot change rota directly.
