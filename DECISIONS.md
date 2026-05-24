
---

# 🧠 `DECISIONS.md` — ForecourtOS / Anci Ops Suite Decisions Log

**Last updated:** 2026-05-17
**Purpose:** Record deliberate product/technical decisions, especially where current implementation diverges from PRDs. Future AI agents must read this before modifying auth, onboarding, company/site/staff setup, or persistence.

---

## Decision Status Legend

| Badge                 | Meaning                                   |
| --------------------- | ----------------------------------------- |
| Active                | Current project decision to follow        |
| Temporary             | Accepted for MVP speed, must be revisited |
| Resolved / Historical | No longer active, kept for context        |
| Target                | Future desired state                      |
| Needs decision        | Not settled yet                           |

---

# 🔐 AUTH & IDENTITY

---

## D001 — Register Contract Differs From API PRD

**Status:** Temporary
**Area:** Auth / onboarding
**Date recorded:** 2026-04-26

### Current implementation

```json
POST /api/v1/auth/register
{
  "full_name": "string",
  "email": "string",
  "password": "string"
}
```

### PRD target

```json
{
  "full_name": "string",
  "work_email": "string",
  "password": "string",
  "confirm_password": "string",
  "accepted_terms": true
}
```

### Why accepted

Simpler endpoint unblocked frontend development.

### Risk

Future agents may build against PRD and break working contract.

### Future direction

* Add confirm password
* Add terms acceptance
* Add email verification
* Align naming (`work_email`)

---

## D002 — Login Uses `/auth/login` Instead of `/auth/admin/login`

**Status:** Temporary
**Area:** Auth

### Current

```text
POST /api/v1/auth/login (form-based)
```

### PRD target

```text
POST /api/v1/auth/admin/login (JSON)
```

### Decision

Keep current OAuth2 flow for now.

### Future direction

Add `/auth/admin/login` wrapper OR migrate fully later.

---

## D003 — `/auth/me` Hybrid Response (Admin + Employee)

**Status:** Active
**Area:** Auth/session
**Updated:** Phase K.1 (2026-04-29)

### Current implementation

Supports BOTH:

### Admin token

```json
{
  "id": "uuid",
  "email": "string",
  "active_tenant_id": "uuid",
  "active_tenant_role": "admin"
}
```

### Employee token

```json
{
  "portal": "employee",
  "employee_account_id": "uuid",
  "tenant_id": "uuid",
  "site_id": "uuid",
  "display_name": "string"
}
```

### Decision

* Keep backward compatibility
* Support dual-token resolution in `/auth/me`
* Maintain `/auth/employee/me`

### Why

* Avoid breaking admin portal
* Align with PRD direction
* Enable shared session handling

### Future direction

Standardise response:

```json
{
  "portal": "admin|employee",
  "tenant_id": "...",
  "role": "...",
  "site_id": "...",
  "user_id": "..."
}
```

---

## D004 — First User Role (Admin vs Owner)

**Status:** Active
**Area:** Roles

### Current implementation after Phase Q.4.4

First tenant user = `owner`.

The implemented tenant membership role set is:

```text
owner | admin | member
```

`owner` inherits all current `admin` permissions. Admin-capable backend dependencies treat `owner` and `admin` as admin-side privileged roles. `member` remains in the tenant membership role set for current staff-profile compatibility, but Phase R.2d blocks `member` from obtaining or refreshing Admin Portal sessions.

Existing tenants are backfilled to exactly one owner where missing. The backfill selects the earliest admin membership by the associated user's `created_at`, then membership `id`; if no admin exists, it selects the earliest tenant membership by the same ordering. The current `tenant_users` table has no `created_at`, so `users.created_at` is the available deterministic timestamp. Tenants with no `tenant_users` are skipped and may require manual remediation.

### Future direction

The future target remains:

```text
owner > admin > manager > employee
```

Employee identity remains separate and site-scoped. Full `manager` tenant-role behavior, owner-only governance, owner transfer/promotion/demotion workflows, and mandatory 2FA or step-up enforcement are deferred to Q.5/Q.5.2. No frontend role-management UI was added in Q.4.4.

### Phase Q.4.4 implementation note

Phase Q.4.4 resolved the owner/admin prerequisite before 2FA by creating new first tenant users as `owner`, adding an owner backfill migration, updating admin-capable RBAC to include `owner`, and preserving existing admin/member compatibility.

---

## D041 — Member Tenant Role Is Not Admin Portal Access

**Status:** Active
**Area:** Auth / RBAC / staff identity
**Date recorded:** Phase R.2d

### Decision

`member` tenant memberships are not valid Admin Portal access roles.

Current staff setup may still create a `users` row and `tenant_users.role = "member"` because `staff_profiles.user_id` is required by the existing schema. That record is a temporary staff identity bridge, not permission to enter the Admin Portal.

Only current admin-side privileged tenant roles may obtain or continue Admin Portal sessions:

```text
owner | admin
```

The future `manager` role remains a target role and is not implemented in the current backend tenant-role set.

### Implementation note — Phase R.2d

Phase R.2d added an admin-auth-specific guard to block `member` admin session/token issuance through admin login, admin refresh, 2FA challenge verification, and 2FA step-up. The guard is not placed in shared token creation utilities, so employee portal login through `employee_accounts` remains separate and unchanged.

Company profile read/update is owner-only as defense-in-depth.

### Future direction

Decouple normal staff/employee creation from admin-auth `users` where practical, or keep the bridge explicitly documented until `staff_profiles.user_id` is redesigned.

---

# 🏢 SETUP & PERSISTENCE

---

## D005 — Company Setup Uses localStorage (RESOLVED)

**Status:** Resolved / Historical

### Update

Phase D/E:

```text
Company profile now persisted in backend
```

### Note

This decision remains for historical context only.

### Phase R.0 Frontend Note

Phase R.0 aligned the admin Company Setup/Profile frontend with the backend company profile contract. The page loads and saves through `GET /api/v1/company/profile` and `PATCH /api/v1/company/profile`; company profile/setup truth is not persisted in browser `localStorage`.

---

## D006 — Site Setup Uses localStorage (RESOLVED)

**Status:** Resolved / Historical

### Update

Phase F / F.1:

* Store created via backend
* Opening hours persisted
* Staff persistence connected
* Employee accounts created during staff setup

### Phase R.1 Frontend Note

Phase R.1 confirmed the current normal site setup target is the backend `/api/v1/stores` API family. `/api/v1/sites` currently serves site-scoped rota/request/shift workflows. The obsolete `forecourt_first_site` localStorage helper was removed so first-site setup state is no longer persisted as browser-only truth.

---

## D007 — Staff Setup Lives Inside Site Setup

**Status:** Active

### Decision

Staff creation is part of site setup.

### Why

Staff must belong to a site.

---

## D008 — Sensitive Staff Data NOT Stored in localStorage

**Status:** Active

### Never store:

```text
NI numbers
passport/BRP
documents
passwords
```

### Decision

UI-only until secure backend implemented.

---

## D009 — Staff Creation Requires Multi-Step Backend Flow

**Status:** Active

### Current

```text
create user → create staff → assign role
```

### Decision

Keep current flow.

### Future direction

Introduce setup wizard endpoint.

---

## D010 — Frontend Auth Token Uses localStorage Temporarily

**Status:** Resolved / Historical
**Area:** Auth/session frontend
**Date recorded:** 2026-04-26
**Updated:** Phase Q.3.1, 2026-05-11

### Current implementation

Frontend active access tokens no longer depend on localStorage after Phase Q.3.1.

Active access tokens are held in memory only and restored through the Q.2 backend refresh/session foundation.

