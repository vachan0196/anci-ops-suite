# ForecourtOS / Anci Ops Suite — Decisions Log

**Last updated:** 2026-05-13
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
**Updated:** Phase Q.2, 2026-05-09

### Current implementation

Frontend still stores access tokens in localStorage keys:

```text
forecourt_access_token
forecourt_employee_access_token
```

Phase Q.2 added a backend refresh/session foundation with hashed refresh tokens and HTTP-only refresh cookie support, but the frontend has not yet been migrated away from localStorage access-token storage.

### Why accepted temporarily

It allows local MVP preview and protected page testing quickly.

### Risk

localStorage token storage is not the intended production auth/session strategy.

### Revisit before

- external user testing,
- staging deployment,
- production deployment.

### Future direction

Move frontend auth to the Q.2 session foundation:

- short-lived access tokens,
- refresh token handling via HTTP-only cookies,
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

Through Phase P.4, `shift_requests` stores the requester `shift_id`, `target_employee_account_id`, and `target_shift_id`. Phase P must not apply a full two-way swap unless both shifts are present and validated.

Target acceptance changes the request workflow state only. It does not mutate rota.

Owner/Admin/Manager approval is still required before any swap request changes the rota.

### Rules

- Swap requests must remain tenant-scoped and site-scoped.
- Targeted employees can accept or decline the swap workflow.
- Target acceptance does not update shifts or rota.
- Target decline does not update shifts or rota.
- Admin rejection does not update shifts or rota.
- Full swap rota mutation is deferred until Phase P.5, after target shift selection and persistence are verified.
- Older one-shift reassignment semantics must not be treated as a full employee portal swap.

### Why

Older rows and older semantics may describe only "requester shift plus target employee." Applying a full swap without the target shift would create unsafe rota side effects and misleading audit history.

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
- Phase P.4 — swap target-shift modelling foundation.
- Phase P.5 — swap approval rota application only after target shift modelling is confirmed.

### Rules

- Phase P.0 is documentation and scoping only.
- Phase P.1 must expose only employee-safe same-site target information.
- Phase P.2 target actions must update request workflow state only.
- Phase P.3 may apply cover rota changes after target/admin rules are implemented.
- Phase P.4 adds explicit target-shift modelling and keeps swap approval decision-only.
- Phase P.5 may apply swap rota changes only after target-shift modelling is explicit and tested.
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

---

## D031 — True Swap Requires Explicit Target Shift Modelling

**Status:** Active
**Area:** Request workflow / swap rota safety
**Added:** Phase P.4

### Decision

True shift-for-shift swaps require explicit modelling of both the requester shift and the target employee shift.

Phase P.4 adds target shift selection/persistence but does not mutate rota.

### Why

Without target shift modelling, approving a swap would behave like cover rather than a true exchange.

To avoid unsafe or ambiguous rota changes, swap approval remains decision-only until both shifts are explicitly stored and validated.

### Rules

- Swap requests require requester shift, target employee, and target shift.
- Requester shift must belong to requester.
- Target shift must belong to target employee.
- Both shifts must be published, scheduled, same-site, and same-tenant.
- Target acceptance remains workflow-state only.
- Admin approval remains required before any swap rota mutation.
- Swap approval remains decision-only in Phase P.4 and applies safe assignment exchange from Phase P.5 onward.

---

## D032 — Target-Accepted Swap Approval Exchanges Both Shift Assignments

**Status:** Active
**Area:** Request workflow / swap rota application
**Added:** Phase P.5

### Decision

A target-accepted swap request can exchange the requester shift and target shift only after an authorised Owner/Admin/Manager approves it.

Target acceptance alone does not mutate rota.

Admin approval is the final authority that applies the swap.

### Why

A true swap requires both shifts to be explicitly modelled and validated.

Phase P.4 added target-shift modelling. Phase P.5 applies the safe mutation by exchanging assignments only after target acceptance and admin approval.

