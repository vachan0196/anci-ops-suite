
---

# 🧠 `DECISIONS.md` — ForecourtOS / Anci Ops Suite Decisions Log

**Last updated:** 2026-05-13
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

**Status:** Needs decision
**Area:** Roles

### Current

First user = `admin`

### Target

First user = `owner`

### Risk

No distinction between business owner and admin

### Future direction

Introduce:

```text
owner > admin > manager > employee
```

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

---

## D006 — Site Setup Uses localStorage (RESOLVED)

**Status:** Resolved / Historical

### Update

Phase F / F.1:

* Store created via backend
* Opening hours persisted
* Staff persistence connected
* Employee accounts created during staff setup

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

metadata_json may contain only safe non-secret context.

Allowed examples:

```text
rejection reason context strings
numeric counters and timing data
non-identifying error categories
safe implementation flags such as cookie_backed=true
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

H066 refresh-token reuse detection and session-family handling remains out of scope for Q.3.2.1 and belongs to Q.3.3.


---