The legacy localStorage keys below are cleared during migration, login, and logout paths:

```text
forecourt_access_token
forecourt_employee_access_token
```

The stale key name below must not be treated as an active key:

employee_access_token

Phase Q.2 added a backend refresh/session foundation with hashed refresh/session tokens, refresh rotation, logout revocation, and HTTP-only refresh cookie support.

Phase Q.2.1 lowered the default access-token lifetime from 60 minutes to 15 minutes.

Phase Q.3.0 chose the frontend cookie/session and CSRF migration strategy in D036.

Phase Q.3.1 implemented the frontend cookie/session migration and CSRF protection for cookie-backed refresh/logout.

## Why this is resolved

The temporary frontend localStorage access-token dependency has been removed as an active auth mechanism.

## Remaining compatibility

Legacy keys may still appear in code only for cleanup/removal purposes.

Bearer-token compatibility remains during the D036 deprecation window, but browser auth no longer actively relies on localStorage access-token persistence.

## Future direction

Continue the D036 deprecation path:

keep access tokens in memory only
keep refresh tokens in HTTP-only cookies
keep CSRF protection for cookie-backed refresh/logout
preserve admin/employee portal separation
later restrict or remove legacy bearer compatibility according to D036/H069

---

## D011 — Dashboard Setup Uses Backend Readiness (RESOLVED)

**Status:** Resolved / Historical

### Update

Phase G:

```text
Dashboard now uses backend readiness
```

---

## D012 — No More UI Built on localStorage

**Status:** Active

### Decision

Do NOT build:

```text
rota
staff directory
reports
employee workflows
```

on localStorage.

---

## D013 — PRDs Are Target, Not Reality

**Status:** Active

### Rule

Always read in order:

```text
IMPLEMENTATION_STATUS.md → DECISIONS.md → PRD
```

---

## D014 — CORS Format for Docker

**Status:** Active

```yaml
CORS_ORIGINS: '["http://localhost:3000"]'
```

---

# 🧑‍💼 EMPLOYEE SYSTEM (NEW — PHASE K & K.1)

---

## D015 — Employee Accounts Are Site-Scoped Identity

**Status:** Active
**Added:** Phase K

### Decision

Employee login uses:

```text
site_id + username + password
```

### Rules

* username unique per site
* no email login
* no Google login

---

## D016 — Staff ↔ Employee Account Mapping Is Mandatory

**Status:** Active
**Added:** Phase K.1

### Rules

```text
1 staff → 1 employee account
1 employee account → 1 staff
```

### Enforced

* employee must link to active staff
* no orphan accounts
* no duplicate accounts

---

## D017 — Employee Token Cannot Access Admin APIs

**Status:** Active
**Added:** Phase K

### Decision

Strict separation:

```text
employee token ❌ admin APIs
admin token ❌ employee APIs
```

---

## D018 — Employee Sees Published Rota Only

**Status:** Active
**Added:** Phase K

### Rules

Employee can see:

```text
own shifts only
published only
```

Employee cannot see:

```text
draft shifts
co-worker data
admin tools
```

---

## D019 — Rota Must Be Published Before Employee Visibility

**Status:** Active
**Added:** Phase J

### Flow

```text
draft → edit → publish → employee sees
```

---

## D020 — Cancelled Shifts Are Excluded From Rota

**Status:** Active
**Added:** Phase I.4

### Decision

Cancelled shifts:

```text
- soft deleted
- not shown in rota
- not publishable
```

---

## D021 — Employee Login Requires Active Staff Link

**Status:** Active
**Added:** Phase K.1

### Decision

Employee login fails if:

```text
- no linked staff profile
- inactive staff profile
```

---
## D022 — Store → Site Naming Migration

Status: Active

Current backend uses "store".
Product standard is "site".

Rules:
- All NEW endpoints MUST use /sites
- /stores endpoints are legacy
- Migration will happen later (no breaking change now)

Risk:
AI agents may duplicate endpoints if unclear.

Enforcement:
Always follow README naming rule.

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

Through Phase P.4, `shift_requests` stores the requester `shift_id`, `target_employee_account_id`, and `target_shift_id`.

Phase P.5 applies the full swap only when requester shift, target employee, and target shift are present, validated, and target-accepted.

Phase P must not fake a full two-way swap without explicit target-shift modelling.

Target acceptance changes the request workflow state only. It does not mutate rota.

Owner/Admin/Manager approval is still required before any swap request changes the rota.

### Rules

- Swap requests must remain tenant-scoped and site-scoped.
- Targeted employees can accept or decline the swap workflow.
- Target acceptance does not update shifts or rota.
- Target decline does not update shifts or rota.
- Admin rejection does not update shifts or rota.
- Full swap rota mutation is allowed only through the Phase P.5 target-accepted swap approval flow.
- Older one-shift reassignment semantics must not be treated as a full employee portal swap.

### Why

Earlier swap semantics could describe only "requester shift plus target employee." Phase P.4 added explicit target-shift modelling, and Phase P.5 made safe swap rota mutation possible only after requester shift, target employee, target shift, target acceptance, and admin approval are all validated.

---

## D029 — Phase P Implementation Breakdown

**Status:** Active
**Area:** Request workflow / phase planning
**Added:** Phase P.0

### Decision

Phase P is split into smaller safe phases:

- Phase P.0 — workflow scoping and decisions.
- Phase P.1 — employee-safe same-site co-worker/target list.
- Phase P.2 — target accept/decline workflow.
- Phase P.3 — cover approval rota application.
- Phase P.4 — swap target-shift modelling foundation.
- Phase P.5 — swap approval rota application.

### Rules

- Phase P.0 is documentation and scoping only.
- Phase P.1 must expose only employee-safe same-site target information.
- Phase P.2 target actions must update request workflow state only.
- Phase P.3 may apply cover rota changes after target/admin rules are implemented.
- Phase P.4 adds explicit target-shift modelling and keeps swap approval decision-only.
- Phase P.5 applies swap rota changes only after target-shift modelling is explicit, target acceptance is complete, and admin approval is given.
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
- Swap approval remained decision-only in Phase P.4 and applies safe assignment exchange from Phase P.5 onward.

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

## D033 — Commercial SaaS Production Standard

**Status:** Active
**Area:** Product quality / production readiness
**Added:** Pre-Q.0 documentation cleanup

### Decision

ForecourtOS / Anci Ops Suite is treated as a real commercial multi-tenant SaaS product, not a portfolio demo or disposable prototype.

Phase Q has started the commercial SaaS hardening track. All future product, security, observability, billing, AI, and operational work must be judged against the standard of a paying UK business customer using the system with real employee data and real rota/pay implications.

### Why

The product contains tenant-scoped operations, employee/admin token separation, rota mutation workflows, approval flows, audit behaviour, and commercial hardening foundations.

Future work must preserve that standard and avoid shortcuts that would be acceptable only in a prototype.

### Rules

- Backend remains the source of truth for permissions, workflow state, and rota mutation.
- Tenant isolation, site isolation, RBAC, deterministic errors, and auditability are production requirements.
- Frontend code must not invent permissions or persist operational truth in browser-only storage for production workflows.
- Prototype or temporary behaviour must be labelled clearly and revisited before commercial rollout.
- New phases must include tests proportional to customer, data, security, and workflow risk.
- Hardening work is product-critical and must not be treated as optional cleanup.

---

## D034 — Phase Q.2 Backend Refresh Session Foundation

**Status:** Active
**Area:** Authentication / session management
**Added:** Phase Q.2
**Updated:** Phase Q.3.1, 2026-05-11

### Decision

The current `/api/v1/auth/login` and `/api/v1/auth/employee/login` endpoints remain compatible and still return bearer access tokens. They also create portal-aware backend refresh sessions and return a refresh token where the compatibility contract requires it.