### Rules

- Only target-accepted swap requests can mutate rota.
- Requester shift must belong to requester.
- Target shift must belong to target employee.
- Both shifts must be published, scheduled, same-site, and same-tenant.
- Both shifts remain published and scheduled.
- Shift times are not changed.
- No duplicate shifts are created.
- No shifts are deleted.
- Employee accept/decline does not mutate rota.
- Admin approval applies the final swap.
- All request approval and shift reassignment actions are audit logged.

---

## D033 — Commercial SaaS Production Standard Before Phase Q

**Status:** Active
**Area:** Product quality / production readiness
**Added:** Pre-Q.0 documentation cleanup

### Decision

ForecourtOS / Anci Ops Suite is treated as a real commercial multi-tenant SaaS product, not a portfolio demo or disposable prototype.

Phase Q.0 starts commercial SaaS hardening. Until Q.0 work is explicitly implemented, documentation must distinguish current implementation from target production expectations.

### Why

The product already contains tenant-scoped operations, employee/admin token separation, rota mutation workflows, and approval/audit behavior. Future work must preserve that standard and avoid shortcuts that would be acceptable only in a prototype.

### Rules

- Backend remains the source of truth for permissions, workflow state, and rota mutation.
- Tenant isolation, site isolation, RBAC, deterministic errors, and auditability are production requirements.
- Frontend code must not invent permissions or persist operational truth in browser-only storage for production workflows.
- Prototype or temporary behavior must be labelled clearly and revisited before commercial rollout.
- New phases must include tests proportional to customer, data, security, and workflow risk.
- Phase Q.0 is documentation/planning/implementation hardening work only when explicitly started.

---

## D034 — Phase Q.2 Backend Refresh Session Foundation

**Status:** Active
**Area:** Authentication / session management
**Added:** Phase Q.2
**Updated:** Phase Q.2.1, 2026-05-10

### Decision

The current `/api/v1/auth/login` and `/api/v1/auth/employee/login` endpoints remain compatible and still return bearer access tokens. They now also create portal-aware backend refresh sessions and return a refresh token during the compatibility window.

Refresh tokens are stored only as SHA-256 hashes in `auth_sessions`. Sessions record `portal` as `admin` or `employee`, distinguish `user_id` from `employee_account_id`, and support refresh rotation and logout revocation through:

```text
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

The API also sets the refresh token in an HTTP-only cookie as additive migration support. Existing bearer-token-only API calls continue to work while the frontend is migrated.

Phase Q.2.1 keeps the 14-day refresh-token default and lowers the default access-token lifetime from 60 minutes to 15 minutes.

### Why

Commercial SaaS authentication needs a revocable server-side session foundation before the frontend can safely move away from localStorage token storage.

### Rules

- Store only hashes of refresh tokens.
- Do not log or echo refresh tokens in errors.
- Refresh sessions must be portal-aware.
- Admin refresh sessions must resolve to active admin/user identity.
- Employee refresh sessions must resolve to an active employee account with an active linked staff profile.
- Employee tokens cannot access admin APIs.
- Admin tokens cannot access employee-token-only APIs.
- Logout revokes refresh/session tokens where present but does not break legacy bearer-only clients during the migration window.
- Default access tokens should be short-lived; Q.2.1 uses a 15-minute default.
- Frontend localStorage token use remains temporary until the Q.3 cookie migration.

---

## D035 — LLM-Suggested Dependency Verification Policy

**Status:** Active
**Area:** Supply chain security / AI-assisted development
**Added:** Phase Q.2.2

### Decision

Any new dependency suggested by an LLM, coding agent, tutorial, blog post, or generated code must be verified before it is added to the repo.

This applies to:

- Python packages
- npm packages
- GitHub Actions
- Docker images
- AI/ML packages
- CLI tools used in CI/CD

### Rules

- Do not add a package only because an LLM suggested it.
- Verify the package exists on the official registry.
- Verify the package name exactly matches the intended library.
- Prefer official documentation over blog/tutorial snippets.
- Prefer mature, maintained, widely used packages.
- Check recent release history and maintainer credibility.
- Check for typosquatting/slopsquatting risk.
- Check package repository/homepage where available.
- Check license compatibility before commercial use.
- Do not install packages with install scripts or suspicious postinstall behaviour without review.
- Do not add new dependencies in security-sensitive phases unless necessary.
- Every new dependency must be justified in the phase summary.

### Required verification before merge

For Python:
- Package exists on PyPI.
- Package name matches official docs.
- Dependency is pinned or locked according to current project standard.
- `pip-audit` is run where practical.

For npm:
- Package exists on npm.
- Package name matches official docs.
- Install uses `npm ci` in CI.
- Lockfile changes are reviewed.
- Dependency age, downloads, maintainer, and repository are checked for unusual risk.

For GitHub Actions:
- Use pinned major versions at minimum.
- Prefer official or widely trusted actions.
- Avoid random untrusted actions.

### Why

AI coding agents can hallucinate package names. Attackers can register those hallucinated names and publish malicious packages. This is a commercial SaaS supply-chain risk.

### Future direction

Move toward stricter lockfile/hash-based installs and dependency approval automation before production deployment.

---

## D036 — Frontend Cookie Session Migration and CSRF Strategy

**Status:** Active
**Area:** Authentication / browser session security / CSRF / frontend auth migration
**Added:** Phase Q.3.0

### Scope

Phase Q.3.0 records the architecture decisions for the Q.3.1 frontend auth migration. It does not implement frontend auth migration, CSRF middleware, cookie-setting changes, endpoint changes, migrations, or tests.

Frontend localStorage token persistence remains temporary until Q.3.1. CSRF protection is mandatory before cookie-backed frontend auth is production-safe.

The correct legacy localStorage keys are:

```text
forecourt_access_token
forecourt_employee_access_token
```

The stale key name `employee_access_token` must not be used as an active key in Q.3.1 migration planning.

### Decision 1 — CSRF strategy

**Chosen option:** A. SameSite=Strict refresh cookie plus a required custom request header, `X-Requested-With: ForecourtOS`.

**Rejected options:** Double-submit cookie pattern, synchronizer token pattern with server-side state, and a combined token pattern are rejected for Q.3.1.

**Rationale:** The MVP production target is same-origin Next.js + FastAPI behind one app origin. SameSite=Strict blocks ordinary cross-site form/image/navigation CSRF attempts, and the custom header forces browser clients through CORS/preflight rules instead of allowing simple cross-site requests. This is strong enough for the current same-origin session model without adding a second CSRF token store before the frontend migration.

**Assumptions:** Admin Portal, Employee Portal, and API are served from the same origin or through an equivalent reverse-proxy path in production. Local development may use separate localhost ports, but Q.3.1 should keep CORS narrow and explicitly include credentials only for approved local origins.

**Refresh endpoint:** `POST /api/v1/auth/refresh` must require the CSRF/custom header when using the cookie-backed flow because it consumes the HTTP-only refresh cookie and issues new access credentials.

**Admin and employee portals:** The same CSRF rule applies to both portals. Portal separation remains enforced by the backend session portal and frontend routing, not by separate CSRF strategies.

**Q.3.1 implementation implication:** Add CSRF enforcement for cookie-backed browser auth requests and make both portals send the required custom header on refresh, logout, and authenticated state-changing API calls.

### Decision 2 — Cookie attribute values

**Chosen option:** Q.3.1 should use one HTTP-only refresh cookie with exact-origin scoping.

| Attribute | Production value | Local development behaviour | Reason |
|---|---|---|---|
| `HttpOnly` | `true` | `true` | JavaScript must not read refresh tokens. |
| `Secure` | `true` | `false` only for non-HTTPS localhost | Production cookies must require HTTPS; local HTTP development needs a practical exception. |
| `SameSite` | `Strict` | `Strict` where browser/local setup permits | The chosen MVP deployment is same-origin, so cross-site cookie sending is unnecessary. |
| `Path` | `/api/v1/auth` | `/api/v1/auth` | Refresh and logout are auth endpoints; path scoping reduces unnecessary cookie exposure to unrelated API paths. |
| `Domain` | omitted | omitted | Host-only cookies avoid cross-subdomain session sharing and simplify tenant/session boundaries. |
| `Max-Age` | tied to `REFRESH_TOKEN_EXPIRE_DAYS`, currently 14 days | same configured TTL | Cookie lifetime should not outlive the server-side refresh/session lifetime. |

**Rejected options:** Wider cookie path, explicit parent domain, non-HTTP-only refresh cookie, and production `Secure=false` are rejected.

**Rationale:** The refresh cookie is a bearer-equivalent secret. Host-only, HTTP-only, secure, Strict cookies match the same-origin MVP deployment and avoid cross-subdomain complexity.

**Q.3.1 implementation implication:** Align cookie-setting and clearing behaviour to these attributes while preserving the configured refresh token TTL.

### Decision 3 — Access token storage strategy

**Chosen option:** A. Access tokens are stored in memory only, using frontend auth state.

**Rejected options:** `sessionStorage` and cookie-based access tokens are rejected.

**Rationale:** Access tokens are short-lived and should not be persisted in browser storage. `sessionStorage` still exposes tokens to XSS. Cookie-based access tokens would increase CSRF exposure across the full API surface and duplicate the refresh-cookie model.

**Page reload behaviour:** A reload loses the in-memory access token. The frontend should show a brief loading/session-check state, call `/api/v1/auth/refresh` with the refresh cookie, and restore the in-memory access token if the refresh succeeds.

**localStorage after Q.3:** Access tokens may not be persisted in localStorage after Q.3.1. The current localStorage behaviour remains temporary only until the migration ships.

**Q.3.1 implementation implication:** Replace active frontend dependency on localStorage access tokens with memory-backed auth state restored from the refresh cookie.

### Decision 4 — Bearer-token deprecation timeline

**Chosen option:** Use a short 30/60/90 day migration clock after Q.3.1 ships.

1. 30 days after Q.3.1 ships: log deprecation warnings for legacy bearer-only browser usage.
2. 60 days after Q.3.1 ships: stop issuing and using bearer tokens in normal frontend browser login flows.
3. 90 days after Q.3.1 ships: remove legacy browser bearer compatibility or restrict bearer auth to internal, development, or documented API-client use only.

**Rejected options:** An indefinite compatibility window and immediate bearer removal are rejected.

**Rationale:** There are no paying customers yet, so a long browser compatibility period is unnecessary. Immediate removal would make Q.3.1 harder to verify and roll back. The 30/60/90 schedule gives enough time to observe migration issues while keeping localStorage bearer risk temporary.

**Q.3.1 implementation implication:** Implement the cookie/session migration so the frontend no longer relies on bearer persistence, then track the deprecation milestones in follow-up hardening work.

### Decision 5 — In-flight localStorage migration approach

**Chosen option:** A. Force re-login on first load after Q.3.1 by clearing old localStorage keys and redirecting to the correct login page.

**Rejected options:** Silent bearer-to-cookie swap and parallel coexistence until token expiry are rejected.

**Rationale:** Silent migration would extend trust in tokens stored in localStorage and add edge cases around wrong-portal or stale sessions. Parallel coexistence would keep the risky storage model alive after the migration. A forced re-login is acceptable before paying customers and gives a clean boundary for the new session model.

**Local dev/staging impact:** Developers and staging testers will be logged out once after Q.3.1 and must sign in again. That is acceptable for a security migration.

**Exact legacy keys to clear:**

```text
forecourt_access_token
forecourt_employee_access_token
```

`employee_access_token` is a stale key name and must not be treated as an active key.

**Q.3.1 implementation implication:** Clear the real legacy keys on migration boundary and route users to the correct admin or employee login flow.

### Decision 6 — Refresh-on-401 strategy

**Chosen option:** The frontend api-client should auto-refresh once after a 401, then retry the original request once if refresh succeeds.

**Rejected options:** No automatic refresh, unlimited retries, and independent refresh attempts for every parallel 401 are rejected.

**Rationale:** A single refresh-and-retry keeps normal short-lived access-token expiry unobtrusive without creating infinite loops or request storms. Parallel 401s should share one in-flight refresh attempt so multiple expired requests do not rotate the same refresh session concurrently.

**Failure behaviour:** If refresh fails, the frontend clears in-memory auth state and routes the user to the correct login page. The refresh request must use `credentials: "include"` and include the required CSRF/custom header.

**Admin and employee portals:** This applies to both portals with portal-aware routing and session restoration.

**Q.3.1 implementation implication:** Build the shared refresh-on-401 behaviour in the frontend api-client as prose-specified here, without allowing infinite retry loops.

### Decision 7 — Logout scope

**Chosen option:** A. Single-session logout only using existing `POST /api/v1/auth/logout`.

**Rejected options:** Shipping both single-session and all-sessions logout in Q.3.1, or only all-sessions logout, are rejected.

**Rationale:** Q.3.1 should focus on safely migrating the browser session model and CSRF protection. The existing logout endpoint already revokes the current refresh/session token and clears the refresh cookie. All-sessions logout is valuable, but it is separate account-security scope.

**`/auth/logout-all`:** A logout-all endpoint is needed later, not in Q.3.1 unless a future phase explicitly reprioritises it.

**Admin and employee sessions:** Logout applies to the current portal session. Admin and employee sessions remain separately represented by portal-aware refresh sessions.

**Audit implications:** Single-session logout should be audit-logged when auth/session audit logging is implemented. Logout-all will need explicit audit records for the actor, scope, and affected sessions.

**Q.3.1 implementation implication:** Use the existing logout endpoint for current-session logout and track all-sessions logout as follow-up hardening.

### Decision 8 — Same-origin vs subdomain deployment

**Chosen option:** A. Same-origin production deployment for the MVP.

Production target:

```text
https://app.forecourtos.com
```

Admin Portal, Employee Portal, and API should be served under the same origin where practical, with the API path-proxied under the app origin.

**Rejected options:** A subdomain split and hybrid transition model are rejected for the MVP session migration.

**Rationale:** Same-origin deployment keeps cookies host-only, keeps `SameSite=Strict` viable, reduces CORS surface area, and avoids cross-subdomain session-sharing decisions before they are necessary.

**Local development:** Local development may continue to use separate frontend/API ports, but it should be treated as an explicit development exception with narrow CORS and credential settings.

**Cookie domain:** `Domain` should be omitted so the refresh cookie is host-only.

**CORS:** Production same-origin traffic should not need broad CORS. Any local or staging cross-origin allowances must be explicit and limited.

**CSRF:** Same-origin plus `SameSite=Strict` plus a required custom header is the chosen CSRF posture for Q.3.1.

**Vercel/AWS implications:** Vercel can serve the Next.js app while routing API requests through rewrites or a reverse proxy where practical. AWS deployment can use an ALB, API gateway, or reverse proxy to keep the browser-facing origin unified. Cross-subdomain admin/staff/API separation remains a later deployment decision if product scale requires it.

**Q.3.1 implementation implication:** Implement the frontend auth migration assuming a same-origin production target and avoid adding cross-subdomain cookie assumptions.

### Q.3.1 implementation note

Phase Q.3.1 implemented D036 for the current browser auth surface: cookie-backed refresh/logout now requires `X-Requested-With: ForecourtOS` when the HTTP-only refresh cookie is used, the refresh cookie is `HttpOnly`, SameSite=Strict, scoped to `/api/v1/auth`, and host-only, and the frontend stores active access tokens in memory only. The legacy localStorage keys `forecourt_access_token` and `forecourt_employee_access_token` are cleared during migration/login/logout paths. Existing bearer-token compatibility remains in place during the D036 deprecation window. H062 tracks the completed frontend auth cookie/session migration; H058 remains the open password reset flow.

---

## D037 — Auth Security Event Storage and Vocabulary

**Status:** Active
**Area:** Authentication / security audit / incident response / UK GDPR
**Added:** Phase Q.3.2.1

### Decision

Auth/session lifecycle and auth security events must be stored in a dedicated `auth_security_events` table rather than the existing `audit_logs` table.

The existing `audit_logs` table remains the business-action audit log for tenant/user-scoped operational actions. It requires non-null `tenant_id` and `user_id`, which is correct for normal business audit events but unsafe for unresolved auth/security events. Auth/security events may occur before any tenant, user, employee account, or auth session can be resolved, so fake tenant/user values must not be written.

### Table Shape

`auth_security_events` supports:

```text
id
created_at
event_type
rejection_reason nullable
portal nullable
tenant_id nullable
user_id nullable
employee_account_id nullable
auth_session_id nullable
request_id nullable
ip_address nullable
user_agent nullable
metadata_json nullable
```

Foreign keys are nullable because unresolved security events are valid.

### Event Vocabulary

Use these exact `event_type` values:

```text
auth.session.issued
auth.session.rotated
auth.session.revoked
auth.session.rejected
auth.session.blocked_disabled_admin
auth.session.blocked_disabled_employee
auth.session.blocked_inactive_staff_profile
```

For `auth.session.rejected`, use only these exact `rejection_reason` values:

```text
invalid
revoked
expired
wrong_portal
missing_csrf_header
```

### PII Decision

`ip_address` is stored as a raw nullable value for auth/security events.

Retention is 365 days. The lawful basis is legitimate interest for security monitoring, abuse detection, incident response, and account/session compromise investigation. Raw IP storage is chosen because hashed IPs reduce the ability to correlate incidents with infrastructure logs, abuse patterns, support reports, and security timelines.

`user_agent` is stored as a raw nullable value for auth/security events.

Retention is 365 days. The lawful basis is legitimate interest for security monitoring, suspicious session investigation, and distinguishing device/browser patterns during incidents.

This is a new personal-data processing decision under UK GDPR. The privacy notice must reflect this collection before commercial launch.

### Metadata Rules

`metadata_json` may contain only safe non-secret context.

Allowed examples:

```text
rejection reason context strings
numeric counters and timing data
non-identifying error categories
safe implementation flags such as cookie_backed=true
```

Forbidden under all circumstances:

```text
raw refresh tokens
raw access tokens
hashed token values
cookie values
password values
Authorization header contents
email addresses
secret material
anything that uniquely identifies a person and is not already in a structured column
```

Use `user_id`, `employee_account_id`, `tenant_id`, and `auth_session_id` structured columns instead of putting identifiers into metadata.

### Indexing

Initial indexes support incident-response queries:

```text
tenant_id + created_at
user_id + created_at
employee_account_id + created_at
event_type + rejection_reason + created_at
ip_address + created_at
auth_session_id
```

The `auth_session_id` index is included in Q.3.2.1 because session drill-down is a natural incident-response query and the index is narrow.

### Retention

All auth security events are retained for 365 days initially, including successful issued/rotated/revoked events and rejected/blocked events.

Retention enforcement is deferred to a later operational phase. The 365-day retention expectation is active now; implementation may later use a scheduled cleanup job, partitioning, or another production-appropriate retention mechanism.

### Out of Scope

H066 refresh-token reuse detection and session-family handling remains out of scope for Q.3.2.1 and belongs to Q.3.3.