Refresh/session tokens are stored only as hashes in `auth_sessions`.

Sessions record the portal type as either:

```text
admin
employee
```

Sessions distinguish admin users from employee accounts by using the correct identity fields:

user_id
employee_account_id

Phase Q.2 added:

POST /api/v1/auth/refresh
POST /api/v1/auth/logout

The API supports an HTTP-only refresh cookie for browser session restoration.

Phase Q.2.1 lowered the default access-token lifetime from 60 minutes to 15 minutes.

Phase Q.3.1 implemented the frontend migration to cookie-backed refresh, memory-only active access tokens, and CSRF/header enforcement for cookie-backed refresh/logout.

## Why

Commercial SaaS authentication needs a revocable server-side session foundation before the frontend can safely move away from localStorage token storage.

Shorter-lived access tokens reduce the risk window when access tokens are exposed or stale, while refresh sessions provide controlled renewal, rotation, and revocation.

## Rules
- Store only hashes of refresh/session tokens.
- Do not log refresh tokens.
- Do not echo refresh tokens in errors.
- Refresh sessions must be portal-aware.
- Admin refresh sessions must resolve to an active admin/user identity.
- Employee refresh sessions must resolve to an active employee account with an active linked staff profile.
- Employee tokens cannot access admin APIs.
- Admin tokens cannot access employee-token-only APIs.
- Logout revokes refresh/session tokens where present.
- Bearer-token compatibility remains during the D036 migration/deprecation window.
- Browser frontend auth must use memory-only active access tokens after Q.3.1.
- Cookie-backed refresh/logout must require X-Requested-With: ForecourtOS.

## Known follow-up hardening
- H065 tracks audit logging for auth/session lifecycle events.
- H066 tracks refresh token reuse detection / session family hardening.
- H067 tracks all-sessions logout / logout-all.
- H069 tracks bearer-token deprecation/removal after migration.

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

- package exists on PyPI
- package name matches official docs
- dependency is pinned or locked according to current project standard
- `pip-audit` is run where practical

For npm:

- package exists on npm
- package name matches official docs
- install uses `npm ci` in CI
- lockfile changes are reviewed
- dependency age, downloads, maintainer, and repository are checked for unusual risk

For GitHub Actions:

- use pinned major versions at minimum
- prefer official or widely trusted actions
- avoid random untrusted actions

### Why

AI coding agents can hallucinate package names. Attackers can register those hallucinated names and publish malicious packages. This is a commercial SaaS supply-chain risk.

### Future direction

Move toward stricter lockfile/hash-based installs and dependency approval automation before production deployment.

---
## D036 — Frontend Cookie Session Migration and CSRF Strategy

**Status:** Active
**Area:** Authentication / browser session security / CSRF / frontend auth migration
**Added:** Phase Q.3.0
**Implemented:** Phase Q.3.1, 2026-05-11

### Decision

Phase Q.3.0 defined the browser-session, cookie, CSRF, localStorage migration, refresh, logout, bearer-token deprecation, and deployment strategy.

Phase Q.3.1 implemented the current browser-auth migration for the existing frontend surface.

Frontend active access tokens are now memory-only.

Legacy localStorage keys are cleared during migration, login, and logout paths:

```text
forecourt_access_token
forecourt_employee_access_token
```

The stale key below must not be used as an active key:

employee_access_token

Cookie-backed refresh/logout now requires:

X-Requested-With: ForecourtOS

Bearer-token compatibility remains during the D036 deprecation window.

## Decision 1 — CSRF strategy

Chosen option: SameSite=Strict refresh cookie plus a required custom request header.

The chosen custom header is:

X-Requested-With: ForecourtOS

Cookie-backed refresh/logout must require the CSRF/custom header.

## Rejected options:

- Double-submit cookie pattern.
- Synchronizer token pattern with server-side state.
- Combined approach for MVP.

## Rationale:

For MVP production, ForecourtOS should use same-origin deployment where the Admin Portal, Employee Portal, and API are served from the same origin. In that setup, SameSite=Strict blocks normal cross-site cookie submission, while a required custom request header blocks simple cross-site form/image/script CSRF attempts.

This is simpler than a synchronizer-token system and avoids extra server-side CSRF-token state during the MVP migration.

## Q.3.1 implementation result:

Q.3.1 implemented header enforcement for cookie-backed /api/v1/auth/refresh and /api/v1/auth/logout. Body refresh-token compatibility and unrelated bearer-protected endpoints remain ungated by this CSRF header.

## Decision 2 — Cookie attribute values

Chosen option: Use strict, host-scoped HTTP-only refresh cookies.

Refresh-cookie attributes:

HttpOnly=true
Secure=true in production
SameSite=Strict
Path=/api/v1/auth
Domain omitted
Max-Age tied to REFRESH_TOKEN_EXPIRE_DAYS

Local development may use Secure=false only where HTTPS is not available locally.

## Rejected options:

- SameSite=None is rejected for MVP because it requires cross-site cookie behaviour and increases CSRF complexity.
- A broad cookie domain is rejected for MVP.
- Storing refresh cookies across subdomains is rejected for MVP.

## Rationale:

Omitting Domain keeps the cookie bound to the exact host. Path=/api/v1/auth limits refresh-cookie transmission to auth endpoints. HttpOnly prevents JavaScript from reading the refresh token. Secure=true is required in production.

## Q.3.1 implementation result:

Q.3.1 aligned refresh cookie behaviour with these attributes while preserving local development compatibility.

## Decision 3 — Access token storage strategy

Chosen option: In-memory access-token storage only.

Access tokens must not be persisted in:

localStorage
sessionStorage
non-HttpOnly cookies

## Rejected options:

- sessionStorage is rejected because it remains JavaScript-readable.
- Cookie-based access tokens are rejected because they increase CSRF surface and blur the refresh/access-token separation.

## Rationale:

The refresh token belongs in an HTTP-only cookie. The access token should be short-lived and held only in memory. On page reload, the frontend should call /api/v1/auth/refresh with cookie credentials and show a brief session-loading state.

## Q.3.1 implementation result:

Q.3.1 moved Admin Portal and Employee Portal active auth state to memory-only access tokens restored through /api/v1/auth/refresh.

## Decision 4 — Bearer-token deprecation timeline

Chosen option: 30/60/90-day deprecation path after Q.3.1.

Timeline:

30 days: log deprecation warnings for legacy bearer-only browser usage
60 days: normal browser login flows stop actively relying on bearer-token persistence
90 days: bearer compatibility is removed or restricted to explicit internal/dev/API-client use

## Rejected options:

- Immediate removal is rejected because it risks breaking development and compatibility checks.
- Long indefinite compatibility is rejected because there are no paying customers yet and the localStorage risk should not remain open.

## Rationale:

A 30/60/90-day timeline provides a controlled migration window without allowing the temporary bearer/localStorage model to become permanent.

## Q.3.1 implementation result:

Q.3.1 implemented the new frontend path while preserving bearer compatibility during the deprecation window. H069 tracks follow-up bearer-token deprecation/removal.

## Decision 5 — In-flight localStorage migration approach

Chosen option: Force re-login / session restoration through refresh cookie and clear legacy localStorage keys.

Legacy keys to clear:

forecourt_access_token
forecourt_employee_access_token

The stale key below must not be used as an active key:

employee_access_token

## Rejected options:

- Silent bearer-to-cookie migration is rejected because it extends reliance on the old browser-token model.
- Parallel coexistence until token expiry is rejected because it leaves XSS-accessible tokens in place.

## Rationale:

There are no paying customers yet. Clearing legacy keys and restoring sessions through the refresh cookie is safer, simpler, and easier to reason about than a silent bearer-token migration path.

## Q.3.1 implementation result:

Q.3.1 clears the correct legacy keys during migration/login/logout paths and no longer actively reads them as auth-token sources.

## Decision 6 — Refresh-on-401 strategy

Chosen option: The frontend API client auto-refreshes once after a 401, then retries the original request once.

## Behaviour:

API request receives 401.
If the request has not already retried, call /api/v1/auth/refresh.
Use credentials: "include".
Include X-Requested-With: ForecourtOS.
Parallel 401 responses share one in-flight refresh attempt.
If refresh succeeds, retry the original request once.
If refresh fails, clear in-memory auth state and route the user to the correct login page.
Do not infinite-loop on refresh failure.
Apply consistently to Admin Portal and Employee Portal with portal-aware routing.

## Rejected options:

No auto-refresh is rejected because it creates poor UX with short-lived access tokens.
Unlimited retry loops are rejected as unsafe.
Separate inconsistent admin/employee refresh behaviour is rejected.

## Rationale:

Short-lived access tokens require a safe refresh path. A single retry with a shared in-flight refresh attempt prevents request storms and avoids infinite loops.

## Q.3.1 implementation result:

Q.3.1 updated the frontend API client to use this refresh-on-401 strategy without exposing refresh tokens to JavaScript.

## Decision 7 — Logout scope

Chosen option: Use existing single-session logout and track all-sessions logout separately.

Q.3.1 uses:

POST /api/v1/auth/logout

All-sessions logout remains a future hardening item.

## Rejected options:

Only all-sessions logout is rejected because it is heavier than needed for the immediate browser migration.
Implementing both in Q.3.1 is rejected because /auth/logout-all is separate future hardening.

## Rationale:

Single-session logout already matches the Q.2 backend foundation. It is enough for the localStorage-to-cookie migration. All-sessions logout is valuable but can be implemented as a later hardening phase.

## Q.3.1 implementation result:

Q.3.1 wired frontend logout to the existing logout endpoint and clears local in-memory auth state plus legacy keys.

Decision 8 — Same-origin vs subdomain deployment

Chosen option: Same-origin MVP production deployment.

Target model:

https://app.forecourtos.com

Admin Portal, Employee Portal, and API should be served under the same origin where practical, with the API path-proxied under the app origin.

## Rejected options:

Separate admin/staff/API subdomains are rejected for MVP.
Hybrid cross-subdomain sessions are rejected for MVP.

Rationale:

Same-origin deployment keeps cookie, CORS, and CSRF rules simpler. It allows SameSite=Strict, omitted cookie Domain, and reduced cross-origin complexity.

## Q.3.1 implementation result:

Q.3.1 assumes same-origin browser auth for the production target while preserving local development compatibility. H068 tracks same-origin deployment/session routing validation.


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
auth.session.reuse_detected
auth.session.revoked_by_family_reuse
auth.password_reset.requested
auth.password_reset.completed
auth.password_reset.token_rejected
auth.password_reset.session_revoked
```

For `auth.session.rejected`, use only these exact `rejection_reason` values:

```text
invalid
revoked
expired
wrong_portal
missing_csrf_header
family_revoked
```

For `auth.password_reset.token_rejected`, use only these exact `rejection_reason` values:

```text
invalid
expired
used
wrong_type
```

### Q.3.3 Session Family Reuse Detection Note

Phase Q.3.3 extends refresh-session storage with nullable session-family fields. New login sessions create a fresh session family, and refresh rotation creates a child session in the same family with `parent_session_id` pointing at the rotated session.

Reuse detection is limited to already-rotated refresh sessions: a revoked session with a non-null family and at least one child session. When detected, the affected family is revoked, `auth.session.reuse_detected` is logged once, and `auth.session.revoked_by_family_reuse` is logged for each family member. Later refresh attempts from a family already revoked for reuse are rejected with `rejection_reason=family_revoked`.

### PII Decision

`ip_address` is stored as a raw nullable value for auth/security events.

Retention is 365 days. The lawful basis is legitimate interest for security monitoring, abuse detection, incident response, and account/session compromise investigation. Raw IP storage is chosen because hashed IPs reduce the ability to correlate incidents with infrastructure logs, abuse patterns, support reports, and security timelines.

`user_agent` is stored as a raw nullable value for auth/security events.

Retention is 365 days. The lawful basis is legitimate interest for security monitoring, suspicious session investigation, and distinguishing device/browser patterns during incidents.

This is a new personal-data processing decision under UK GDPR. The privacy notice must reflect this collection before commercial launch.

### Metadata Rules

metadata_json may contain only safe non-secret context.

Allowed examples:

```text
rejection reason context strings
numeric counters and timing data
non-identifying error categories
safe implementation flags such as cookie_backed=true
safe session-family incident context such as family_id and revoked_count
```

Forbidden under all circumstances:

raw refresh tokens
raw access tokens
hashed token values
cookie values
password values
Authorization header contents
email addresses
secret material
anything that uniquely identifies a person and is not already in a structured column

Use `user_id`, `employee_account_id`, `tenant_id`, and `auth_session_id` structured columns instead of putting identifiers into metadata.

### Indexing

Initial indexes support incident-response queries:

tenant_id + created_at
user_id + created_at
employee_account_id + created_at
event_type + rejection_reason + created_at
ip_address + created_at
auth_session_id

The auth_session_id index is included in Q.3.2.1 because session drill-down is a natural incident-response query and the index is narrow.

### Retention

All auth security events are retained for 365 days initially, including successful issued/rotated/revoked events and rejected/blocked events.

Retention enforcement is deferred to a later operational phase. The 365-day retention expectation is active now; implementation may later use a scheduled cleanup job, partitioning, or another production-appropriate retention mechanism.

### Out of Scope

All-sessions logout, password reset, email verification, 2FA, bearer-token deprecation/removal, and production deployment/session routing validation remain separate hardening work.


---

## D038 — Email/Auth Token Infrastructure for Password Reset and Email Verification

**Status:** Active
**Area:** Authentication / account recovery / email verification / security audit
**Added:** Phase Q.4.0

### Decision 1 — Scope

Q.4 covers admin-side users only for H058 password reset and H059 email verification.

Employee account recovery is out of scope for Q.4 because employees authenticate through site-scoped employee credentials rather than admin-side email identity. Employee recovery must be designed later with site/manager operational workflows in mind.

Q.4 does not include 2FA, does not remove bearer compatibility, and does not change D036 cookie/CSRF rules or D037 auth security event metadata/PII rules.

### Decision 2 — Token Table Strategy

Use one generic `auth_tokens` table with a `token_type` discriminator instead of separate password-reset and email-verification token tables.

Proposed schema:

```text
auth_tokens
  id UUID primary key
  token_type string not null
  user_id UUID FK users.id not null
  token_hash string not null
  expires_at timestamptz not null
  used_at timestamptz nullable
  created_at timestamptz not null
  created_ip string nullable
  consumed_ip string nullable
  request_id string nullable
  metadata_json nullable
```

Expected token types:

```text
password_reset
email_verification
```

Expected indexes:

```text
token_hash unique/indexed
user_id + token_type + created_at
expires_at
used_at
```

### Decision 3 — Token Generation and Hashing

Raw tokens must be generated from high-entropy random values, shown or sent only once, and never stored.

Use:

```text
secrets.token_urlsafe(32)
SHA-256 token hash
```

SHA-256 is acceptable because these tokens are high-entropy random secrets. Do not use bcrypt for auth tokens unless a later decision records a strong reason.

Only token hashes are stored. Token hashes must never be logged in `auth_security_events` or normal logs.

### Decision 4 — Expiry Windows

Use these initial expiry windows:

```text
password_reset: 1 hour
email_verification: 24 hours
```

Expired tokens must be rejected generically and must never reveal account or token details.

### Decision 5 — Single-Use and Replay Protection

Tokens are single-use. `used_at` must be set atomically when a token is consumed. Used tokens cannot be reused.

Token type must be checked during consumption:

```text
password_reset tokens cannot verify email
email_verification tokens cannot reset passwords
```

User identity must come from the token row, not from request body fields.

### Decision 6 — Account Enumeration Defence

Password reset request and email verification resend flows must not reveal whether an email/user exists, is disabled, or is already verified.

Password reset request returns generic success whether the email exists or not. Email verification resend returns a generic or otherwise safe response. Timing differences should be minimized where practical.

Approved generic wording:

```text
If an account exists for that email, instructions have been sent.
```

### Decision 7 — Email Sending Abstraction

Create an email service abstraction in a later implementation phase:

```text
EmailService.send_email(to, template_id, context)
```

Planned implementations:

```text
LocalLogEmailService
TestCaptureEmailService
StubProductionEmailService
```

No real SES, SendGrid, Postmark, Resend, or other provider integration is part of Q.4.0. Production provider selection is a later operational/deployment decision.

SPF, DKIM, and DMARC setup must be completed before commercial launch email sending.

### Decision 8 — Email Verification Login Policy

Allow unverified admin users to log in for now.

Do not block all login in Q.4 because current onboarding and tests may depend on login before verification. Future sensitive actions should be restricted until email is verified, and the frontend may later show a verification banner.

### Decision 9 — Password Reset Session Impact

Successful password reset must revoke all active `auth_sessions` for that user.

This is internal security behavior for password reset and is not the same as public all-sessions logout endpoint H067. The client must not receive session details.

Safe auth security events should be logged for session revocation.

### Decision 10 — Auth Security Events

Future implementation should extend D037 with these event types:

```text
auth.password_reset.requested
auth.password_reset.completed
auth.password_reset.token_rejected
auth.password_reset.session_revoked
auth.email_verification.requested
auth.email_verification.completed
auth.email_verification.token_rejected
auth.email_verification.already_verified
```

Future token rejection reasons:

```text
invalid
expired
used
wrong_type
```

Existing D037 forbidden metadata rules apply. Never log raw tokens, token hashes, passwords, email body content, Authorization headers, or cookies.

### Decision 11 — Rate Limits

Future implementation should use the existing SlowAPI/rate-limit approach where practical.

Proposed limits:

```text
password reset request:
  3 per email per hour
  10 per IP per hour

email verification resend:
  3 per user per hour
  10 per IP per hour
```

Q.4.0 does not implement rate limits.

Q.4.2 implements the existing SlowAPI route/IP-level password reset request limiter at `RATE_LIMIT_PASSWORD_RESET_REQUEST=10/hour`. The D038 target of 3 per email per hour remains a future hardening follow-up because implementing identifier-specific limits safely requires a repo-consistent rate-limit storage strategy and must not add Redis/new infrastructure in Q.4.2.

Q.4.3 implements the existing SlowAPI route/IP-level email verification request limiter at `RATE_LIMIT_EMAIL_VERIFICATION_REQUEST=10/hour`. The D038 target of 3 per user per hour remains H074 future hardening because implementing identifier-specific limits safely requires a repo-consistent rate-limit storage strategy and must not add Redis/new infrastructure in Q.4.3.

### Decision 12 — Implementation Phase Split

Implementation sequence:

```text
Q.4.0 — Email/auth token infrastructure design only
Q.4.1 — Email service abstraction + local/test email backend
Q.4.2 — Admin password reset backend
Q.4.3 — Admin email verification backend
Q.4.4 — Frontend wiring, if needed
```

Q.4.0 is documentation/design only. It adds no endpoints, code, migrations, tests, dependencies, or auth behavior changes.

### Q.4.1 Implementation Note

Phase Q.4.1 added the internal email service foundation:

```text
EmailService protocol
LocalLogEmailService
TestCaptureEmailService
EMAIL_BACKEND setting
get_email_service factory
```

The local logging backend does not send real email and does not log raw recipient email addresses. Local logs use a redacted recipient form with only the domain and a 4-character SHA-256 local-part prefix, for example `***@example.com (lp:a7b3)`.

Local template context logging uses an allowlist. Unknown keys are redacted by default, and forbidden/sensitive keys such as tokens, token hashes, passwords, cookies, auth headers, reset URLs, verification URLs, and verification codes are redacted.

Q.4.1 added no real provider integration, no password reset endpoints, no email verification endpoints, no `auth_tokens` table, no migrations, no frontend changes, and no auth behavior changes.

### Q.4.2 Implementation Note

Phase Q.4.2 added the admin-side password reset backend:

```text
auth_tokens table/model
password_reset token type
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
```

Raw password reset tokens are generated with `secrets.token_urlsafe(32)`, sent only once through the Q.4.1 email service, and stored only as SHA-256 hashes. Password reset tokens expire after 1 hour.

Token consumption uses an atomic update for unused, unexpired `password_reset` tokens. If atomic consumption fails, Q.4.2 performs a second read-only lookup to classify the internal audit reason as `invalid`, `expired`, `used`, or `wrong_type`; the client still receives a generic token failure.

Unknown and disabled email reset requests return the generic 202 response, log `auth.password_reset.requested` without `user_id`, do not include raw email in metadata, do not create token rows, and do not send email.

Successful password reset updates the admin user password hash, consumes the token, revokes active admin `auth_sessions` for that user, logs `auth.password_reset.completed`, and logs `auth.password_reset.session_revoked` per revoked session.

Q.4.2 applies the repo-consistent SlowAPI route/IP-level password reset request limit through `RATE_LIMIT_PASSWORD_RESET_REQUEST=10/hour`. Identifier-specific 3 per email per hour throttling remains deferred to H071.

Password reuse/history checks are deferred to H070. Email verification remains deferred to Q.4.3. Employee recovery and 2FA remain out of scope.

### Q.4.3 Implementation Note

Phase Q.4.3 added the admin-side email verification backend:

```text
users.email_verified_at
email_verification token type usage
POST /api/v1/auth/email-verification/request
POST /api/v1/auth/email-verification/confirm
```

The request/resend endpoint is authenticated for admin-side users and uses the current admin token as identity. It does not accept an arbitrary email or user ID. Employee tokens are rejected by the admin auth path.

Raw email verification tokens are generated with `secrets.token_urlsafe(32)`, sent only once through the Q.4.1 email service, and stored only as SHA-256 hashes. Email verification tokens expire after 24 hours.

Token consumption uses an atomic update for unused, unexpired `email_verification` tokens. If atomic consumption fails, Q.4.3 performs a second read-only lookup to classify the internal audit reason as `invalid`, `expired`, `used`, or `wrong_type`; the client still receives a generic token failure.

Already-verified verification requests return a safe success message, create no token row, send no email, and log `auth.email_verification.already_verified`. Confirming a valid token for an already-verified user consumes the token, preserves the original `email_verified_at`, returns success, and logs `auth.email_verification.completed` with safe metadata.

Successful email verification sets `users.email_verified_at`, consumes the token, logs `auth.email_verification.completed`, and does not revoke active sessions.

Q.4.3 applies the repo-consistent SlowAPI route/IP-level email verification request limit through `RATE_LIMIT_EMAIL_VERIFICATION_REQUEST=10/hour`. Identifier-specific 3 per user per hour throttling remains deferred to H074.

Unverified admin users are still allowed to log in per D038. Sensitive-action enforcement until email is verified remains deferred to H073. Employee recovery remains deferred. 2FA remains deferred to Q.5. Real email provider integration remains deferred.

---

## D039 — Owner 2FA / TOTP / Recovery Codes / Step-Up Auth Design

**Status:** Active
**Area:** Authentication / 2FA / sensitive action protection
**Added:** Phase Q.5.0

Q.5.0 is design-only. It adds no implementation code, migrations, endpoints, dependencies, frontend UI, tests beyond documentation checks, real secrets, or auth behavior changes.

**Implementation note — Phase Q.5.1:** Q.5.1 implemented the backend TOTP enrolment, login challenge verification, encrypted TOTP secret storage, and recovery-code use loop. It added `pyotp==2.9.0` and `cryptography==42.0.8`, `admin_user_2fa`, `auth_2fa_challenges`, `recovery_code` support in `auth_tokens`, and Q.5.1 auth security events. Q.5.1 did not implement disable 2FA, recovery-code regeneration, step-up auth, H073 enforcement, frontend UI, employee 2FA, SMS/email OTP, WebAuthn/passkeys, tenant-wide admin 2FA policy, owner transfer/demotion workflows, disaster recovery bypass, or production KMS/key rotation.

**Implementation note — Phase Q.5.1b:** Q.5.1b implemented backend 2FA lifecycle endpoints for disabling active 2FA and regenerating recovery codes. Disable requires an authenticated admin-side session, current password, and either current TOTP or a valid recovery code. Recovery-code regeneration requires an authenticated admin-side session and either current TOTP or a valid recovery code. Recovery codes used for these actions are consumed, disable invalidates unused recovery codes and permits future enrolment, regeneration invalidates old unused recovery codes and returns exactly 10 new codes once, and both endpoints are route-rate-limited. Q.5.1b did not implement step-up auth, H073 enforcement, frontend UI, employee 2FA, WebAuthn/passkeys, SMS/email OTP, tenant-wide admin 2FA policy, disaster recovery bypass, production KMS/key rotation, or all-session revocation on disable.

**Implementation note — Phase Q.5.2a:** Q.5.2a implemented the backend step-up mechanism using a server-side freshness stamp on `auth_sessions.last_2fa_step_up_at`, with a 5-minute TTL and route-limited `POST /api/v1/auth/2fa/step-up`. Newly issued access tokens carry an additive `sid` claim so protected actions can resolve the current server-side auth session without trusting client-provided session IDs. Q.5.2a wired the reusable sensitive-action dependency to store deactivation only; store deactivation is owner-only and requires verified email, active 2FA, and fresh step-up. H073 remains open/partial after Q.5.2b because only store deactivation is currently protected; future sensitive modules and approved Tier 1 flows must use the dependency at build time.

**Implementation note — Phase Q.5.2b:** Q.5.2b completed the sensitive-action rollout inspection as a documentation-only close-out. No additional currently-built endpoints were wired. D040 records the rollout boundary: store deactivation remains protected, 2FA lifecycle endpoints keep their action-level factor proof rather than duplicate step-up, admin-user creation is deferred until onboarding/user-management step-up UX exists, mixed staff pay/compliance fields need conditional or dedicated gating, and routine operational workflows are not step-up gated by default.

### Decision 1 — Default 2FA Method

**Chosen option:** TOTP using RFC 6238. Q.5.1 should target `pyotp` for TOTP generation and verification.

**Rejected options:** Email OTP, SMS OTP, and WebAuthn/passkeys for MVP.

**Rationale:** TOTP is the standard authenticator-app flow, has no SMS or email dependency, works with Google Authenticator, Authy, 1Password, Microsoft Authenticator, and similar apps, and is suitable for commercial SaaS owner/admin protection.

**Implementation implication:** Q.5.1 added pinned `pyotp` after dependency verification, then implemented TOTP enrolment and verification for admin-side accounts.

### Decision 2 — Reject Email OTP for 2FA

**Chosen option:** Do not use email OTP as the primary 2FA factor.

**Rejected options:** Using email verification links or email OTP codes as the second factor.

**Rationale:** Email is already used for password reset, email verification, and account recovery. If email is compromised, email-based 2FA does not provide a strong independent second factor.

**Implementation implication:** Q.5.1 must not implement email OTP as the primary 2FA factor. Email may remain part of account recovery workflows, but not the main 2FA method.

### Decision 3 — Reject SMS OTP

**Chosen option:** Do not use SMS OTP for MVP 2FA.

**Rejected options:** SMS OTP as default or fallback 2FA.

**Rationale:** SMS has SIM-swap risk, adds provider and infrastructure complexity, is not needed for MVP, and is weaker than TOTP for this stage.

**Implementation implication:** Q.5.1 must not add SMS provider dependencies, phone-number OTP flows, or SMS-based recovery.

### Decision 4 — Defer WebAuthn / Passkeys

**Chosen option:** Defer WebAuthn/passkeys to v2.

**Rejected options:** Implementing passkeys before TOTP or requiring passkeys for first launch.

**Rationale:** WebAuthn is strong long-term, but requires frontend/browser API work, device and recovery modeling, and more support complexity than is needed for first launch.

**Implementation implication:** Q.5.1 must not implement WebAuthn. H078 tracks future passkey support.

### Decision 5 — Supply-Chain Decision for `pyotp`

**Chosen option:** Select `pyotp` for Q.5.1, but do not install it during Q.5.0.

**Rejected options:** Adding the dependency during design, using an unverified similarly named package, or hand-rolling TOTP cryptography.

**Rationale:** D035 dependency discipline applies. Q.5.1 must verify the package exists on PyPI, the package name matches official documentation, and the package is mature and widely used before installation. Q.5.0 did not perform package installation or dependency audit.

**Implementation implication:** Q.5.1 must run dependency and audit checks before commit after adding `pyotp`.

### Decision 6 — TOTP Secret Storage

**Chosen option:** Encrypt TOTP secrets in Q.5.1 using AES-256-GCM with a runtime environment key named `TOTP_ENCRYPTION_KEY`.

**Rejected options:** Plain storage without encryption, storing the encryption key in the database, hardcoding an encryption key, or reusing `JWT_SECRET_KEY` as the TOTP encryption key.

**Rationale:** AES-GCM with an environment-injected key is acceptable for MVP while keeping the key separate from JWT/session/token secrets. Production maturity should move toward managed secrets, rotation, and KMS/Secrets Manager.

**Implementation implication:** Q.5.1 added the `TOTP_ENCRYPTION_KEY` setting, validates it when encrypted TOTP storage is used, does not use `JWT_SECRET_KEY`, does not store the key in the database, and does not commit generated keys. Docs may show only a placeholder:

```env
TOTP_ENCRYPTION_KEY=replace-with-generated-production-secret
```

Suggested key generation may be documented as `openssl rand -base64 32`, but the generated value must never be committed. H075 tracks production-grade key rotation/KMS hardening.

### Decision 7 — Recovery Codes

**Chosen option:** Generate 10 recovery codes after successful enrolment confirmation, show them once, store only hashes, and make each code single-use.

**Rejected options:** Storing recovery codes in plaintext, displaying them after enrolment, allowing reuse, or logging recovery-code values.

**Rationale:** Recovery codes are necessary when an owner/admin loses access to their authenticator device, but they must be treated as high-entropy secrets.

**Implementation implication:** Q.5.1 should reuse the existing `auth_tokens` table if practical by adding token type `recovery_code`, extend constraints where present, consume codes with the same atomic replay-protection pattern as Q.4.2 auth tokens, audit recovery-code use, and never log raw values or hashes.

### Decision 8 — Owner Enrolment Policy

**Chosen option:** Owner must enrol in 2FA. Admin enrolment is optional initially. Tenant-level require-2FA-for-all-admins policy is deferred.

**Rejected options:** Requiring all admins immediately, employee 2FA in this phase, or tenant-level policy controls in Q.5.1.

**Rationale:** Owner accounts protect tenant-level business control and future sensitive governance, while admin-wide policy needs tenant settings and rollout behavior that should be designed later.

**Implementation implication:** Q.5.1 should expose enrolment status and support owner/admin enrolment. H076 tracks future tenant-level admin-wide 2FA policy. Employee 2FA remains separate and future.

### Decision 9 — Existing-Owner Grace Model

**Chosen option:** `ENROL-BEFORE-SENSITIVE-ACTIONS`.

**Rejected options:** A time-based grace period such as "enrol within 14 days or get locked out."

**Rationale:** Existing owners must not be instantly locked out when Q.5.1 is deployed. A time-based lockout creates support incidents and requires scheduling/notification behavior that does not currently exist. Action-gated enrolment prompts the user when they attempt sensitive work.

**Implementation implication:** Q.5.1 must not block all owner login. It should expose 2FA enrolment status and provide enrolment/verification foundations. Q.5.2 should block sensitive actions when email verification, 2FA enrolment, or recent step-up verification is required and missing.

### Decision 10 — Login Flow When 2FA Is Enrolled

**Chosen option:** If a user has no active/enrolled 2FA, login remains compatible and returns access/refresh tokens as today. If a user has active/enrolled 2FA, password verification succeeds but normal access/refresh tokens are not issued yet. The response should indicate:

```json
{
  "requires_2fa": true,
  "two_factor_challenge_token": "short-lived-token",
  "token_type": "2fa_pending"
}
```

The client then calls a Q.5.1 verification endpoint with the challenge token plus a TOTP code or recovery code. On successful 2FA verification, access token and refresh cookie/session are issued.

**Rejected options:** Requiring password resubmission at the verification endpoint, issuing full access/refresh tokens before second factor, or allowing a 2FA challenge token to access admin APIs.

**Rationale:** The second factor must complete before the account receives normal authenticated session power.

**Implementation implication:** Q.5.1 must introduce a short-lived, single-purpose challenge that grants no admin/API access and is not equivalent to an access or refresh token.

### Decision 10b — Enrolment Confirmation Handshake

**Chosen option:** TOTP enrolment is a two-step handshake: `enrol/begin` creates a pending secret and returns QR provisioning data/manual secret; `enrol/confirm` verifies the first TOTP code and only then activates 2FA and issues recovery codes.

**Rejected options:** Single-step activation or issuing recovery codes before proof that the authenticator works.

**Rationale:** Users must prove their authenticator app can produce valid codes before 2FA is enforced. Otherwise a failed QR scan or clock issue could lock the user out.

**Implementation implication:** Q.5.1 must model pending versus active enrolment, keep `totp_enrolled_at` or equivalent null until confirmation succeeds, make pending enrolment retryable/discardable, expire or safely replace pending secrets, and issue recovery codes only after confirmation.

### Decision 10c — 2FA Challenge-Token Lifecycle

**Chosen option:** The 2FA challenge token expires after 5 minutes, is single-use, is invalidated immediately after successful TOTP or recovery-code verification, is usable only at the 2FA verification endpoint, and carries no admin/API permissions.

**Rejected options:** Long-lived challenges, reusable challenges, or stateless challenges that cannot support failed-attempt counting and invalidation.

**Rationale:** A pending 2FA challenge is not a session. It must be safe to abandon, expire without creating a session, and support brute-force controls.

**Implementation implication:** Q.5.1 must choose a concrete mechanism such as a short-lived signed token with tracked `jti` or a server-side challenge row. It must support expiry, single-use invalidation, five failed attempts per five minutes, and safe abandonment. Submitted TOTP and recovery codes must never be logged.

### Decision 11 — Refresh Cookie / CSRF Interaction

**Chosen option:** Q.3.1 cookie/session rules remain unchanged.

**Rejected options:** Setting refresh cookies before 2FA succeeds or treating the 2FA pending token as a refresh token.

**Rationale:** Full refresh sessions should exist only after successful 2FA. Cookie-backed refresh/logout still require `X-Requested-With: ForecourtOS`, and bearer compatibility remains governed by D036.

**Implementation implication:** Q.5.1 must not set a refresh cookie until 2FA succeeds. The 2FA challenge token must not work as a refresh token, access token, or admin API credential.

### Decision 12 — TOTP Verification Window and Replay Protection

**Chosen option:** Use 6-digit TOTP, 30-second time steps, and accept a +/-1 time-step window. Prevent replay by tracking the last accepted time step, not just a timestamp.

**Rejected options:** Accepting broad time windows or accepting the same TOTP time step more than once.

**Rationale:** A narrow window balances normal clock drift with replay resistance. Production server clocks must use reliable time/NTP.

**Implementation implication:** Q.5.1 should store `totp_last_used_time_step` or equivalent and reject repeated use of the same accepted code/time step.

### Decision 13 — Brute-Force Protection

**Chosen option:** TOTP/recovery-code verification should allow at most 5 failed attempts per challenge/session per 5 minutes; after that, invalidate the challenge and require password login again.

**Rejected options:** Unlimited TOTP attempts or logging submitted codes for debugging.

**Rationale:** TOTP is short, so brute-force controls are required. Route/IP rate limiting remains useful but is not enough on its own.

**Implementation implication:** Q.5.1 must count failed attempts against the challenge, log failures safely, preserve route/IP limiting where available, and never log submitted TOTP or recovery codes.

### Decision 14 — Disable 2FA

**Chosen option:** Disabling 2FA initially requires an authenticated admin-side session, current password, and either current valid TOTP code or a valid single-use recovery code.

**Rejected options:** Password-only disable, unauthenticated disable, or support bypass without a dedicated disaster-recovery flow.

**Rationale:** Disabling 2FA is a sensitive account-security action and should require proof of password plus possession of either the current authenticator or a valid recovery code. Allowing recovery-code disable lets a user who lost the authenticator but retained a recovery code regain account control without a support bypass.

**Implementation implication:** Q.5.1b audit-logs disable, consumes a recovery code when used, invalidates unused recovery codes, clears active/pending TOTP state, and never reveals TOTP secrets or recovery codes. Owner disable may later require step-up or another owner/admin approval. All-session revocation on disable remains deferred.

### Decision 15 — Recovery-Code Regeneration

**Chosen option:** Regeneration requires an authenticated admin-side session plus current TOTP or a valid single-use recovery code. Old unused recovery codes are revoked, 10 new recovery codes are generated and shown once, and an audit event is recorded.

**Rejected options:** Regenerating with password only, appending unlimited recovery codes, displaying old recovery codes, or leaving previous unused codes valid.

**Rationale:** Regeneration creates new account-recovery secrets and must not leave older unused codes valid. A valid recovery code may stand in for TOTP so a user who lost the authenticator can rotate back to a fresh recovery-code set.

**Implementation implication:** Q.5.1b consumes the supplied recovery code when one is used, revokes old unused recovery codes atomically enough to prevent reuse races, stores only hashes, and never logs recovery-code values.

### Decision 16 — Step-Up Auth for Sensitive Actions

**Chosen option:** Q.5.2 should add sensitive-action step-up using TOTP, granting short-lived step-up state such as 5 minutes tied to the current session/user.

**Rejected options:** Global step-up across browsers/devices, implementing step-up in Q.5.1, or protecting sensitive actions with email verification only.

**Rationale:** Sensitive actions need a recent proof of control, not just an old login. Step-up must be scoped to the active session/device.

**Implementation implication:** Q.5.2a stores step-up freshness on the current `auth_sessions` row, uses a 5-minute TTL, and protects store deactivation first. Q.5.2 should also protect billing/subscription actions, payroll/pay settings, staff sensitive data/compliance documents, role/permission changes, tenant-level destructive actions, owner/admin 2FA disable, future AI autonomous/high-impact approvals, and exports of sensitive employee data. Categories without endpoints yet are future sensitive-action categories.

### Decision 17 — H073 Relationship

**Chosen option:** Combine H073 with the Q.5.2 sensitive-action gate.

**Rejected options:** Building separate email-verified and step-up enforcement systems.

**Rationale:** H073 email-verified restriction and step-up 2FA both gate sensitive actions. One gate avoids duplicate enforcement logic.

**Implementation implication:** Q.5.1 must not implement H073. Q.5.2 should enforce verified email where required, enrolled 2FA where required, and recent step-up where required.

### Decision 18 — Auth Security Event Vocabulary

**Chosen option:** Extend D037/D039 vocabulary for future Q.5.1/Q.5.2.

**Rejected options:** Logging raw secrets/codes/tokens or using vague events that do not distinguish enrolment, verification, recovery-code use, and step-up.

**Rationale:** 2FA and step-up need auditability without exposing secrets.

**Implementation implication:** Q.5.1 adds events `auth.2fa.enrolment_started`, `auth.2fa.enrolment_completed`, `auth.2fa.enrolment_abandoned`, `auth.2fa.verification_succeeded`, `auth.2fa.verification_failed`, and `auth.2fa.recovery_code_used`. Q.5.1b adds `auth.2fa.recovery_codes_regenerated` and `auth.2fa.disabled` with the disable/regeneration endpoints. Q.5.2a adds `auth.2fa.step_up_succeeded`, `auth.2fa.step_up_failed`, `auth.sensitive_action.blocked`, and `auth.sensitive_action.allowed` to support session-bound step-up and sensitive-action gate auditing. For `auth.2fa.verification_failed` and `auth.2fa.step_up_failed`, allowed rejection reasons include `invalid_code`, `code_reused`, `expired_window`, `rate_limited`, `challenge_expired`, and `challenge_invalid`.

Q.5.2 should add events `auth.stepup.required`, `auth.stepup.succeeded`, and `auth.stepup.failed`.

Metadata must not log TOTP secrets, TOTP codes, recovery codes, recovery-code hashes, challenge tokens, challenge-token hashes, passwords, cookies, Authorization headers, email addresses, or raw secret values.

### Decision 19 — Q.5 Phase Split

**Chosen option:** Split Q.5 as:

```text
Q.5.0 — 2FA design decisions only
Q.5.1 — TOTP enrolment + login verification + recovery codes backend
Q.5.1b — disable 2FA + recovery-code regeneration backend
Q.5.2a — step-up auth mechanism + store deactivation gate
Q.5.2b — sensitive-action rollout inspection close-out
Q.5.3 or later — frontend 2FA UI wiring if not included elsewhere
```

**Rejected options:** Combining all 2FA, step-up, H073, and frontend UI work into one implementation phase.

**Rationale:** Auth changes need narrow reviewable increments.

**Implementation implication:** Q.5.1 must not implement Q.5.2 sensitive-action gates, and Q.5.0 remains documentation/design only.

### Decision 20 — Out of Scope

**Chosen option:** Q.5.0 is documentation/design only.

**Rejected options:** Code, migrations, endpoint implementation, dependency installation, frontend UI, real secrets, and tests beyond doc/grep checks in Q.5.0.

**Rationale:** Implementation should follow the locked design in smaller phases.

**Implementation implication:** Q.5.1 must also exclude step-up auth, H073 sensitive-action enforcement, frontend UI, SMS OTP, email OTP, WebAuthn/passkeys, employee 2FA, owner transfer/demotion workflows, tenant-level require-2FA-for-all-admins policy, disaster-recovery bypass process, and production KMS/key rotation implementation.

### Secret Handling Rules

No hardcoded secrets, real keys, README real keys, `.env.example` real keys, database-stored TOTP encryption keys, or JWT-secret reuse are allowed. Production TOTP encryption keys must be generated outside the repo and injected via runtime environment/config/secrets manager.


---

## D040 — Sensitive-Action Step-Up Rollout Boundary

**Status:** Active
**Area:** Authentication / 2FA / sensitive actions
**Added:** Phase Q.5.2b

Q.5.2b is documentation-only. It adds no backend behavior changes, endpoint guards, migrations, models, schemas, tests, frontend UI, or auth-flow changes.

### Decision

Step-up is required for session-only sensitive actions where a hijacked session alone could execute the action.

Step-up is not automatically required for actions that already require live action-level factor proof in the request body. In the current implementation this applies to:

- `POST /api/v1/auth/2fa/disable`, which requires current password plus current TOTP or a valid recovery code.
- `POST /api/v1/auth/2fa/recovery-codes/regenerate`, which requires current TOTP or a valid recovery code.

Store deactivation remains the first protected sensitive action:

- `POST /api/v1/stores/{store_id}/deactivate` is owner-only and requires verified email, active 2FA, and fresh session-bound step-up.

Admin-user privilege creation/change is a future Tier 1 step-up candidate, but wiring is deferred until admin onboarding/user-management UX supports owner 2FA enrolment and step-up.

Mixed staff profile endpoints containing pay/compliance fields should not be blanket-gated. Future implementation should use conditional field-level step-up when pay/right-to-work fields change, or dedicated pay/compliance endpoints protected by the sensitive-action dependency.

Routine operational workflows should not be step-up gated by default. This includes store setup/configuration, company profile edits, coverage templates, hour targets, rota publish/unpublish, shift CRUD/cancel, availability, shift requests, hot food entries, rota recommendations, normal reads, and operational staff job-tag metadata.

### Rejected Options

- Wiring every inspected mutation endpoint to the sensitive-action dependency in Q.5.2b.
- Adding duplicate step-up to 2FA lifecycle endpoints that already require current factor proof.
- Blanket-protecting general staff profile endpoints because they contain both routine profile edits and sensitive pay/compliance fields.
- Protecting routine operational workflows that are already governed by RBAC, tenant/site isolation, validation, and audit logging.

### Rationale

Step-up should protect high-impact session-only authority without creating re-prompt fatigue. Over-gating routine workflows makes users habituated to prompts and weakens real security behavior. The current 2FA lifecycle endpoints are not session-only actions because a stolen session alone is insufficient: the attacker would still need the password, current TOTP, or a valid recovery code.

Admin-user creation and staff pay/compliance writes are legitimate future sensitive-action candidates, but the current implementation shape needs product sequencing. Admin-user creation has onboarding/bootstrap risk until owner 2FA enrolment and step-up UX are available. Staff pay/compliance writes are mixed into broad profile endpoints, so field-level or dedicated endpoint design is needed before enforcement.

### Implementation Implication

Q.5.2b makes no code changes. Future phases should:

- Gate `POST /api/v1/admin/users` when admin onboarding/user-management frontend flow supports owner 2FA enrolment and step-up.
- Apply conditional field-level gating or dedicated protected endpoints for staff pay and right-to-work/compliance changes.
- Apply the sensitive-action dependency at build time for future billing/subscription, payroll/pay-rule, compliance document, sensitive export, sensitive audit-log, tenant/site/employee erasure, and owner/admin governance modules.
- Keep routine operational endpoints outside fresh step-up unless their semantics change into financial, governance, destructive, export, or hard-erasure actions.

H060 and H073 remain partial after Q.5.2b.

---
