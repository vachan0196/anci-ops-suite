
---

# 🧠 `DECISIONS.md` — ForecourtOS / Anci Ops Suite Decisions Log

**Last updated:** 2026-08-15
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

**Superseded in part by D063 (2026-09-02).** The `manager` tenant-role target above is withdrawn. The admin-side role set is and remains `owner | admin`; no `manager` tenant role will be created, and `admin` is the operational role the business calls a manager. Store scope comes from an explicit assignment relation, not from a role. The rest of this future direction — owner-only governance, owner transfer/promotion/demotion, and 2FA or step-up enforcement — is unaffected.

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

**Amended by D063 (2026-09-02).** That target is withdrawn: there is no future `manager` tenant role. The admin-side role set is `owner | admin`. This entry's own decision is unchanged — `member` is not Admin Portal access, and D063 restates that `member` remains a staff-identity bridge per this entry.

### Implementation note — Phase R.2d

Phase R.2d added an admin-auth-specific guard to block `member` admin session/token issuance through admin login, admin refresh, 2FA challenge verification, and 2FA step-up. The guard is not placed in shared token creation utilities, so employee portal login through `employee_accounts` remains separate and unchanged.

Company profile read/update is owner-only as defense-in-depth.

### Future direction

Decouple normal staff/employee creation from admin-auth `users` where practical, or keep the bridge explicitly documented until `staff_profiles.user_id` is redesigned.

---

## D043 — Owner-Only Sensitive Staff Pay/RTW Access

**Status:** Active
**Area:** Staff / RBAC / sensitive employee data
**Date recorded:** 2026-05-31
**Implemented:** Staff.2, Staff.2b, and Staff.1 safe UI boundary

### Decision

For MVP, sensitive staff pay and right-to-work fields are Owner-only.

The Admin Portal may be shared by Owner and operational Admin roles, but field visibility and backend permissions are role-specific.

```text
Same Admin Portal
Different role
Different backend permissions
Different field visibility
```

### Current role boundary

Current implemented tenant roles remain:

```text
owner | admin | member
```

The future `manager` tenant role remains a target and is not fully implemented in the current backend role set.

Until a real manager role and permission-grant model exist, Manager must not be assumed to have sensitive staff data access.

**Amended by D063 (2026-09-02).** No `manager` tenant role will be created, so the target above is withdrawn and the condition in the sentence preceding this note is never met. This entry's own decision is unchanged: pay and RTW fields are owner-only, and D063's `admin` role — the operational role the business calls a manager — does not receive sensitive staff data access.

### Owner access

Owner may read and write these sensitive staff fields through staff admin APIs:

```text
hourly_rate
pay_type
rtw_status
```

Owner access to future payroll/compliance-sensitive fields must remain Owner-only unless a later explicit permission model says otherwise.

Sensitive payroll/compliance views and actions should require 2FA/step-up where applicable and should be audit logged where implemented.

### Admin access

Admin may use operational Admin Portal workflows where permitted.

Admin must not receive these sensitive fields from staff read endpoints:

```text
hourly_rate
pay_type
rtw_status
```

Admin must not write non-null values for these fields through staff write endpoints:

```text
hourly_rate
pay_type
rtw_status
```

If Admin sends those fields as explicit `null`, the backend treats them as “not setting” and strips them before persistence. Explicit null values must not clear existing Owner-set sensitive values.

Admin may continue to create/update basic staff profile fields where currently permitted.

### Member access

`member` remains a staff identity bridge and is not Admin Portal access.

Member-accessible admin-style staff profile reads must use the safe staff projection and must not expose pay or RTW fields.

Employee-facing data remains separate through the Employee Portal.

### Endpoint behaviour after Staff.2 / Staff.2b

Staff.2 hardened staff read models:

```text
GET /api/v1/staff
GET /api/v1/staff/{staff_id}
GET /api/v1/staff/me
```

Owner receives full staff profile data including:

```text
hourly_rate
pay_type
rtw_status
```

Non-owner staff read responses omit those keys entirely. They are not returned as `null`.

`GET /api/v1/staff/directory` remains a trimmed directory endpoint and must not expose sensitive pay/RTW fields.

Staff.2b hardened staff write models:

```text
POST /api/v1/staff
PATCH /api/v1/staff/{staff_id}
```

Owner can write `hourly_rate`, `pay_type`, and `rtw_status`.

Non-owner roles cannot write non-null values for those fields.

For non-owner writes:

```text
non-null hourly_rate/pay_type/rtw_status → reject with 403
null hourly_rate/pay_type/rtw_status     → strip and treat as not setting
omitted hourly_rate/pay_type/rtw_status  → allow normal safe-field write
```

### Employee portal distinction

Do not confuse admin staff models with employee-facing projections.

The Employee Portal may expose its own employee-safe pay or status projections where product-approved, such as own earnings or pay breakdown.

Admin staff profile projections must not be used as a shortcut for employee-facing sensitive data.

### Staff.1 frontend implementation note

Staff.1 completed the normal safe staff profile view/edit UI as frontend-only work.

The Admin Portal route is:

```text
/admin/staff/[staffId]
```

Staff.1 loads staff detail for edit pre-fill with:

```text
GET /api/v1/staff/{staff_id}
```

Staff.1 must not use `/api/v1/staff/directory` for edit pre-fill.

Staff.1 saves with:

```text
PATCH /api/v1/staff/{staff_id}
```

The Staff.1 save payload is a dedicated safe edit payload containing only:

```text
job_title
phone
emergency_contact_name
emergency_contact_phone
contract_type
notes
```

Even when Owner receives a full staff detail response, Staff.1 must not round-trip `hourly_rate`, `pay_type`, or `rtw_status` back into PATCH.

Staff.1 added visible notes warning copy:

```text
Do not store NI numbers, right-to-work document details, passport/BRP/share-code details, medical information, payroll-sensitive data, or other sensitive personal data in notes.
```

Staff.1 changed no backend files, auth/session/localStorage behaviour, or employee portal behaviour.

### Still out of scope

The following remain future design work and must not be added as fake frontend-only fields:

```text
NI number
passport number
BRP/passport/share-code document upload
compliance document storage
weekly hour cap
base hours threshold
overtime rate
payroll rules
conditional Admin/Manager grant model
```

Weekly hour cap, base hours threshold, overtime rate, and payroll rules belong to the future payroll/pay-rules model, not the generic staff profile form.

NI/document/compliance storage requires a separate secure storage, retention, audit, access-control, and 2FA/step-up design.

### Staff UI implication

Normal Staff edit UI should use a safe-fields payload only.

Safe operational staff fields may include:

```text
job_title
phone
emergency_contact_name
emergency_contact_phone
contract_type
notes
```

`notes` is free text and must include UI warning copy not to store NI numbers, right-to-work document details, medical information, payroll-sensitive data, or other sensitive personal data.

Do not include these in normal safe staff edit UI:

```text
is_active
deactivate
reactivate
archive
delete
hourly_rate
pay_type
rtw_status
NI number
passport number
BRP/share-code documents
document upload
base hours threshold
overtime rate
weekly hour cap
payroll rules
display_name
```

Staff activation/deactivation is a lifecycle action and must be handled separately from normal safe staff edit, similar to the store lifecycle decision in T.2a.

`display_name` editing is deliberately deferred because it may be coupled to the linked admin/user identity record and raises a name-authority question.

### Known follow-ups

```text
Staff.1 — Safe staff profile view/edit UI (completed frontend-only)
Staff.1L — Staff deactivate/reactivate lifecycle design
Future — Owner-only pay/RTW UI with 2FA/step-up/audit where applicable
Future — NI/compliance document secure storage design
Future — Payroll/pay-rules model
Future — conditional Admin/Manager grant model, if required
```

---

## D044 — Admin Rota Uses Site-Scoped Route Family and Backend Store List Scope

**Status:** Active
**Area:** Admin rota / frontend routing / site scoping
**Date recorded:** Rota.1, 2026-06-07

### Decision

The Admin Portal rota UI uses the site-scoped rota route family for normal rota operations:

```text
GET  /api/v1/sites/{site_id}/rota/week
POST /api/v1/sites/{site_id}/shifts
PATCH /api/v1/sites/{site_id}/shifts/{shift_id}
POST /api/v1/sites/{site_id}/shifts/{shift_id}/cancel
POST /api/v1/sites/{site_id}/rota/publish
POST /api/v1/sites/{site_id}/rota/unpublish
```

The older `/api/v1/shifts/*` route family remains legacy/current compatibility and must not be selected for new Admin Portal rota UI work unless a later decision changes the route strategy.

The Rota.1 site selector is sourced from the existing backend store list:

```text
GET /api/v1/stores
```

The frontend renders only active sites returned by the backend for the current admin-side session. It does not invent assigned-site filtering, broaden access, or persist the selected site in localStorage.

### Why

Current product naming is moving toward "site", and the implemented admin rota workflow already uses `/sites/{site_id}` for weekly rota, shift create/edit/cancel, and publish/unpublish. Site scoping and tenant visibility must remain backend-owned.

### Future direction

Assigned-site Admin/Manager RBAC remains a future backend/product decision. The frontend selector must continue to defer to backend store-list scope until that policy is explicitly implemented.

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

## D007 — Staff Setup Can Happen During Site Setup or Later

**Status:** Active

### Decision

Staff can be created during site setup and can also be added later to an existing site.

### Current implementation

UX.2 added `/admin/staff/new`, allowing staff to be added to an existing active site after site creation.

### Why

Staff must belong to a site, but real operators need to add employees after the initial site setup.

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

### UX.2 / Staff.2b note

The frontend staff creation flow remains multi-step:

```text
create user → create staff → assign role
```

Staff.2b may reject `POST /staff` for non-owner users if non-null pay/RTW fields are submitted. Because user creation happens first, this can leave an orphan member user in some failed non-owner sensitive-write attempts.

This orphan-chain consequence is accepted temporarily and should be addressed by a future safer setup endpoint or by hiding/omitting sensitive fields for non-owner staff creation flows.

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

**Amended 2026-09-03.** Decision 7 named three implementations:
`LocalLogEmailService`, `TestCaptureEmailService` and
`StubProductionEmailService`. Live inspection on 2026-09-03 established that
`StubProductionEmailService` does not exist at HEAD.
`apps/api/services/email/__init__.py:9-13` accepts only `local_log` and
`test_capture` and raises `ValueError` on any other value. The original list is
retained above as the record of what was planned; it does not describe the code.

The settled **target** implementation set is:

```text
test_capture    automated tests
local SMTP      local and manual development, delivering to a local
                mailbox such as Mailpit
production      a real transactional provider
```

`local SMTP` and the production provider do not exist at HEAD. They are the
direction this amendment settles, to be built in Q.5.3a.

`local_log` is retained for environments where no delivery is expected. It
cannot serve development verification or password-reset flows, because
`verification_url` and `reset_url` are members of `FORBIDDEN_CONTEXT_KEYS`
(`apps/api/services/email/local.py:28-45`) and are rendered as
`<REDACTED:length=N>`.

**Raw token exposure.** No product API, development bypass endpoint,
application log, or user-facing non-email surface may expose a raw verification
or password-reset token.

Raw tokens may exist transiently inside the EmailService delivery payload, and
inside `TestCaptureEmailService`'s in-memory fixture for automated tests. They
are never persisted in plaintext — `auth_tokens` stores a SHA-256 hash and has
no raw-token column.

No development bypass endpoint will be created. `FORBIDDEN_CONTEXT_KEYS`
redaction stands and is test-locked. Delivery is made usable by delivering, not
by unredacting.

An authenticated endpoint returning a raw token, or a UI that displays the
verification link on screen, are both rejected. Either would prove possession of
the browser session rather than possession of the mailbox, which is the property
verification exists to establish.

**Production provider: Resend.** Chosen for low initial setup and operational
overhead for the first customer, behind this decision's existing abstraction. It
is not an architectural commitment; the provider is replaceable without touching
product-domain logic. No pricing figures are recorded here — they change, and
the current terms must be checked at the point of signup rather than cited from
this entry.

**Sending domain.** A dedicated sending subdomain, isolating reputation from the
primary domain. SPF, DKIM and DMARC must be configured before first-customer
use, per this decision's existing pre-launch requirement. DMARC begins at
`p=none`.

**`APP_BASE_URL` must be configured per environment.** It defaults to
`http://localhost:3000` (`settings.py:15`) and supplies the host for both the
verification and password-reset URLs. A delivered email carrying the wrong host
is a broken flow regardless of the provider.

**Verification and password reset share infrastructure, not semantics.** The
email-verification request is initiated by an authenticated admin; confirmation
uses the emailed raw token as its credential on an unauthenticated endpoint and
records mailbox ownership.

Password reset is an account-recovery flow; its emailed raw token authorises a
password change on an unauthenticated endpoint.

Delivery, route shape and presentation may be shared. Their domain actions and
backend security contracts remain distinct.

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

## D042 — Tenant Isolation Gate and Missing Permission Matrix

**Status:** Active
**Area:** Tenant isolation / RBAC / security testing
**Added:** Phase T.0

### Decision

Tenant isolation is an absolute product rule and is enforced in the current backend at the application layer through dependencies, active tenant membership, and explicit `tenant_id` / site-store query filters. PostgreSQL Row Level Security is not currently used.

Phase T.0 adds a focused backend security gate for high-risk company, stores, staff, and employee portal isolation paths. SQLite tests are meaningful for the current app-layer isolation mechanism, but they do not provide database-layer RLS assurance because there are no RLS policies to validate.

### Permission Matrix Boundary

The expected `forecourt_os_permission_matrix_v1.md` file was not present in the local repo during T.0, and no complete local equivalent was found.

Therefore:

- Cross-tenant isolation tests are enforced as bugs if they fail.
- Role-boundary tests in T.0 use only explicit local decisions as oracles, such as D041 member-not-admin and company profile owner-only behavior.
- Broader role-boundary expectations must not be inferred from current code behavior or invented without the permission matrix.

### Future Direction

T.1 should add the permission matrix or local equivalent, then expand matrix-backed role-boundary coverage across admin-user creation, staff pay/right-to-work field policy, rota/shifts/requests, availability admin APIs, hour targets, coverage templates, and rota recommendations.

### Phase T.1 update

Phase T.1 created `apps/api/docs/forecourt_os_permission_matrix_current_v1.md` instead of restoring or inventing an old PRD permission matrix. The document is pinned to commit `5b79955` and separates CURRENT-TRUTH, TARGET, and GAP/BACKLOG rows.

The CURRENT-TRUTH layer is derived from effective backend access: guards, handler logic, tenant/site filters, response schemas, mutation schemas, and tests. TARGET rows are not current enforcement. GAP/BACKLOG rows must be triaged before onboarding real tenants or turning target behavior into tests.

### Phase T.2a update

Phase T.2a closed the confirmed store lifecycle bypass recorded by T.1. Ordinary `PATCH /api/v1/stores/{store_id}` no longer accepts or writes `is_active`; lifecycle/deactivation state must not be changed through generic store update. Store deactivation remains routed through `POST /api/v1/stores/{store_id}/deactivate`, protected by the Q.5.2a sensitive-action gate. No reactivation endpoint exists after T.2a; reactivation requires a future explicit lifecycle design if the product needs it.

---
## D044 — Staff roles are operational job-role labels, not permission roles

**Status:** Accepted
**Date:** 2026-06-11

### Decision

`staff_roles` are operational staff/job-role labels only.

They are not permission-bearing roles and must not be treated as tenant RBAC roles.

### Scope

Staff roles may be used for:

* staff categorisation
* staff profile display
* rota role matching
* rota recommendations
* operational scheduling hints

Staff roles must not be used for:

* authentication
* authorization
* token/session capability
* tenant membership
* admin portal access
* employee portal access
* owner/admin/member RBAC decisions

Tenant/application permissions remain governed by the auth/RBAC layer, especially tenant membership role values such as owner/admin/member.

### Rationale

D2.0 confirmed that `staff_roles` are stored separately from RBAC membership and are consumed only by operational staff/rota flows. They do not grant portal capability or mutate user/session/tenant membership state.

### Implementation notes

Staff role editing is therefore allowed as a frontend-led operational edit, provided it uses existing staff role endpoints and preserves tenant/RBAC boundaries.
---
## D045 — Staff role edit allows zero roles; staff create still requires one role

**Status:** Accepted
**Date:** 2026-06-11

### Decision

Staff profile edit may leave a staff member with zero operational roles.

Add Staff / staff creation continues to require at least one role.

This asymmetry is intentional.

### Behaviour

When a staff member has zero roles:

* staff profile displays “No role”
* the staff member remains manually schedulable in rota
* the staff member may be skipped by role-constrained rota recommendations
* no backend block is added

### Rationale

Backend and employee profile flows already support empty role lists. Edit needs to support cleanup/correction of operational labels without forcing an artificial role. Create still requires at least one role to keep onboarding structured.
---
## D046 — Staff location and role changes are future-facing and no-cascade

**Status:** Accepted
**Date:** 2026-06-11

### Decision

Staff location transfers and staff role changes affect future scheduling eligibility and recommendations only.

They must not cascade into existing shifts.

### Behaviour

When staff home store changes:

* future rota dropdown eligibility follows the new home store
* existing shifts remain assigned and unchanged

When staff roles change:

* future role matching/recommendations use the updated roles
* existing shifts remain assigned and unchanged
* removing a role must not cancel, unassign, reassign, delete, or regenerate shifts

### Rationale

Existing rota assignments are historical/operational records. Changing a staff profile rule should not silently rewrite already-created shifts. Any shift correction should be an explicit rota action, not a side effect of staff profile editing.
---
## D047 — Source 1 admin rota-generation inputs closed for MVP

**Status:** Accepted
**Date:** 2026-06-11

### Decision

Source 1 — the standing, admin-set inputs that rota generation depends on — is closed for MVP rota feasibility.

### Source 1 includes

Standing admin-set Source 1 inputs are:

* site/store setup
* staff profile safe operational fields
* staff home store/location
* staff operational roles
* weekly/monthly working-hour soft caps

These are editable and sufficient for MVP rota feasibility.

### Not Source 1

Availability, leave, cover, swaps, and requests are Source 2: per-period or staff-generated constraints.

Labour/rota summary, monthly soft-cap progress, and reports are downstream reporting/output surfaces, not rota-generation inputs.

### Pay/costing deferral

Pay, base-hours threshold, overtime rate, overtime eligibility, and cost-aware rota generation are deferred to a future owner-only pay-rules/costing phase.

MVP rota value is feasibility and hour-cap compliance, not cost optimisation.

Pay remains sensitive and owner-only.

### Next step

Proceed to `Availability.0` read-only inspect for Source 2.
---
## D048 — Availability source-of-truth and admin replace-week MVP

**Status:** Accepted
**Date:** 2026-06-13

### Decision

Availability is Source 2: a per-period rota constraint that feeds rota recommendations.

For MVP, availability is person-scoped and keyed by staff `user_id`, not `employee_account_id`.

### Availability scope

Availability represents a staff member’s availability calendar.

The canonical identity is:

* `tenant_id`
* `user_id`
* `date`
* availability slot/type

`store_id`, `site_id`, and `employee_account_id` may exist as nullable metadata, but they are not the source-of-truth identity for admin-set availability.

### Canonical uniqueness

Availability uniqueness is user-based and uses NULL-safe partial indexes for:

* full-day rows
* timed rows

This avoids the old mismatch where database uniqueness was based on `site_id` / `employee_account_id`, while application behaviour used `store_id` / `user_id`.

### Provenance

Availability rows include nullable `source` provenance.

Current sources:

* `admin`
* `employee`

Provenance is recorded for future admin/employee precedence work, but precedence logic is deferred.

### Admin replace-week rule

For MVP, admin availability editing uses a replace-week model.

Admin replace-week is authoritative for the selected staff member and selected week.

Saving admin availability for a week replaces existing availability rows for that staff member/week, including rows originally set by the employee.

The UI must warn the admin before saving.

### MVP UI semantics

The admin MVP is binary:

* Available = submit a full-day `type="available"` row
* Unavailable = submit no row for that date

This matches the current recommendation engine behaviour:

* `available` / `available_extra` = eligible
* `preferred_off` / `unavailable` / no row = skipped

`available_extra`, `preferred_off`, timed windows, notes, recurring availability, and precedence/merge logic are deferred.

### Leave remains separate

Leave, cover, and swap workflows remain separate through request/shift workflow tables.

Availability must not become a second writer of leave.

Approved leave may be derived read-only later if needed.

### Deferred decisions

The following remain future product decisions:

* employee/admin precedence and merge rules
* recurring/default availability
* timed availability windows in admin UI
* notes in admin UI
* whether `available_extra` and `preferred_off` should affect recommendation scoring
* how recommendation reasons such as `over_weekly_soft_cap` should be surfaced in admin UX

---
## D049 — StaffProfile weekly soft caps are recommendation warnings, not hard gates

**Status:** Accepted
**Date:** 2026-06-14

### Decision

`StaffProfile.weekly_working_hour_soft_cap` is operational guidance for recommendations, not a hard scheduling gate.

When a staff member would exceed their StaffProfile weekly soft cap, rota recommendations should:

* keep the otherwise eligible candidate available for recommendation
* attach the candidate reason `over_weekly_soft_cap`
* rank/deprioritise that candidate behind under-cap candidates

`HourTarget.max_hours` remains the hard weekly override/limit when present. If a candidate would exceed `HourTarget.max_hours`, the candidate is excluded by the recommendation engine.

### Rationale

StaffProfile weekly and monthly soft caps are Source 1 operational guidance. They should warn and shape recommendations, but must not block operations when no better eligible staff member exists.

HourTarget is the per-week exception/override layer and remains stricter than standing StaffProfile guidance.

### Follow-up

Recommendation UX should surface `over_weekly_soft_cap` and other recommendation reasons clearly enough for admins to understand why a candidate was ranked or flagged.

---
## D050 — Recommendation draft is a point-in-time snapshot

**Status:** Accepted
**Date:** 2026-07-20

### Decision

A rota recommendation draft is a point-in-time snapshot for one store and week.

Recovery from stale or empty recommendation drafts is via explicit discard/regenerate, not automatic refresh.

### Current behaviour

`POST /api/v1/rota-recommendations` creates a draft once for a store/week. If an active draft already exists, the create endpoint returns `ROTA_RECOMMENDATION_DRAFT_EXISTS`; the Admin Rota UI reloads the existing draft instead of replacing it.

If the draft was created before open shifts and availability were complete, it can legitimately capture an empty or stale state.

### Rationale

Automatically refreshing or replacing the draft on every Generate click would silently discard manager review state.

Keeping the snapshot explicit makes the workflow auditable and predictable:

* generate draft
* review draft
* discard/regenerate if source inputs changed
* apply recommendations when ready
* publish rota separately

Apply and Publish remain deliberately separate steps.

### Implementation note

RecommendationUI.3 added in-app discard/regenerate recovery for stale or empty drafts without changing backend draft semantics.

---
## D051 — Recommendation regenerate uses discard-then-create over HTTP

**Status:** Accepted
**Date:** 2026-07-20

### Decision

The current frontend regenerate workflow uses `discard -> create -> load` rather than a single atomic create/replace HTTP call.

### Current contract

The backend service function `create_rota_recommendation_draft_detail` has a `replace_existing_draft` parameter.

The public HTTP create schema is `DraftCreate`, which uses `extra="forbid"` and exposes only:

```text
store_id
week_start
```

Therefore `replace_existing_draft` is not part of the public `POST /api/v1/rota-recommendations` contract.

### Rationale

RecommendationUI.3 is a frontend-wiring phase over existing endpoints. It must not invent an unverified backend contract or widen the public create payload.

### Known limitation

The current regenerate flow is non-atomic. If discard succeeds and the subsequent create/load fails, the manager may be left with no active recommendation draft. The frontend shows a safe error, but a future dedicated atomic regenerate endpoint could close this partial-failure gap.

---
## D052 — Demand generation uses operational work areas and safe lineage-aware reconciliation

**Status:** Accepted
**Date:** 2026-07-22

### Work-area meaning

A work area is site-scoped operational context attached to coverage demand and generated shifts. It is not RBAC, a staff permission, or a recommendation matching input. `required_role` remains the separate candidate-matching field; Coverage.1a does not change recommendation scoring or candidate selection.

Work areas are soft-deactivated. Active coverage templates may reference only an active work area in the same tenant and site, and a work area cannot be deactivated while an active template references it. Coverage templates are also soft-deactivated so generated-shift lineage remains intact.

### Regeneration classification and reconciliation

Pre-provenance shifts are classified as `legacy_untracked`, not `manual`. They are always preserved and never satisfy template demand.

A shift is replaceable only when all of these are true:

* `source = demand_generation`
* `status = scheduled`
* it is unassigned and unpublished
* both role and availability override flags are false

Replaceable shifts are soft-superseded to `cancelled`; they are never hard-deleted. All other active generated shifts are kept. A kept generated shift satisfies an occurrence only when template ID, UTC start/end, normalized role, and work area all match. Matching kept shifts satisfy demand only up to the desired headcount; excess matches and all mismatches are reported as conflicts. Manual and `legacy_untracked` shifts are preserved conflicts and do not suppress demand creation.

### Recommendation snapshot exception

Demand regeneration deliberately discards an active recommendation draft for the same site and week when that draft is visible inside the regeneration transaction. The discard is atomic with shift reconciliation, generation-run creation, and audit records. This is a narrow exception to D050 because regeneration replaces the underlying shift set itself, unlike ordinary manager review.

### Transaction and concurrency boundary

Generate Week executions for the same tenant, site, and week are serialised by a deterministic PostgreSQL transaction advisory lock. Generation loads active templates, row-locks all shifts that feed reconciliation, and then row-locks an active recommendation draft visible to its transaction before validation or mutation. Shift supersession, new shifts, generation-run creation, a visible draft's discard, and audit records commit or roll back together. SQLite has only the test-dialect fallback and does not prove PostgreSQL concurrency; a PostgreSQL-backed two-transaction test covers the Generate Week lock boundary.

Recommendation-draft creation does not currently acquire the same tenant/site/week advisory lock as Generate Week. Regeneration atomically discards any active draft visible to its transaction, but invalidation against a draft created concurrently remains best-effort. Coverage.1a does not implement atomic discard-and-recreate and does not close H091.

### Provenance limitation

Coverage.1a records shift-to-run and shift-to-template LINEAGE. It does not store an immutable per-run snapshot of template inputs; editing a template later changes the values that ID resolves to. Historical timing/role/work-area values remain on the shift itself. Full run-input reproducibility is a future provenance enhancement.

---
## D053 — Staff are one employment per tenant; hours and pay thresholds are person-level, attribution is store-level

**Status:** Accepted
**Date:** 2026-07-26

### Context correction

The first customer was previously understood as one store containing three businesses: Greggs, Burger King, and convenience. That understanding was wrong. They are three separate stores under one tenant, each with its own manager, staff, rota, and coverage rules.

The existing store-scoped design is therefore already correct. Coverage.1a `work_area_id` remains nullable and tag-only and is not used by this customer.

### Decision

A person employed by a tenant has one staff profile regardless of how many stores they work at. Multiple per-store identities for the same person are explicitly rejected.

Hours and pay thresholds are calculated per person across all stores. Cost attribution and operational views remain per store.

### Rationale

The stores belong to one company, so this is a single employment. Fragmenting a person into per-store records miscalculates pay: 50 hours at Store A plus 40 hours at Store B plus 30 hours at Store C appears as three sub-threshold totals, so a 100-hour monthly threshold is never crossed and the employee is underpaid.

The existing `uq_staff_profiles_tenant_user` constraint already enforces one staff profile per person per tenant.

### Locked semantics

* Qualifying hours are published scheduled hours: `status == 'scheduled' AND published_at IS NOT NULL`. Draft or unpublished shifts create no pay liability because planning must not move a person's pay totals. Cancelled and superseded shifts are excluded.
* The hours basis is scheduled, not actual. A shift scheduled from 06:00 to 15:00 counts as nine hours regardless of attendance. Clocked hours are future work.
* The period is the calendar month in the tenant payroll timezone: Europe/London for the UK-first MVP. It is not a custom 26th-to-25th period. Thresholds and pay use the same monthly window.
* Attribution is chronological by shift start time, tie-broken by shift ID. Monthly hours accumulate across stores; the store whose shift crosses the threshold bears the split, including a split within one shift.
* Overlapping shifts must be detected and surfaced for human resolution, never silently summed. For example, 09:00–17:00 at Store A plus 12:00–20:00 at Store B must not produce 16 paid hours across an 11-hour elapsed period.
* `monthly_threshold_hours` is tenant-level policy. Standard `hourly_rate` and `overtime_rate` are employee-level. `hourly_rate` and `pay_type` already exist on `staff_profiles` and remain owner-only under the existing Staff.2/Staff.2b protections. Employees may legitimately have different rates. Hours remain operational and scheduler-visible; money remains owner-only.
* Employment identity is separate from portal credentials. D053 does not decide between one tenant-level employee login with selectable stores and store-specific accounts linked to one staff profile. That remains part of the H085 identity seam.

### Existing decision boundary

D053 partially overrides the employment-identity and single-home-store assumptions in D004, D007, D015, D016, D046, and D047. Those entries remain unchanged for historical context.

Current site-scoped employee portal credentials and endpoint scopes are not silently redesigned by this decision. D053 establishes one tenant-level employment profile and leaves the future credential model to H085.

### Product positioning

The system is a calculator. The tenant configures all thresholds and rates and is responsible for its own pay decisions. The product does not hardcode statutory rates or provide pay or legal advice.

### Consequences

* Multi-store assignment and cross-store aggregation must be implemented before any earnings, payroll, or pay-facing feature.
* Operational rota and coverage views remain store-scoped even when a person works across stores.
* Pay calculations must not use per-store staff identities or mutable current profile values to reconstruct closed historical periods.

---
## D054 — Site-local wall-clock times are stored as UTC-labelled timestamps

**Status:** Accepted (temporary simplification, exit condition recorded)
**Date:** 2026-08-11

### Decision

All scheduling times in the system are site-local wall-clock times. Where those times are
stored in a `TIMESTAMP WITH TIME ZONE` column, the `+00:00` offset is a storage label, not
a timezone conversion. No writer converts between local time and UTC.

### Verified writers (2026-08-11)

* Rota generation: `apps/api/routers/rota.py` builds `Shift.start_at` / `Shift.end_at` with
  `datetime.combine(date, template.start_time, tzinfo=timezone.utc)` from a coverage
  template's local `TIME`.
* Frontend: `admin-shell.tsx::buildShiftDateTime` uses `Date.UTC(...)`, and
  `formatTimeInputValue` reads back with `getUTCHours()`.
* Availability: `availability_entries.start_time` / `end_time` are bare `TIME` values
  compared directly against `_as_utc(shift.start_at).time()`.

All three agree. Because nothing converts, the system is internally consistent and displays
correctly year-round, including across BST transitions.

### Why this is acceptable now

The first customer operates three sites in a single timezone. Real timezone handling would
add conversion logic, a per-site timezone field, and DST-boundary complexity for no current
benefit.

### What this convention assumes

1. Every site in a tenant shares one timezone.
2. No system outside ForecourtOS reads `start_at` / `end_at` and interprets the `+00:00`
   offset literally.

Assumption 2 is the more dangerous one. An external consumer treating these as true UTC
would read every BST-period shift as one hour earlier than scheduled. In a payroll or
hours-worked context that is a pay error, not a display error.

### Exit condition

Revisit this decision when either occurs:

* A tenant operates sites in more than one timezone, or
* Any external system — payroll export, EPOS integration, reporting tool, customer-facing
  API — consumes `start_at` / `end_at` directly.

### Migration direction if triggered

Add a per-site timezone (IANA identifier), convert at the boundary rather than in domain
logic, and backfill existing rows using the tenant's single timezone, which is unambiguous
precisely because this constraint held. The constraint is what makes the future migration
tractable.

### Developer-facing placement

This convention is recorded in `docs/AI_WORKFLOW.md` and `README.md`. When Availability.1
consolidates the duplicated `_availability_covers_shift` into a single shared helper, the
convention must also be stated in that helper's module docstring, which is the closest
point to the code that would break it.

### Not decided here

Availability window semantics — full containment, overnight handling, and contradictory
rows — are recorded separately in D055 and D056.

---
## D055 — Availability.1 declared-availability semantics

**Status:** Accepted
**Date:** 2026-08-13
**Supersedes:** D048's deferred status for timed windows and declaration-type semantics,
and D048's earlier recommendation semantics where they conflict with this decision. D048
otherwise remains in force, including person-scoped availability on `user_id`, source
provenance, and the current admin replace-week authority.

### Context

Availability.1 introduces timed employee availability. Four declaration types already exist
(`available`, `available_extra`, `preferred_off`, `unavailable`) but their semantics were
never decided. Current matching behaviour is an artefact of implementation, not a product
choice: `unavailable` and `preferred_off` rows are never loaded, full containment is
required, and cross-midnight handling is inconsistent.

These six rules settle the weekly declared-availability layer only. They do not settle the
standing-agreement layer, cross-source precedence, or overnight implementation. See
`docs/design/availability_product_area.md` for the wider proposed design, which is NOT
adjudicated.

### 1. Declaration type semantics

| Type | Automatic assignment |
|---|---|
| `available` | Eligible |
| `available_extra` | Eligible |
| `preferred_off` | Eligible, deprioritised in ranking |
| `unavailable` | Not eligible |
| No applicable declaration | Not eligible |

`preferred_off` reduces desirability without removing eligibility. If two candidates are
otherwise equal and one is `preferred_off`, prefer the other. If only the `preferred_off`
candidate can cover, they may still be recommended, with the preference shown.

`unavailable` is decisive for automatic assignment. It must never be silently overridden to
make a rota fillable. Manual assignment despite `unavailable` is an explicit, reasoned,
auditable override.

### 2. `available_extra` carries no ranking advantage

`available_extra` ranks equally with `available` for recommendation purposes. It remains a
distinct self-declared hard-positive type. Availability.1 does not infer or verify what
makes that availability "extra"; a future standing scheduling baseline may give the
distinction system-level meaning.

Rationale:

1. Automatically favouring whoever volunteers extra would systematically load more shifts
   onto the most flexible employees. In a site mixing fixed-pattern and flexible staff, the
   flexible staff would absorb every awkward slot, and the incentive to volunteer would
   disappear.
2. There is no authoritative standing pattern today, so the system cannot establish that any
   declaration is genuinely beyond someone's normal availability.
3. No ranking effect has been deliberately justified.

The scheduler may still select that person. The engine must not select them automatically on
that basis.

### 3. Full containment required for eligibility

A timed availability window must fully contain the shift:
`entry.start_time <= shift_start AND entry.end_time >= shift_end`.

Availability 09:00–17:00 does not make an employee eligible for an 08:00–16:00 shift,
because they cannot work the whole shift.

Partial overlap remains useful information for feasibility display and possible future
split-shift coverage. Eligibility and useful overlap are different concepts.

The recommendation engine and manual assignment validation use the same rule, so the two
matchers can never disagree. Manual assignment outside a declared window is an explicit
override.

### 4. Same-source contradiction is rejected at write time

Declaration types compose by effective strength, not by whichever row the database returns
first.

| Overlapping pair, same source | Effective outcome |
|---|---|
| `available` + `preferred_off` | Eligible, deprioritised |
| `available_extra` + `preferred_off` | Eligible, deprioritised |
| `preferred_off` + `unavailable` | Not eligible; `preferred_off` remains explanatory |
| `available` + `unavailable` | Rejected at write time |
| `available_extra` + `unavailable` | Rejected at write time |
| Multiple non-conflicting windows on one date | Allowed; compose normally |

Rule: a single writer may not create overlapping hard-positive and hard-negative
declarations for the same availability subject and applicable scheduling scope.

Deliberately not phrased as "person, site, and time interval": D048's canonical availability
identity is person-scoped on `tenant_id + user_id + date + type`, and `site_id` is not part
of that identity.

**This governs contradiction within one writer only.** Competing declarations from different
authorities are a precedence question, not a contradiction, and remain governed by D048.

### 5. No-declaration semantics, weekly layer only

> In the weekly declared-availability layer, no applicable declaration does not establish
> eligibility. An applicable declaration establishes eligibility according to its type
> semantics.

Not "no row means unavailable." No declaration and explicit `unavailable` currently produce
the same automatic-assignment outcome, but they are different business facts and must remain
distinguishable: "James declared unavailable" and "James has not submitted availability"
lead to different managerial actions.

Scoped to the weekly layer so a future standing-availability layer may evaluate: weekly
declaration exists → apply weekly semantics; no weekly declaration → consult the standing
baseline. That adds a source before the final eligibility decision rather than contradicting
this decision.

### 6. Overnight availability remains unsupported

`_validate_availability_payload` rejects `end_time <= start_time`, so a timed 22:00–06:00
availability window cannot currently be expressed. **Availability.1 retains that validation
and does not introduce overnight timed availability.**

Cross-midnight matching is not settled by this phase. The existing matcher has incomplete
legacy behaviour: timed rows are skipped for cross-midnight shifts, while a full-day row on
the shift's start date can match before that check is reached. Availability.1 must not
promote that behaviour into accepted product semantics.

Semantic direction recorded for the future overnight phase:

> An overnight shift is eligible only when availability continuously covers the complete
> shift interval across the relevant calendar dates.

Representation and matching must be designed together with Coverage.1b or a dedicated
overnight phase. Availability.1 must not simulate overnight support by splitting a window at
midnight merely to bypass the current `TIME` validation. This does not forbid a future
overnight design from choosing a multi-segment representation if proper design finds it
cleanest.

### Not decided here

- How standing and weekly availability compose.
- Cross-source precedence, and whether admin authority must remain destructive. D048's
  destructive replace-week stands as current behaviour. Availability.1 tests may preserve
  the current API contract but must not assert that destructive replacement is desirable
  product behaviour.
- Feasibility reporting categories and presentation.
- Standing agreement shape, scoping, versioning, or change lifecycle.
- Cross-site conflict surfacing, which is blocked on H094 regardless.

### Test to apply to any future availability rule

> Can the proposed rule explain why the site is impossible to staff, without silently
> violating what employees told us?

---
## D056 — Availability.1 amendments from second-pass code inspection

**Status:** Accepted
**Date:** 2026-08-13
**Amends:** D055. D055 remains in force except where this decision modifies it.

### Why this exists

D055 was accepted on 2026-08-13 based on the inspection of 2026-08-11. A second,
deeper inspection established two live behaviours that D055 assumed differently.
Rather than editing accepted history, those corrections are recorded here.

D055 assumed cross-source availability conflicts could not persist, because admin
replace-week deletes employee rows. Verified: an employee can write again after an
admin replacement, leaving `source="admin"` and `source="employee"` rows coexisting.
This is invisible today because the matcher loads only positive types, but
Availability.1 loads all four.

D055 also required manual assignment outside availability to be explicit, reasoned,
and auditable. Verified: the live admin UI does not use the override-aware assign
endpoint at all. Create-shift and update-shift bypass the override machinery and can
persist `availability_override = False` for an override that actually occurred.

### 1. Candidate ranking order

Amends D055 rule 1, which said only that an otherwise-equal `preferred_off`
candidate should be passed over. That wording read as a tie-break. It is not.

**Hard exclusions, evaluated before ranking:**

- Role mismatch
- `unavailable`
- No applicable declaration
- Unresolved cross-source hard conflict (rule 2)
- HourTarget hard maximum

**Ranking of eligible candidates, in order:**

1. Not over the weekly soft cap
2. Not `preferred_off`
3. Existing below-min / below-target / lowest-hours score
4. Projected hours
5. Deterministic tie-break

The soft-cap class remains stronger than `preferred_off`. A candidate who stated a
preference will still be recommended ahead of one who is over their soft cap.

Worked examples:

| Alice | Bob | Recommended |
|---|---|---|
| `available`, under cap | `preferred_off`, under cap | Alice |
| `available`, over soft cap | `preferred_off`, under cap | Bob |
| excluded | `preferred_off`, only candidate | Bob, with `preferred_off` in the reason |

Rationale for the second row: `preferred_off` is a preference, not a prohibition.
Pushing an employee further over their hour cap to honour someone else's preference
is the worse outcome, and the soft-cap class already has categorical priority.

Consequence, accepted deliberately: an employee who marks `preferred_off` will still
be scheduled when the alternative is over their cap. The preference must therefore be
visible in the recommendation reason, so a human can notice a repeating pattern.

### 2. Unresolved cross-source conflict fails closed

Where overlapping declarations from **different sources** produce incompatible hard
states, and no adjudicated precedence rule resolves them, automatic assignment must
fail closed for that interval. The candidate remains unassigned and the conflict is
represented explicitly.

Qualifying combinations — any cross-source hard-positive against hard-negative:

- admin `unavailable` + employee `available`
- admin `unavailable` + employee `available_extra`
- admin `available` + employee `unavailable`
- admin `available_extra` + employee `unavailable`

`preferred_off` is a soft signal and does not create a conflict. Admin `available`
plus employee `preferred_off` is a coherent state: management says this is a working
period, the employee would rather it were not.

**Availability.1 must not infer source precedence from row order, timestamps,
declaration type, or writer role.** Any of those would settle the precedence phase by
accident.

**The conflict must carry its own reason code, distinct from `unavailable`.**

```text
unavailable      → excluded because the employee is declared unavailable
source_conflict  → excluded because no trustworthy effective state can be established
```

The distinction matters for Feasibility.1. A manager must see "conflicting admin and
employee declarations" rather than "James is unavailable," which would falsely
attribute the outcome to one party.

The authoritative resolution of cross-source precedence remains deferred to a
dedicated precedence phase.

### 3. Manual override enforcement is deferred

D055's requirement that manual assignment outside declared availability be explicit,
reasoned, and auditable **remains target product semantics and is not withdrawn.**

Its enforcement moves out of Availability.1 into a dedicated phase,
**Availability.Override.1**, because satisfying it requires converging four
assignment paths (create shift, update shift, the dedicated assign endpoint, and the
admin frontend), deciding whether a reason becomes mandatory, and adding a
frontend acknowledgement flow. That is an assignment-API and frontend workflow phase,
not an availability-matcher phase.

Two constraints on Availability.1 in the meantime:

- Availability.1 **must not make the existing override false-negative worse**, and
  must not imply through code, tests, or documentation that manual assignment now
  obeys D055 when it does not.
- Availability.1 **must not claim manual-override compliance is complete.**

### Not decided here

- Cross-source precedence itself. Deferred to the precedence phase.
- Submission windows, availability deadlines, publication timing, and standing
  scheduling baselines. These surfaced during design discussion on 2026-08-13 and are
  recorded in `docs/design/availability_product_area.md` as **proposed only**. They
  are not required to implement Availability.1 and must be independently adjudicated
  when Availability.2 begins.
- What effect changing availability after a rota is published should have.

---
## D057 — Availability.1a implementation-forced availability rules

**Status:** Accepted
**Date:** 2026-08-15
**Relates to:** D048, D054, D055, D056. This entry amends none of them. It records rules
none of them decide, but which Availability.1a cannot be implemented without.

**Contains one deliberate behaviour change.** Rule 6 ends existing cross-midnight matching
behaviour. It is not a refactor side effect. See rule 6.

### Why this exists

The Availability.1a implementation prompt contained rules that read as instructions but
function as product decisions. Presented in the same voice as the adjudicated D055/D056
rules and unmarked, they would have been implemented, locked green by tests, and become de
facto product truth without ever being adjudicated — the documentation-laundering pattern
`CLAUDE.md` forbids, relocated from `DECISIONS.md` into a prompt, where it is harder to see
because a prompt reads as instructions.

This entry names them so they are adjudicated on their merits.

### Already settled elsewhere — deliberately not restated

- **Manual assignment and recommendations must use one matcher.** D055 rule 3 already
  states both use the same rule so they can never disagree. The consequence — that manual
  assignment's availability determination necessarily changes once the shared evaluator
  lands, so it cannot be described as behaviourally unchanged — follows from D055 and is
  not a new decision.
- **`preferred_off` remains explanatory when a candidate is excluded.** D055 rule 4's table
  already requires it in the `preferred_off + unavailable` case. The evaluator's internal
  data shape is implementation, not decision.

---

### 1. Non-positive declarations apply to a shift by overlap

A hard-negative (`unavailable`) declaration overlapping any part of a shift excludes the
candidate from the whole shift. A soft (`preferred_off`) declaration overlapping any part of
a shift marks the whole proposed assignment as `preferred_off`. Hard-positive declarations
continue to require full containment, per D055 rule 3.

**Why this had to be decided.** D055 rule 3 defines applicability for positive windows only —
a window must fully contain the shift to establish eligibility. It says nothing about what
makes a negative or soft window applicable. For full-day rows the answer is obvious; for
timed rows it was undefined. Without this rule an `unavailable` 12:00–13:00 against an
09:00–17:00 shift has no defined outcome and the evaluator cannot be written.

**Rationale.** The asymmetry is the point: an employee must be available for **all** of a
shift, but a conflict during **any** part of it makes the whole shift unworkable.

**Rejected.** Requiring containment for negatives. An `unavailable` 12:00–13:00 would then
fail to exclude an 09:00–17:00 shift, recommending someone the system has been told cannot
work part of it. That inverts the safety property D055 rule 1 gives `unavailable`.

### 2. Overlap is half-open

Two intervals overlap when `a.start < b.end AND b.start < a.end`. Adjacent windows such as
09:00–12:00 and 12:00–17:00 therefore do **not** overlap. A full-day row — both times NULL —
overlaps every shift and every timed row on its date.

**Why this had to be decided.** D055 rule 4 rejects "overlapping hard-positive and
hard-negative declarations" without defining overlap, and rule 1 above needs the same
primitive. Under a closed-interval reading, `available` 09:00–12:00 and `unavailable`
12:00–17:00 would be a write-time contradiction and rejected; under half-open they are two
coherent adjacent declarations. Whether an employee can express that pair is a
product-visible consequence of an otherwise unstated definition.

**Rationale.** Half-open matches how this codebase already treats time windows. The
availability date window is half-open — `week_start <= date < week_start + 7`, locked by
H088a — as is the recommendation week-bounds helper. One definition serves both shift
applicability and contradiction detection.

**Rejected.** Closed intervals, which would turn ordinary back-to-back declarations into
spurious contradictions and force employees to express artificial gaps.

### 3. Multiple positive windows do not stitch

At least one hard-positive row must **independently and fully** contain the complete shift.
Two adjacent positive windows that jointly cover it do not establish eligibility.
`available` 09:00–12:00 plus `available` 12:00–17:00 does not make a candidate eligible for
an 09:00–17:00 shift.

**Why this had to be decided.** H088b explicitly carries "multiple windows per date" into
this phase. D055 rule 3 is phrased in the singular — "A timed availability window must fully
contain the shift" — but never says whether several may compose.

**"Compose normally" does not authorise stitching.** D055 rule 4's table row "Multiple
non-conflicting windows on one date | Allowed; compose normally" governs *coexistence*: several
compatible declarations may exist on one date and their meanings compose according to their
type semantics. It does not union adjacent intervals into one virtual availability window.
Interval stitching would require a deliberate amendment to D055 rule 3.

**Rationale.** This is the narrowest reading of the accepted rule and avoids inventing
interval-union logic that nobody has reviewed.

**Rejected.** Interval union across adjacent positives. It may well be what employees expect,
but expanding eligibility is a change that must be made deliberately with its own tests, not
inferred from an ambiguous four-word table cell.

### 4. Historical same-source contradictions fail closed, kept distinct

Where a same-source hard-positive and hard-negative overlap is found at read time, the
candidate is not automatically assignable. The state is represented distinctly from
`source_conflict`. No new persisted admin-facing reason code is added in this phase; the
shift retains `no_eligible_candidate`.

**Why this had to be decided.** D055 rule 4 rejects these at *write* time only. Rows already
persisted — through the generic availability route, or predating the invariant entirely — are
unaffected by a new write-time check. The evaluator will encounter a state D055 says cannot
exist and needs defined behaviour for it. Without this rule it would either fail or silently
pick whichever row the database returned first, which is precisely the failure mode D055
rule 4 exists to prevent.

**Rationale.** `source_conflict` has a specific meaning in D056 rule 2 — conflicting hard
states from *different* sources, where no adjudicated precedence rule resolves them. Reusing
it for corrupt or legacy same-source data would erase the distinction Feasibility.1 depends
on, and would tell a manager that two authorities disagree when in fact one authority's own
data is incoherent.

**Rejected.** Folding it into `source_conflict`; and treating it as an ordinary `unavailable`,
which would attribute a data-integrity fault to the employee.

### 5. NULL-source contradictions fail closed as unknown provenance

Where contradictory hard declarations involve one or more rows with `source IS NULL`, the
candidate fails closed under unknown provenance. This is not recorded as `source_conflict`,
and the shift retains `no_eligible_candidate`.

**NULL provenance alone does not invalidate a declaration.** A lone NULL-source row of any
type carries its ordinary type semantics: a NULL-source `unavailable` excludes normally, a
NULL-source `available` establishes eligibility normally. Unknown-provenance handling applies
**only** where contradictory hard facts require deciding whether a conflict is same-source or
cross-source.

**Why this had to be decided.** D048 records `source` as nullable provenance. D056 rule 2's
four qualifying combinations name `admin` and `employee` explicitly, so a NULL-source row
matches neither side. Availability.1a is the first phase to load all four declaration types,
so it is the first that can meet the case.

**Rationale.** We cannot truthfully assert that a NULL-source row shares a source with
another row, nor that it differs. Both `source_conflict` and a same-source label would be
claims the data does not support. Failing closed under an honestly-labelled unknown avoids
asserting either.

**Rejected.** Treating NULL as a distinct third source, which would manufacture cross-source
conflicts from provenance we do not have; and treating NULL as matching whatever it is
compared against, which makes the outcome depend on comparison order — the thing D056 rule 2
forbids.

### 6. Cross-midnight shifts fail closed in automatic matching

> **Availability.1a does not support automatic matching of cross-midnight shifts. Such shifts
> fail closed in the declared-availability evaluator until continuous multi-date availability
> is implemented.**

**This is a deliberate behaviour change, not a refactor side effect.** Today a full-day
availability row on a shift's start date can establish eligibility for a cross-midnight
shift. **That behaviour ends.** The system holds no evidence about the second calendar date
and never consulted it; recommending on that basis presents a guess as a recommendation.

Manual assignment through existing workflows is unaffected and remains the route for
overnight shifts until Coverage.1b.

**Why this had to be decided.** Cross-midnight shifts are reachable today. Shift-time
validation compares full datetimes and only requires `end_at > start_at`, so a manually
created 22:00→06:00 shift is valid, even though generated shifts cannot be overnight because
coverage templates reject `end_time <= start_time`. The evaluator will be handed one and must
return something. D055 rule 6 forbids promoting the legacy behaviour into accepted semantics
but does not say what the evaluator does.

**Superseded ruling.** An earlier site-dependent ruling — preserve current behaviour for
24-hour sites, fail closed otherwise — is **discarded**. It depended on a 24-hour site
indicator that does not exist. `stores` has no such field, and `store_opening_hours` enforces
`close_time > open_time` at both the database CHECK constraint and the API schema, so 24-hour
operation cannot be expressed at all. The discriminator could not be read because it cannot
be written.

**Rejected.** Preserving the legacy behaviour untested, which would carry an acknowledged
artefact forward into the new shared evaluator and leave the system recommending against
evidence it does not have.

### 7. The same-source contradiction invariant is transactionally serialised

D055 rule 4's prohibition must be enforced with serialisation sufficient that concurrent
writes cannot both commit a contradiction, using an established repository locking mechanism.

The serialisation key must use the **server's known writer identity**, not the nullable and
potentially client-influenced `source` column. Lock key and granularity are implementation
details to be settled by inspection, not by this decision.

**Why this had to be decided.** Neither D055 nor D056 mentions concurrency. A
check-then-insert implementation does not enforce the invariant: two concurrent same-source
writes each validate against the pre-insert state and both commit. The existing partial
unique indexes cannot catch it because they key on `type`, which differs between the two
rows. Without this rule D055 rule 4 is a best-effort check rather than an invariant, and
rule 4 above becomes a permanent live path rather than a legacy-data path.

**Rejected.** Deferring to a hardening backlog item. Shipping a stated invariant with a known
race, in the same phase that states it, is the kind of shortcut D033 rules out for a
commercial product.

### 8. `source_conflict` is selected causally

> If a shift is unfilled **and** at least one candidate would otherwise have been eligible
> except solely for a qualifying cross-source hard conflict, the persisted reason is
> `source_conflict`. Otherwise it is `no_eligible_candidate`.

A candidate who also fails role matching, `HourTarget` maximum, or any other exclusion must
not relabel the shift.

**Why this had to be decided.** D056 rule 2 requires the conflict to carry a distinct reason
code but does not say how the code is selected when several candidates fail for different
causes. `RotaRecommendationItem.reason` is a single nullable string, not a list, so the engine
must choose one value. Without this rule any incidentally-conflicted person anywhere in the
candidate pool could relabel an unfilled shift, telling a manager that cross-source conflict
was the cause when it was not.

**Rejected.** Accumulating multiple codes, which the single-column model does not support; and
letting any conflicted candidate set the reason, which breaks the causal attribution D056
rule 2 exists to protect.

### 9. Availability.1 splits into 1a and 1b

Availability.1a is backend-only: declared-availability semantics, write validation, and the
shared evaluator. Availability.1b adds the employee-facing `preferred_off` surface and follows
immediately. **Availability.1 is not complete until both land.**

**Why this had to be decided.** The employee availability client type carries only
`available | unavailable | available_extra`, and the admin availability UI writes full-day
`available` rows exclusively. On backend-only completion, `preferred_off` is reachable through
no UI at all, so D056 rule 1's ranking is dormant in production and exercised only by API and
tests. Recording the split makes that dormancy a scheduled gap rather than an unnoticed one.

**Rejected.** Folding the UI change into 1a, which would break the repository's own review
gate — no engine change in a UI phase, no UI change in an engine phase; and deferring
`preferred_off` UI indefinitely, which leaves the engine honouring a declaration employees
cannot make.

### Not decided here

- Cross-source precedence itself. Still deferred to a dedicated precedence phase, per D056.
- Whether adjacent positive windows should compose into continuous coverage. Requires an
  explicit amendment to D055 rule 3.
- Continuous cross-calendar-day availability matching. Deferred to Coverage.1b or a dedicated
  overnight phase, for all sites.
- How 24-hour site operation should be represented at all. Blocked identically in store
  opening hours, coverage templates, and availability. Tracked as H101.
- Whether the unknown-provenance and same-source-contradiction states should ever become
  admin-facing reason codes. That is Feasibility.1's call.

---
## D058 — Availability.1a contradiction scope and reason composition

**Status:** Accepted
**Date:** 2026-08-15
**Relates to:** D048, D049, D055, D056, D057. This entry amends none of them.

### Why this exists

Adversarial review of the Availability.1a implementation prompt surfaced two further
questions that D055, D056, and D057 do not answer, but which the phase cannot be
implemented without. Recording them in the prompt rather than here would repeat the pattern
D057 exists to prevent — on the eighth and ninth questions rather than the first seven.

Both are narrower than D057's rules. Neither changes an adjudicated outcome; each fixes the
*scope* over which an already-accepted rule applies.

---

### 1. Read-time contradictions are shift-local

A same-source contradiction (D057 rule 4) or an unknown-provenance contradiction (D057
rule 5) causes an evaluated shift to fail closed only where **both** of the following hold:

1. The contradictory hard declarations overlap **each other**, and
2. That contradictory interval intersects the evaluated shift's interval.

Contradictory declarations elsewhere on the same date do not cause an unrelated shift to
fail closed.

This scopes the **consequence of a contradiction during matching**. It does not redefine
whether the persisted data is contradictory. Such data remains invalid either way.

**The two-part test is deliberate.** It is not sufficient that one of the contradictory rows
touches the shift. The *overlap between the two declarations* is the interval that must
intersect it.

Worked example — a 09:00–17:00 shift, same source holding:

```text
available    09:00–17:00
available    18:00–20:00
unavailable  18:30–19:00
```

The contradiction is real and must still be rejected at write time, but the contradictory
interval is 18:30–19:00. It does not intersect 09:00–17:00, so the morning shift is
unaffected and the candidate remains eligible for it.

**This does not weaken D055 rule 4.** The write-time invariant is unconditional: a writer
must reject a prohibited same-source contradiction whether or not any shift exists, and
regardless of when any shift falls. Rule 1 governs only how an *already-persisted*
contradiction is evaluated against a specific shift at read time.

**Why this had to be decided.** D057 rules 4 and 5 establish that these contradictions fail
closed, but not what "closed" is scoped to. Two readings were equally available: any
contradiction anywhere on the date poisons every shift that day, or the contradiction must
intersect the shift being evaluated. The difference is directly visible to a manager — under
the first reading, corrupt evening data silently removes a candidate from a morning shift.

**Rationale.** D056 rule 2 already scopes cross-source conflict this way, requiring automatic
assignment to "fail closed for that interval." Rule 1 brings D057 rules 4 and 5 into line
with the scoping the architecture already uses for the cross-source case, rather than
introducing a new principle. Applying a data-integrity fault beyond the interval it affects
would present to a manager as the availability engine mysteriously dropping people, with no
visible cause on the shift in question.

**Rejected.** Date-wide poisoning, which over-applies a data-integrity fault well beyond the
interval it affects, and would let one corrupt evening row remove a candidate from every
shift that day.

### 2. Reason parts compose additively for selected candidates

For a **selected eligible candidate**, `preferred_off` is additive to the existing
recommendation reason parts. It does not replace `over_weekly_soft_cap`, `below_min_hours`,
`below_target_hours`, or any other applicable existing code. A candidate who is both over the
soft cap and `preferred_off` carries both.

**Boundary, stated explicitly to prevent an apparent conflict with D057 rule 8.** This rule
governs the reason parts on a **selected** candidate. D057 rule 8's single-value causal
selection governs the reason on an **unfilled** shift. These are different cases and are not
contradictory.

```text
selected candidate   → all applicable reason parts survive     (this rule)
unfilled shift       → exactly one causal reason is chosen     (D057 rule 8)
```

**Literal ordering of reason parts is not a product rule.** The rule is that every applicable
code survives. The existing deterministic assembly convention is preserved as it stands.

**Why this had to be decided.** D049 requires `over_weekly_soft_cap` to be attached to a
recommended candidate who exceeds the soft cap. D056 rule 1 requires that a `preferred_off`
candidate's preference "must therefore be visible in the recommendation reason, so a human
can notice a repeating pattern." Neither addresses the case where both apply to the same
selected candidate, and the reason field is a single string. An implementer must decide
whether both survive or one wins.

**Inspection finding.** D049 is dated 2026-06-14 and never mentions `preferred_off`. It could
not have: D048, dated one day earlier, explicitly lists "whether `available_extra` and
`preferred_off` should affect recommendation scoring" among its deferred decisions.
`preferred_off` acquired ranking meaning only in D055 and D056, two months later. D049
therefore does not settle composition with it.

**Why this was recorded rather than left implicit.** The additivity alone is close to
derivable — two unconditional requirements, D049's "attach" and D056 rule 1's "must be
visible", both hold when both conditions apply, and satisfying both means both codes are
present. The boundary against D057 rule 8 is not derivable. D057 rule 8 introduces a
competing single-value discipline for the unfilled case, and an implementer could reasonably
over-apply that discipline to selected candidates and then be forced to choose between the
two codes. That boundary needs a durable authoritative record, not a note in a prompt.

**Review history.** GPT initially characterised this as following from D049 and D056 rather
than being a new decision, and subsequently withdrew that position. Neither decision
addresses the both-apply case, so it is recorded rather than assumed.

**Rejected.** Making the engine choose one code and discard the other, which loses
information a manager needs — either that a preference was overridden, or that a cap was
exceeded.

### No third question surfaced

Drafting was checked for further implementation-forced questions. None was found.
Specifically examined and resolved without new decisions:

- **What constitutes "the contradictory interval" when one declaration is full-day.** It is
  the intersection of the two declarations, which follows from rule 1's own wording combined
  with D057 rule 2, under which a full-day row overlaps every timed row on its date. Two
  full-day contradictory rows intersect across the whole date and therefore affect every
  shift that day, which is the intended outcome.
- **Whether `preferred_off` needs a reason representation for excluded candidates.** It does
  not. Recommendation items are per shift with a single proposed candidate; non-selected
  candidates have no persisted reason field. D055 rule 4's requirement that `preferred_off`
  remain explanatory on an excluded candidate is satisfied within the evaluator result, which
  D057's "already settled elsewhere" section records as implementation.
- **Whether rule 1 extends to cross-source conflict.** It does not need to. D056 rule 2
  already scopes that case to the interval explicitly.

### Closing condition

**D058 is the final decision entry before Availability.1a implementation.**

**Stopping rule.** A D059 during Availability.1a is permitted only if Step 0 inspection
proves either:

```text
A. an accepted D055–D058 rule is impossible to implement against live code, or
B. two accepted rules are mutually contradictory.
```

Everything else is deferred to a named follow-up rather than expanding Availability.1a.

A further implementation-forced question arising outside exceptions A and B is a signal to
reassess whether Availability.1a is correctly scoped, or whether the decisions are being
drafted too thinly. It is not an invitation to write D059.

### Not decided here

- The store scope at which availability rows are loaded for evaluation. D048 records identity
  as person-scoped with `store_id` as nullable metadata; D055 rule 4's phrase "applicable
  scheduling scope" gestures at it without defining it. Availability.1a preserves existing
  behaviour unchanged, which decides nothing. Natural home is the precedence phase or
  Feasibility.1.
- Everything already listed as undecided in D055, D056, and D057, unchanged.

---
## D059 — `preferred_off` does not independently establish eligibility

**Status:** Accepted
**Date:** 2026-08-16
**Amends:** D055 rule 1, for `preferred_off` only.
**Qualifies:** D056 rule 1.
**Leaves controlling and unchanged:** D057 rules 1 and 3; D055 rules 4 and 5.
**Invoked under:** D058 stopping-rule exception B — two accepted rules mutually contradictory.

### Why this exists

Two accepted rules govern the same case and cannot both hold.

D055 rule 1's table reads, unqualified:

```text
preferred_off → Eligible, deprioritised in ranking
```

D057 rule 3 reads, categorically:

> At least one hard-positive row must **independently and fully** contain the complete shift.

Where a candidate holds a lone `preferred_off` declaration and no applicable hard-positive,
D055 rule 1 says eligible and D057 rule 3 says not eligible. Both are Accepted. The
contradiction is genuine, not a matter of interpretation.

D057 rule 1 already supports the second reading through a deliberate verb choice:
hard-positive declarations *establish* eligibility by containment, while a soft declaration
*marks* the whole proposed assignment as `preferred_off`. Marking is not establishing. That
distinction was never made explicit enough to survive implementation.

### Recorded timing

**This was found during post-implementation adversarial review of the diff, not during
Step 0.** D058's stopping rule is phrased in Step 0 terms. The discovery does not fit that
phrasing, and it is recorded as it happened rather than restated to match. Exception B
applies in substance: two accepted rules are mutually contradictory. If the stopping rule's
Step 0 framing proves too narrow in practice, that is a defect in D058's wording to be
addressed on its own terms, not by misdescribing when a contradiction was found.

### How this entered

The v3.1 Availability.1a implementation prompt encoded the incorrect reading directly,
specifying `preferred_off → available` as an expected shift-side outcome. Codex implemented
what the prompt specified. The prompt survived two adversarial review passes with that line
intact.

This is the failure mode D057 exists to prevent: a product rule entering through a prompt
rather than through adjudication. It is recorded here so the pattern stays visible and is not
attributed solely to implementation. The prompt is where the defect originated; the code is
where it became observable.

### Structural note — amended from outside

D055 is **not** edited in place. It stands as accepted history and is amended from here,
following the D056 precedent. Editing accepted history would lose the explanation of why both
the implementation and the v3.1 prompt got this wrong, which is the part most likely to
prevent a recurrence.

---

### The rule

> `preferred_off` is a soft modifier only. It never independently establishes automatic
> eligibility. A candidate is automatically eligible only where at least one applicable
> hard-positive (`available` or `available_extra`) independently and fully contains the
> shift. Where eligibility is so established, an overlapping `preferred_off` keeps the
> candidate eligible but deprioritised, and remains explanatory state.

D057 rule 3 remains controlling and unchanged.

`preferred_off` remains orthogonal explanatory and ranking state, including on excluded
candidates, per D055 rule 4.

Where `preferred_off` applies but no hard-positive establishes eligibility:

```text
preferred_off only
→ eligible=false
→ preferred_off=true
→ exclusion_cause=no_declaration
```

`no_declaration` is read as **"no applicable eligibility-establishing declaration,"** not
literally "zero rows exist." No new exclusion cause is introduced; a `preferred_off_only`
category would create a public semantic the product does not need.

### This does not weaken D055 rule 5

D055 rule 5 requires "no declaration" and explicit `unavailable` to remain distinguishable,
because they are different business facts leading to different managerial actions. Reusing
`no_declaration` for the `preferred_off`-only case does not collapse that distinction,
because `preferred_off` is orthogonal state and remains set:

```text
(eligible=false, preferred_off=false, no_declaration)  → submitted nothing
(eligible=false, preferred_off=true,  no_declaration)  → submitted a preference only
(eligible=false, preferred_off=false, unavailable)     → declared unavailable
```

All three remain distinguishable in the evaluator result. D055 rule 5 is satisfied without a
new cause.

### Worked cases

| Declarations, shift 09:00–17:00 | Result |
|---|---|
| `available` 09:00–17:00 + `preferred_off` 12:00–13:00 | `eligible=true`, `preferred_off=true` |
| `preferred_off` 12:00–13:00 only | `eligible=false`, `preferred_off=true`, `no_declaration` |
| `available` 09:00–12:00 + `preferred_off` 12:00–13:00 | `eligible=false`, `preferred_off=true`, `no_declaration` |

The third case follows from D057 rule 3: the hard-positive does not contain the shift, so
nothing establishes eligibility, and the preference cannot supply it.

### What each affected decision now says

**D055 rule 1 — AMENDED for `preferred_off`.** The table row
`preferred_off → Eligible, deprioritised in ranking` is amended to soft-modifier-only. The
accompanying prose "If only the `preferred_off` candidate can cover, they may still be
recommended, with the preference shown" is amended in the same direction: "can cover" now
requires an applicable hard-positive. The rest of D055 rule 1 — the treatment of `available`,
`available_extra`, `unavailable`, and no-declaration — is untouched.

**This is an amendment, not a clarification.** Stated explicitly because leaving D055's
unqualified "preferred_off → Eligible" textually intact would keep the contradiction live for
every future reader, and this defect has already survived two review passes by looking like
settled text.

**D056 rule 1 — QUALIFIED, not amended.** Its ranking order and soft-cap priority stand
exactly as written. Under D059, D056 rule 1's "`preferred_off`, only candidate" example is
read as a candidate who **also** has an applicable hard-positive. The `preferred_off` cell
describes their ranking state, not their complete declaration set. **D056 did not state the
hard-positive; D059 supplies that prerequisite.** Recorded explicitly because that example
could otherwise be cited to resurrect exactly this defect.

**D057 rule 1 — CONTROLLING, unchanged.** Its establish/mark distinction is the correct
reading and is now explicit rather than implied by verb choice.

**D057 rule 3 — CONTROLLING, unchanged.** It is the rule that survives the contradiction
intact.

**D055 rules 4 and 5 — CONTROLLING, unchanged.** `preferred_off` remains explanatory on
excluded candidates; the no-declaration/unavailable distinction remains intact, as shown
above.

### Why the phase cannot proceed without deciding it

The evaluator must return a value for a lone `preferred_off` declaration. It cannot satisfy
both D055 rule 1 and D057 rule 3, so the contradiction must be resolved before the semantics
can be considered settled — regardless of which way it is resolved.

The live implementation currently takes the incorrect reading, so a candidate who declared
only "I would prefer not to work 12:00–13:00" is treated as eligible for a full 09:00–17:00
shift they never said they could work.

**The same reading has a second site.** D057 rule 8's causal reason selection depends on
whether a candidate "would otherwise have been eligible except **solely** for a qualifying
cross-source hard conflict." The implemented counterfactual treats a lone `preferred_off` as
satisfying that test, so a cross-source conflict touching a preference-only candidate can
relabel an unfilled shift `source_conflict` when no candidate was ever eligible. Remediation
must cover both the eligibility determination and the counterfactual test; fixing only the
first leaves D057 rule 8 wrong.

### Why severity rises when Availability.1b ships

The defective state is currently reachable only through the API and tests, because no user
interface can send `preferred_off` (D057 rule 9).

Availability.1b makes it declarable by employees. From that point, an employee selecting
"I'd prefer not to work 12:00–13:00" would silently mean "I affirm I can work this entire
eight-hour shift, but would rather not." Those are different declarations, and the system
would be recording one as the other against the employee's own submission.

The exposure therefore rises exactly when 1b ships — a small frontend phase during which
nobody will be reviewing evaluator semantics. **The fix belongs before 1b, not after.**

### Rejected

- **Amending D057 rule 3 instead, letting a preference establish eligibility.** This would
  recommend people for shifts they never affirmatively declared they could work, on the
  strength of a declaration whose meaning is reluctance. It would directly contradict D057
  rule 3's accepted hard-positive requirement, and would undermine D055 rule 5's distinction
  between affirmative eligibility evidence and the absence of it.
- **A dedicated `preferred_off_only` exclusion cause.** It creates a public semantic the
  product does not need, adds a category Feasibility.1 would then have to present, and is
  unnecessary because orthogonal `preferred_off` state already preserves every distinction
  D055 rule 5 requires.
- **Leaving D055 rule 1's text intact and recording only a clarification.** The unqualified
  table row is what the implementation followed. Text that has already misled one
  implementation and two reviews must be amended, not annotated.

### Stopping rule, carried forward from D058

**No D060 during Availability.1a**, except where Step 0 or review proves either:

```text
A. an accepted D055–D059 rule is impossible to implement against live code, or
B. two accepted rules are mutually contradictory.
```

Everything else is deferred to a named follow-up rather than expanding Availability.1a.

D059 is itself an exception-B invocation. A second invocation would no longer read as an
isolated defect: it would indicate that the decision set is being drafted too thinly, or that
Availability.1a is scoped too widely to hold in one head. Treat a third contradiction as a
signal to stop and reassess the phase, not as licence to write D060.

### Not decided here

- No further contradiction was found while drafting. The counterfactual-eligibility site
  described above is the same contradiction in a second consequence path, not a distinct one.
- Remediation of the live implementation. D059 records the rule; the code change is separate
  work.
- Everything already listed as undecided in D055, D056, D057, and D058 is unchanged,
  including the store scope at which availability rows are loaded.

---
## D061 — Cross-midnight interval representation and overnight operation

**Status:** Accepted
**Date:** 2026-08-18
**Supersedes:** D057 rule 6, effective on completion of Coverage.1bB-2b
(2026-09-02). Coverage.1bB is complete in three parts: 1bB-1 made cross-date
interval arithmetic correct; 1bB-2a made the write invariant transactional
across periods; 1bB-2b opened the write gate and removed the cross-midnight
early-return branch. D057 rule 6 is no longer controlling.
Overnight declared availability is now writable and matchable.
**Blocks:** D060 (night bands), Coverage.1bA, Coverage.1bB, SiteHours.24h

### Context

The first customer operates a mix of overnight and non-overnight sites under one
tenant. Overnight operation is currently unrepresentable at three layers —
store opening hours, coverage templates, and declared availability — each
enforcing that an end time must follow a start time within one calendar day.

Repository inspection on 2026-08-18 established that these are **not one shared
mechanism**. Nine enforcement points exist across five distinct mechanisms, with
no shared helper crossing a layer. The three layers are also unequally coupled to
scheduling:

- **Opening hours** are consumed by nothing in the scheduling path. Two
  duplicated readiness `COUNT(*)` predicates and a display round-trip are the
  only consumers.
- **Coverage templates** have one consumer, `generate_week_shifts`, where a
  single expression anchors both endpoints to the same date.
- **Availability** carries four independently reachable same-date assumptions:
  the shift-side loader's `date ==` predicate, the evaluator's start-date filter,
  `_entry_interval`'s anchoring, and contradiction detection's `first.date !=
  second.date` guard.

Shifts already store full timestamps and already permit cross-midnight intervals.
Duration arithmetic is therefore already correct for overnight work.

This decision settles the semantics. It does not settle implementation.

### 1. Cross-midnight representation for timed intervals

Where a stored timed interval's end time is earlier than its start time, **the
end time belongs to the following calendar day**.

```text
22:00 → 06:00   means   22:00 on day D through 06:00 on day D+1
```

This applies to store opening hours, coverage templates, and declared
availability windows. Shifts are unaffected — they already store dated
timestamps and require no convention.

**An interval whose start and end times are equal is invalid and must be
rejected.** It is not zero duration and it is not 24 hours. No operator enters it
deliberately, and interpreting it as a full day would turn a typo into a
day-length shift or a day-length availability declaration.

A timed interval may not exceed 24 hours. `22:00 → 06:00` is 8 hours; there is no
timed representation for a longer span, and none is needed.

### 1a. Continuous opening is not a timed interval

Rule 1 governs intervals with two clock times. **Continuous opening for a whole
day is a distinct concept and must not be expressed as a timed interval.**

`00:00 → 23:59` is lossy and is the representation this decision removes.
`00:00 → 00:00` is prohibited by rule 1. Neither can express a full day
truthfully.

**A day of continuous opening is represented by `open_time` and `close_time`
both NULL, with `is_closed` false.**

The `store_opening_hours` columns are already nullable, and the existing DB
constraint permits NULL times only when `is_closed` is true. The state
`is_closed=false` with both times NULL is therefore not being reinterpreted from
an existing valid meaning.

**Corrected 2026-09-02 by live inspection.** This rule previously described that
state as "genuinely unused today." It is stronger than unused — it is
**forbidden**, at three independent layers:

```text
Pydantic validator   store.py:62-73    "open_time and close_time are required
                                       when store is open"
Database CHECK       ck_store_opening_hours_open_times
                     CHECK (is_closed OR (open_time IS NOT NULL
                       AND close_time IS NOT NULL AND close_time > open_time))
Readiness predicates sites.py:747-757, stores.py:307-317
                     both require open_time IS NOT NULL AND close_time IS NOT NULL
```

The `CheckConstraint` is declared on the model at
`store_opening_hours.py:29-32`, so engineering constraint 1's warning about
migration-only constraints invisible to `create_all` does **not** apply to this
table.

**Consequence: SiteHours.24h requires a migration to drop or replace
`ck_store_opening_hours_open_times`, not only validator changes.** The same
constraint's `close_time > open_time` clause is also what makes cross-midnight
opening hours unrepresentable, per H101.

The three-state shape becomes explicit:

```text
is_closed = true                        no opening interval begins that day;
                                        a previous day's cross-midnight
                                        interval may still carry into it
is_closed = false, both times NULL      open continuously, 00:00–24:00
is_closed = false, both times set       open for that timed interval,
                                        cross-midnight per rule 1
```

A day with exactly one time set remains invalid, as today.

The column is named `is_closed` for historical reasons. Its semantic meaning
under this decision is "no local opening interval begins on this day," per rule
1b. The column name must not be read as the rule.

Chosen over a dedicated discriminator column because it adds no schema, and over
equal-times-means-24-hours because a rule that inverts its meaning between layers
is the kind of inconsistency this decision exists to prevent. The absence of
times reads naturally as the absence of a boundary. It also mirrors the
availability layer, where a full-day declaration is already NULL/NULL and already
matches any shift — so the convention is not new to the system.

**Current API validation rejects a day marked open with missing times.** That
rejection must be replaced by the three-state rule above, on **both request and
response paths** — see engineering constraint 2.

**A continuous-open row is a configured open day for all readiness purposes.**
Readiness logic must treat it as equivalent to a valid timed-open row. The two
duplicated readiness predicates today count a row only when `is_closed` is false
and both times are non-NULL; unchanged, they would report a truthful 24-hour
site's opening hours as unconfigured immediately after a successful save.

### 1b. `is_closed` and cross-midnight carry-over

**`is_closed = true` means no opening interval begins on that weekday. It does
not cancel a cross-midnight interval that began on the previous weekday.**

Consistent with rule 2's start-date ownership, applied uniformly. The alternative
— that a closed day truncates the previous day's interval at midnight — would
introduce a second, contradicting ownership rule for opening hours alone.

Where this applies, the UI must not present the day as unstaffed for its full 24
hours. It is covered until the carried interval ends.

**This rule does not arise for continuously-open sites**, where `is_closed` is
false on every day, and does not arise for sites whose intervals do not cross
midnight. It exists so the system cannot be configured into a state it cannot
interpret, not because it describes common operation.

### 2. Date ownership: an interval belongs to the date on which it starts

A cross-midnight interval is owned by its start date. Monday 22:00 → Tuesday
06:00 is a **Monday** interval.

Confirmed by customer operational language, not inferred from code: the customer
refers to that shift as "Monday night." It also matches the existing shift model,
which buckets by start time throughout.

Consequences:

- An availability row's `date` is the date the declared window begins.
- A coverage template's `day_of_week` is the day the window begins.
- A shift's day, for display and grouping, is the day it starts.

**Ownership is a grouping and scheduling-boundary rule only.** Interval
containment, overlap, and contradiction detection operate on the **actual dated
interval**, not on the owning date. A Tuesday-owned declaration may therefore
intersect a Monday-owned overnight interval, and must be evaluated as
intersecting it.

This sentence is load-bearing. Without it, "the shift belongs to Monday" could
later be cited to justify ignoring a Tuesday declaration — recreating precisely
the same-date defect Coverage.1bB exists to remove.

There must be no second scheduling-ownership rule anywhere in the rota, coverage,
availability, or opening-hours layers governed by this decision. A convention
applied inconsistently across those layers is worse than either convention
applied uniformly. This does not constrain the domains rule 3 explicitly
excludes.

### 3. Week ownership: an interval belongs to the week its start date falls in

A rota week runs Monday to Sunday. A Sunday 22:00 → Monday 06:00 shift belongs
to **that week**.

For rota ownership, generation, publishing, admin replace-week scope, and
existing scheduling calculations that operate by rota week, the whole interval
belongs to the week containing its start date. It is not divided.

**Explicitly rejected: splitting an interval at midnight for scheduling
purposes.** An 8-hour Sunday night shift is not stored as 2 hours on Sunday plus
6 hours on Monday. It is one shift. Splitting would contradict how the customer
describes the work, would require deciding which half an employee accepts or
swaps, and would thread a new concept through generation, publishing, requests,
and employee visibility.

**This decision does not settle attribution for any other purpose.** Payroll
period attribution, calendar-month attribution, statutory working-time
reporting, and financial or labour-cost reporting are outside its scope and may
adopt different attribution rules, decided separately. Rota-week ownership is a
scheduling boundary and must not be cited as a payroll or accounting rule.

### 4. Contradiction detection is not bounded by date or week ownership

**Same-source hard-positive and hard-negative declarations that overlap in real
time remain contradictory even where their owning dates or owning weeks
differ.**

```text
Sunday   available    22:00 → 06:00   (Monday 06:00)
Monday   unavailable  01:00 → 03:00
```

These overlap in real time. They are a contradiction under D055 and must be
rejected at write time, notwithstanding that they carry different `date` values
and may fall in different rota weeks.

Today they cannot conflict, because contradiction detection short-circuits on
`first.date != second.date`. Coverage.1bB must remove that guard.

**Logical comparison is not sufficient on its own.** Availability.1a enforces the
write-time invariant transactionally, under an advisory lock keyed in part by
period. Two concurrent writes against adjacent weeks may take different locks,
each read before the other commits, and both succeed — producing a persisted
contradiction that no single request could have created.

Coverage.1bB must preserve the transactional invariant across adjacent-date and
adjacent-week overlaps. The existing period-scoped lock design must not be
assumed sufficient. *How* is an implementation question; *that* it must hold is
settled here.

This boundary case is unlikely to be caught by the existing suite: the
PostgreSQL concurrency guarantee is deliberately stronger than what SQLite tests
exercise.

### 5. Phasing: overnight creation precedes overnight automatic matching

Three implementation phases, sharing this decision's semantics, shipping
independently.

**Coverage.1bA — overnight intervals become creatable and schedulable.**
Overnight coverage templates, correct next-day anchoring in generation, admin
overnight shift creation, and overnight display. On completion a manager can
build and publish an overnight rota.

**Coverage.1bB — overnight declared availability becomes matchable.**
`_entry_interval` becomes genuinely cross-date, both availability loaders are
repaired, contradiction detection compares across dates and weeks under rule 4,
and D057 rule 6 is deliberately replaced. Completed 2026-09-02.

**SiteHours.24h — truthful continuous-opening representation.** Rule 1a's
three-state shape across schema, request and response validation, readiness, and
the frontend round-trip, plus repair of the lossy 24/7 shortcut. Separable
because opening hours have no scheduling consumer.

**D057 rule 6 remained in force until Coverage.1bB.** Cross-midnight shifts
failed closed in automatic matching, and overnight shifts were assigned manually
in the interim. That was a stated limitation, not a defect. It ended with
Coverage.1bB-2b on 2026-09-02.

Rationale for the ordering. Relaxing an availability write constraint before the
interval logic understands cross-midnight would create a silent safety failure,
and the failure is asymmetric. Inspection established that an inverted interval
reaching the evaluator today never establishes eligibility as a hard positive —
failing safe — but as an `unavailable` declaration it **silently stops
excluding**, because the overlap test becomes unsatisfiable. No code path raises
or logs. A person declared unavailable would become assignable with no error.

**Ordering is therefore mandatory: `_entry_interval` and the overlap logic must
understand cross-midnight before any availability write constraint is relaxed.**

Coverage.1bB's proof had to include a causal regression for the unsafe overnight
`unavailable` case, demonstrated to fail before the fix and pass after it, and
established before the overnight availability write gate was relaxed. That
obligation was discharged in Coverage.1bB-1 by regressions T1a and T1b, which
landed before the gate opened in 1bB-2b.

### 6. Overnight display

A cross-midnight shift renders in the column of the date it starts, showing its
full span. It appears once, under its owning date.

```text
Monday   22:00 – 06:00
Tuesday  covered until 06:00   (indication, not a second shift entry)
```

**The receiving date must carry an indication that it is covered until the
interval ends.** A manager reading Tuesday must be able to see that staff are on
site until 06:00 without a duplicate shift appearing in Tuesday's column.

The mechanism is a presentation concern; the requirement is not. The current grid
already buckets by start time and therefore already satisfies the placement rule.
What it does not do is make the carry-over legible.

### 7. Site 24-hour status is derived, not stored

A site declares its opening hours. Where every day is continuously open under
rule 1a, the site is presented as a 24-hour site. **No stored discriminator is
added.**

A stored flag can contradict the hours it claims to describe — set once, then
made false by a later edit to a single day — producing two sources of truth for
one fact. A derived indicator cannot drift.

Consequences:

- No new column on the site record.
- Site setup retains its 24/7 shortcut as a **convenience that populates the
  hours**, writing continuous-open rows for all seven days, after which any day
  remains editable.
- The current defect is that the shortcut writes `00:00–23:59` across seven days
  and discards the `24_7` intent, which exists in the frontend only and is never
  persisted. Under rule 1a the shortcut writes a truthful representation, and
  intent survives in the data rather than beside it.

**Existing site data is ambiguous and cannot be repaired by inference.** Sites
carrying `00:00–23:59` may be genuinely 24-hour or may have accepted the form
default. The discriminator was discarded at write time. Any backfill must be
confirmed with the operator, per site. Implementation must not guess.

### What this decision does not settle

- Which admin-side role may configure opening hours or coverage templates.
  Governed by existing site-settings authority; not amended here.
- The grid's carry-over presentation mechanism.
- Whether coverage templates should validate against opening hours. They do not
  today; nothing in scheduling consumes opening hours at all.
- Payroll, month-boundary, statutory, or financial attribution of hours.
- Cross-source availability precedence. Still deferred.
- Standing availability baselines. Availability.2, unadjudicated.

### Engineering constraints carried to implementation

Inspection findings, recorded so they are not rediscovered mid-phase.

1. **The coverage-template CHECK constraint is invisible to tests.** It exists in
   migration `0014` but is not declared on the model, and the test suite builds
   schema via `Base.metadata.create_all`. A green suite is not evidence that the
   production PostgreSQL constraint was changed correctly. This also diverges from
   `CLAUDE.md`'s "Alembic migrations only, no create_all."
2. **`OpeningHoursDay` validates both request and response.** A relaxed write
   without a matching relaxation of the response model would make a valid stored
   row fail on serialisation during GET. Rule 1a's three-state shape must land on
   both paths together.
3. **The write gate and the generation re-gate are unaware of each other.**
   `_validate_time_window` and `_validate_templates` are independent duplicates
   with different error codes. Both must move together.
4. **Three duplicated shift-duration implementations exist.** Two clamp negative
   durations to zero; one does not and would render a negative in the weekly hours
   display. All three subtract full timestamps and are correct for genuine
   overnight shifts.
5. **The admin UI blocks overnight shift creation twice** — in
   `validateCreateShiftDraft` and structurally in `buildShiftDateTime`, which
   derives both endpoints from a single day index. H101's claim that overnight
   shifts remain manually creatable is true of the API and false of the product.
6. **Availability.1a's advisory lock is period-scoped.** See rule 4. Cross-week
   contradiction detection must not silently lose the transactional guarantee.
7. **Two duplicated readiness predicates** must both be updated for rule 1a's
   continuous-open state — `stores.py` and `sites.py`.

### Test to apply

> Does every layer that stores or interprets a time interval agree on which
> calendar date it belongs to; does no layer confuse ownership with overlap; and
> does no layer silently stop excluding someone it previously excluded?

---
## D060 — Site-scoped shift bands and band-based admin availability entry

**Status:** Proposed — recorded for future adjudication; not implementation authority  
**Date:** 2026-08-22  
**Draft lineage:** v1/v2 discussed 2026-08-17; v3 incorporates the settled review corrections from the Coverage.1b session.  
**Amends if later Accepted:** D048's binary/full-day admin availability UI model. D055–D059 and D061 continue to govern declaration and overnight semantics unchanged. D048 otherwise remains in force, including person-scoped availability on `user_id`, source provenance, and admin replace-week authority.  
**Implementation dependency:** D060 ships as one phase only after Coverage.1bB is complete. No partial daytime-only band implementation before 1bB.

### Context

For the first-customer MVP operating model, management-entered availability is the primary workflow and employee self-service is deprioritised. Employees tell management when they can work; an authorised admin-side user records that availability.

This is a rollout and commercial-priority decision, not a claim that the Employee Portal does not exist. The portal and employee availability APIs already exist. They are simply not on the current MVP critical path.

Availability.1a established the backend semantics for timed declared availability, including hard-positive containment, hard-negative overlap, `preferred_off`, contradiction handling, source provenance, and transactional same-source contradiction protection. Availability.1b exposed `preferred_off` to employees.

The current admin availability surface remains the practical gap: it is binary/full-day and cannot faithfully record ordinary operational statements such as:

```text
Sarah can work mornings on Tuesday and Thursday.
Ali can work evenings on Friday.
James can work 09:00–17:00 on Wednesday.
```

This decision proposes replacing that binary admin surface with site-configured named shift bands plus a Custom time escape hatch.

D061 has now settled the cross-midnight representation used by the Night band. Coverage.1bB must still make cross-midnight declared availability and matching safe before this surface is implemented.

---

### 1. Shift bands are site-scoped configuration; availability remains person-scoped

Each site defines four named shift bands in site-local wall-clock time under D054:

```text
morning
afternoon
evening
night
```

Band names are fixed in MVP. Their times are editable per site.

**Site scope applies to the band definition, not to the resulting availability declaration.**

Selecting a site's Morning band resolves that band to concrete start/end times and writes an ordinary person-scoped availability declaration for the employee and date. The availability row does not gain a new band identity and does not become permanently linked to the site band definition.

D048's person-scoped availability model remains unchanged.

Band configuration belongs to site setup/configuration. Implementation must reuse the existing authority boundary for site setup/configuration; this decision must not invent a `manager` tenant role or a new RBAC rule.

---

### 2. The four seed windows are fixed defaults and remain editable

Confirmed MVP seed times:

```text
morning    06:00–14:00
afternoon  14:00–22:00
evening    18:00–22:00
night      22:00–06:00
```

These are **seed values**, not evaluation-time fallbacks.

A site's saved band rows are the source of truth. There must be no runtime rule such as:

```text
if band rows are missing, silently use the system defaults
```

A later change to software defaults must never silently move a customer's operational shift boundaries.

The seed values are prefilled for convenience, but the site must explicitly complete/confirm band setup.

---

### 3. Band setup is mandatory; there is no silent existing-site backfill

D060 does **not** silently backfill existing sites with persisted default band rows.

Existing sites must complete a mandatory one-time band setup before the band availability surface is enabled for that site.

New sites receive the confirmed seed values in the setup flow and explicitly save/confirm them as part of site configuration.

The purpose is auditability and customer intent: an old site must not acquire new scheduling assumptions merely because a migration ran.

No runtime fallback and no silent migration backfill are permitted.

---

### 4. Bands may overlap and may leave gaps

The four configured windows do not need to tile 24 hours and do not need to be disjoint.

Examples that are valid:

```text
morning    06:00–14:00
afternoon  12:00–20:00
```

or:

```text
morning    07:00–12:00
afternoon  14:00–18:00
```

Overlaps and gaps are operational configuration, not validation errors.

Selecting overlapping bands writes the resolved windows independently unless they resolve to the exact same stored window, in which case rule 6 deduplicates them.

**Adjacent positive bands do not stitch.**

Per D057 rule 3, Morning 06:00–14:00 plus Afternoon 14:00–22:00 does not make a 09:00–17:00 shift eligible. One hard-positive declaration must independently contain the whole shift.

---

### 5. Custom time entry is mandatory

The admin surface must offer **Custom** in addition to the named bands.

Custom lets the authorised user enter arbitrary start and end times for the selected date.

Without Custom, the band vocabulary is lossy. For example, if an employee says:

```text
09:00–17:00
```

and the configured bands are:

```text
06:00–14:00
14:00–22:00
```

then:

- Morning invents 06:00–09:00 availability;
- Afternoon invents 17:00–22:00 availability;
- selecting both still does not establish 09:00–17:00 eligibility because positive rows do not stitch;
- All-day invents even more availability.

Bands are the operational fast path. Custom is what keeps the surface truthful.

---

### 6. Multiple selections are allowed; duplicate detection is on the resolved window

A date may carry multiple positive declarations.

Examples:

```text
Morning + Evening
Morning + Custom
two distinct Custom windows
```

This preserves D055/D057's existing allowance for multiple non-conflicting positive windows.

**Deduplication occurs after controls are resolved to concrete stored windows, not by which control was clicked.**

If two different controls resolve to the same concrete window for the same date, only one declaration is written.

Examples:

- Morning is configured as 06:00–14:00 and Custom is also entered as 06:00–14:00 → one row.
- Two differently named bands happen to have identical 18:00–22:00 definitions → one row when both are selected.
- Re-selecting the same band → no duplicate row.

For this proposed admin surface, new declarations are hard `available` declarations, so the resolved-window identity is the selected date plus its resolved full-day/timed window. UI control provenance is not stored as declaration identity.

---

### 7. There is no "Unavailable" control

The D060 admin surface does **not** expose an Unavailable button, checkbox, band, or toggle.

For a date where management records no All-day, band, or Custom availability, the surface records **no new positive declaration for that date**.

That is the weekly-layer **no-declaration state**, not an explicit `unavailable` declaration.

The UI must not label the empty state as "Unavailable".

D055/D059 preserve the distinction:

```text
no applicable declaration
!=
explicit unavailable declaration
```

Both currently prevent automatic eligibility in the weekly layer, but they are different business facts and must remain distinguishable.

Explicit hard-negative `unavailable` entry is not introduced by D060.

---

### 8. All-day remains available and is exclusive

All-day remains an admin availability option.

It writes the existing full-day positive declaration:

```text
start_time = NULL
end_time   = NULL
```

All-day is mutually exclusive with timed band/Custom selections for that date.

Selecting All-day clears newly selected timed positive windows for that date. Selecting a timed band or Custom window clears a newly selected All-day positive declaration.

This avoids redundant positive rows such as:

```text
All-day + Morning
```

while retaining the ability to say "available all day" even at sites whose configured bands leave gaps.

---

### 9. D060 is one post-1bB phase; no partial pre-1bB release

The complete D060 surface, including Night, ships only after Coverage.1bB.

Do not ship Morning/Afternoon/Evening/Custom first and bolt Night on later.

Reasons:

1. Night is one of the four fixed MVP bands, not an optional extension.
2. D061 already defines Night's `22:00–06:00` representation.
3. Until Coverage.1bB lands, the declared-availability write/evaluation path still deliberately fails closed for cross-midnight automatic matching.
4. A partial surface would create two temporary product models and another migration/review boundary for little customer value.

Coverage.1bB therefore gates **D060 implementation as a whole**.

Recording this proposed decision now is not gated. Only implementation is.

---

### 10. Existing/off-band rows must survive replace-week; semantic content is carried forward

The admin grid may load rows that are not represented by a currently configured named band.

Examples include:

- an availability row entered before the site's band definitions changed;
- an employee-authored timed row;
- a generic-API row;
- a `preferred_off`, `available_extra`, or explicit `unavailable` row that D060 itself does not offer as a new control;
- a literal time window that does not equal any configured band.

The UI must display the stored declaration truthfully, using its literal declaration type and/or literal times rather than snapping it to the nearest band.

**On an admin replace-week save, an existing row the band surface is not actively replacing must be carried forward in the replacement payload with its declaration semantics preserved. It must not be silently dropped.**

Because D048's current replace-week path recreates the saved week as admin-authored data, carried-forward rows acquire:

```text
source = admin
```

This provenance rewrite is deliberate and must be visible in the design/review. D060 does not create a second-source retention model and does not solve cross-source precedence. It preserves the declaration's semantic content through the current authoritative replace-week mechanism while accepting that the current mechanism rewrites provenance.

This is preferable to silently destroying off-band declarations.

The existing same-source contradiction invariant still applies to the final replacement set. Carry-forward must not bypass it.

---

### 11. Band edits do not rewrite historical availability

Availability rows store resolved declaration times, not references to band configuration.

If Morning changes from:

```text
06:00–14:00
```

to:

```text
07:00–15:00
```

an existing 06:00–14:00 availability row stays 06:00–14:00.

It may display as an off-band/custom literal declaration after the configuration change.

The band edit affects future selections only.

No migration rewrites historical declarations to match new band definitions.

---

### 12. The admin surface captures new hard availability only

D060's new-entry controls are:

```text
All-day
Morning
Afternoon
Evening
Night
Custom
```

All create ordinary hard-positive `available` declarations.

The surface does **not** provide new controls for:

```text
available_extra
preferred_off
unavailable
```

This is a deliberate MVP limitation.

It does not change the semantics of those declaration types and does not remove the Employee Portal's existing `preferred_off` capability.

Existing non-`available` rows may still appear and be carried forward under rule 10.

Do not justify the omission of `preferred_off` with a "near tie" or similar scoring claim. D056/D059 do not define such a threshold. The reason is product scope: management-entered MVP availability captures hard capability; preference capture remains outside this admin-band surface.

---

### 13. Save semantics remain replace-week semantics, with round-trip protection

D060 does not introduce an additive admin writer and does not create dynamic cross-source precedence.

The admin save remains a replace-week action under D048.

Before writing, the surface constructs the complete replacement set from:

1. newly selected All-day/band/Custom positive declarations;
2. existing declarations that must be carried forward under rule 10.

It then:

- resolves every named band to literal start/end values;
- deduplicates equivalent resolved positive windows;
- preserves carried-forward declaration type/times;
- applies the existing contradiction/write validation to the complete set;
- performs one replace-week write.

The UI must not derive the replacement solely from currently selected named-band controls, because doing so would silently erase declarations the band vocabulary cannot express.

---

### 14. Night uses D061's accepted cross-midnight representation

The confirmed default Night band is:

```text
22:00–06:00
```

Under D061, that means:

```text
22:00 on date D -> 06:00 on date D+1
```

Equal start/end times remain invalid.

D060 adds no separate overnight representation and must not split Night into two rows merely to fit the old same-date validator.

Coverage.1bB is responsible for making that representation safe in declared availability and automatic matching before D060 implementation begins.

---

### 15. What this proposed decision does not settle

D060 does not settle:

- cross-source precedence or retention of simultaneous admin + employee declarations;
- standing scheduling agreements / Availability.2;
- employee-facing band selection;
- customisable band names;
- multi-site employee availability scope beyond the existing D048 model;
- feasibility-report presentation;
- manual assignment override provenance (H099);
- employee credential UX (H102);
- Employee Portal availability-capture UX (H103);
- continuous-opening SiteHours.24h.

It also does not create a `manager` tenant role.

---

### 16. Implementation gate

D060 remains **Proposed** until explicitly adjudicated.

Even if later Accepted, implementation must not begin before Coverage.1bB is complete and D057 rule 6 has been deliberately replaced for cross-midnight declared availability/matching.

At implementation time, inspect the live admin replace-week schema before assuming it can round-trip every declaration type required by rule 10. If it cannot, that is an implementation/decision conflict to report, not a licence to silently drop rows or change their meaning.

---

### Test to apply

> Can management record the employee's stated hard availability without inventing extra time, silently deleting existing declarations, or changing historical rows when band configuration changes?

And for every save:

> Does the complete replacement set preserve every declaration the surface did not explicitly replace, even when that declaration no longer matches a named band?

---

## D062 — RETIRED, NEVER ISSUED

**Status:** Rejected / number retired
**Date:** 2026-09-02

A duration-based availability exclusion rule was drafted during Coverage.1bB-2b
and rejected before acceptance. `NO_DECLARATION` already means "no applicable
eligibility-establishing declaration" per D059, and a `>24h` threshold does not
carve the structural condition: `Mon 09:00 → Tue 09:00` is exactly 24 hours and
cannot be expressed as a single timed declaration.

A shift from `Mon 00:00 → Tue 00:00` is exactly 24 hours and can be covered by a
full-day availability declaration. That does not make the timed pair
`00:00 → 00:00` valid. Equal timed start and end remains invalid under D061
rule 1.

The number is retired rather than reused. The Coverage.1bB-2b Codex prompt cites
"D062 was drafted and rejected," so reissuing the identifier for a different
subject would give one number two meanings across the record.

---

## D063 — Admin-side identity is one person, one login, scoped by store assignment

**Status:** Accepted
**Date:** 2026-09-02
**Supersedes:** D004's future `manager` tenant-role target
**Amends:** D041 and D043, wherever they describe `manager` as a future tenant role
**Related:** D053, H085, H102

### Context

The product documents describe five roles. Two of them are the same role.
`forecourt_os_permission_matrix_v1.md` section 2.3 defines Admin as "Operational
role. Works within assigned site scope. Cannot manage tenant-level governance,"
and section 2.4 defines Manager as "Operational role. Works within assigned site
scope. Similar to Admin for day-to-day operations where allowed, but not
governance." Every row of that document's portal-access table is identical for
both.

Two names were created for one role and no distinguishing rule was ever found to
put between them. That ambiguity has appeared in at least three separate
planning sessions.

Live inspection on 2026-09-02 established the current state:

- The implemented tenant role set is `owner | admin | member`.
- `manager` appears exactly once in the non-test API, at `sites.py:63-78`, in a
  branch that cannot execute because no code path can issue that role.
- Admin access is tenant-wide. Every write endpoint across `rota.py`,
  `shifts.py`, `coverage_templates.py`, `rota_recommendations.py`, `staff.py`,
  `availability.py`, `hour_targets.py` and `stores.py` takes `store_id` from the
  request and validates only that the store belongs to the active tenant. Seven
  duplicated lookup helpers each run the same two-clause query. No dependency
  accepts a store parameter.
- No per-user store assignment exists in the schema. `tenant_users` carries
  `id, tenant_id, user_id, role` and nothing else.
- `stores.manager_user_id` exists and is settable, but is read for authorisation
  in exactly one place — the unreachable branch above.

### 1. There is no `manager` role

The admin-side role set is and remains:

```text
owner | admin
```

`admin` is the operational role the business calls a manager. No `manager`
tenant role is created, and `admin` is not renamed.

Renaming would require a migration plus edits to every guard, test, permission
document and frontend reference, for no functional gain. The word shown on
screen is a presentation choice, recorded separately from the role name in code.

`member` is unchanged: a staff-identity bridge, not Admin Portal access, per
D041.

### 2. Admin-side identity is one person, one login

A person holding admin-side access to a tenant has **one** `users` row and
**one** `tenant_users` membership, regardless of how many stores they work
across.

Separate credentials per store are explicitly rejected.

**Why.** Credentials do not enforce store scope; server-side authorisation does.
Under either credential model, every store-scoped operation must resolve the
requested store and prove the authenticated user is authorised for it, so the
seven lookup sites need the same check either way. Per-store credentials
therefore add cost and save no authorisation work.

The cost is real: `users.email` is UNIQUE, so one person would need two email
addresses; two passwords to reset against a credential-lifecycle gap that is
already open; two future 2FA enrolments; fragmented audit identity for one
human; a log-out to change store; and either a second auth model on the admin
side or the employee store-picker bolted onto it.

This follows D053's reasoning. A person employed by a tenant is one person with
one staff profile, because fragmenting them into per-store records miscalculates
pay. Fragmenting the credential contradicts the same principle without the pay
consequence to justify it.

**This decision does not settle session or token architecture.** Whether the
selected store is a token claim, a session value, or an ordinary request
parameter is an implementation question. What is settled is that authorisation
is resolved server-side against assignment state, never inferred from which
credential was used.

### 3. Store scope comes from an assignment relation

Admin-side store access is granted by explicit assignment.

Conceptual assignment relation:

```text
id
tenant_id
store_id
user_id
is_active
created_at
updated_at

UNIQUE (tenant_id, store_id, user_id)
```

The physical table name and exact foreign-key implementation are settled during
the implementing phase against the live schema. This decision settles the grain
and the invariants, not a table name. The shape in
`forecourt_os_database_schema_prd_v1.md` section 5.4 is design intent that
predates the live `stores` / `store_id` nomenclature and must not be inherited
verbatim.

Rules:

```text
owner   implicit access to every store in the tenant.
        No assignment rows required.

admin   access only to stores with an active assignment row.
        Zero assignments means zero operational store access.
```

An admin with more than one assignment selects a store after logging in. Store
selection is an operational context choice, not a second authentication.

**Zero assignments must never fall back to tenant-wide access.** A fallback
would turn a migration or backfill mistake into privilege escalation.

A second role dimension inside the assignment — a `site_role` column or
equivalent — is **not** adopted. It would reintroduce exactly the ambiguity
rule 1 removes.

### 3a. Tenant integrity is an invariant, not a convention

An assignment row is valid only when its `tenant_id`, its `store_id`'s store,
and its `user_id`'s tenant membership all resolve to the **same tenant**.

This must be structurally enforced, not left to application code that "normally
creates them correctly." Whether that enforcement lives in foreign key
structure, service validation, or both is an implementation question the
building phase must settle by inspecting how this repository currently enforces
cross-table tenant integrity.

### 4. The scope check applies to every store-scoped operation

Authorisation is not a write-path concern. The property is:

```text
admin:  requested store ∈ that user's active assigned stores
```

for every protected store-scoped operation, including reads, creates, updates,
deletes, generation, recommendation, export and any other action, unless a later
explicit rule grants broader scope.

An unassigned admin reading another store's staff, rota, or availability is an
isolation failure even where they cannot mutate it. A correct write-side
implementation with intact read-side leakage does not satisfy this decision.

### 5. `manager_user_id` and the dead branch

`stores.manager_user_id` cannot express rule 3. It models one manager per store;
the case that prompted this decision is one manager over two stores. It also
cannot express multiple operational admins for one store, clean revocation, or
any assignment metadata.

**`manager_user_id` has no authorisation meaning and must not be consulted by
access-control logic.** It is retained as descriptive metadata — "who runs this
store" is legitimate information. Its long-term fate is deferred.

The unreachable branch at `sites.py:63-78` is **deleted**, not activated. It
assumes a role the system cannot issue, applies to two endpoints out of seven,
and encodes single-manager-per-store semantics nobody adjudicated. Leaving it is
a latent security defect: the day `manager` enters `TENANT_ROLES` it activates
silently with the wrong rule on an arbitrary subset of endpoints.

**Acceptance of this decision does not authorise that edit.** The deletion
belongs to the implementing phase, not to the documentation commit that accepts
this decision.

### 6. Employee credentials — direction recorded, not decided

The same principle should apply to employees: one person, one login, store
selected after authentication.

**This is direction, not authority. It is explicitly not decided here.**

Today employee accounts are site-scoped — store selection, then username and
password — so a person working two stores has two logins, while D053 already
gives them one staff profile. That split is a known inconsistency.

D053 states the credential model belongs to the H085 identity seam and leaves it
open. H102 records that no employee credential lifecycle exists at all, which
makes the current model unoperable by a customer regardless of its shape.

A future phase must adjudicate this against live code before implementing it.
Recording the direction means the next session knows which way to lean without
being bound by a design nobody has inspected.

### Not decided here

- Which admin-side role may create or revoke assignments. Candidate is
  owner-only; requires its own ruling alongside the admin lifecycle phase.
- **How existing tenant-wide admin accounts are migrated into assignment rows. A
  compatibility and backfill plan is mandatory before enforcement is enabled.**
  If enforcement ships ahead of backfill, every non-owner admin loses
  operational access on deploy. This decision states the product rule and
  deliberately does not prescribe the migration.
- Whether store selection persists across sessions.
- Whether an admin with exactly one assignment skips the picker.
- `manager_user_id`'s long-term fate.
- Session and token architecture. See rule 2.
- The employee credential model. See rule 6 and H085.
- Any platform-owner or super-admin role.

### Test to apply

> Can a person who works across two stores do their job with one password; and
> can the system prove, for every store-scoped operation, that this user was
> authorised for the store they requested?

---

## D064 — Admin lifecycle revocation is tenant-membership scoped

**Status:** Accepted
**Date:** 2026-09-03
**Related:** D004 (owner lifecycle deferred), D040 (sensitive-action step-up),
D041 (member is not Admin Portal access), D063 (admin identity and store
assignment), H122, H124, H126, H128

### Context

Phase 1a's stated goal is that an owner can remove one admin's access. Live
inspection on 2026-09-03 established that neither half of that sentence has a
mechanism today.

- `tenant_users` has exactly four columns: `id`, `tenant_id`, `user_id`, `role`.
  No active state, no timestamps, no soft-delete. No endpoint deletes a
  membership.
- The only deactivation primitive present is `users.is_active`, which is global
  to the identity. One `users` row may hold memberships in more than one tenant;
  `UNIQUE (tenant_id, user_id)` constrains duplicates within a tenant and places
  no limit across tenants.
- `users.is_active` has no writer. It is set `True` at `auth.py:989` and
  `admin_users.py:61` and set `False` nowhere in non-test code.
- Every admin-side auth path reloads the user and enforces `is_active`: login
  (`auth.py:1018`), refresh (`auth.py:924`), 2FA challenge verification
  (`auth.py:1391`), step-up (`deps.py:195`), protected requests (`deps.py:95`),
  sensitive actions (`deps.py:195`), and `_get_user_from_subject`
  (`auth.py:765`). None omits it.
- No path from any user-state change writes to `auth_sessions`. Revocation is
  called only from password reset, refresh-reuse detection, rotation, and
  logout.

### 1. Revocation is scoped to the tenant membership

Phase 1a answers "the owner of tenant A revokes this admin's access to tenant
A." It does not answer "disable this human's admin identity everywhere."

`users.is_active` is therefore the wrong grain and is not the primitive.
`tenant_users` gains an active/inactive lifecycle state.

`users.is_active` remains what it is today — a global account state — and this
decision gives it no new writer.

### 2. Membership is deactivated, not deleted

Hard deletion of a `tenant_users` row is rejected. It is irreversible, it
destroys the record that access once existed, and `audit_logs.user_id` is a NOT
NULL foreign key to `users` that would retain rows referring to a user with no
membership.

Nothing foreign-key references `tenant_users`, so deletion would not violate
referential integrity. That makes it available, not correct.

Retaining the membership preserves tenant-access lifecycle history and remains
compatible with D063's future store-assignment model. D064 does not decide
whether assignment rows physically reference `tenant_users` or enforce the
membership relationship by another structural mechanism; D063 leaves that
implementation detail to Phase 2.

### 3. Revocation is atomic: membership plus sessions

Deactivating a membership blocks authority while the flag is false. It does not
end the session.

Measured at HEAD, deactivate then reactivate leaves usable:

```text
refresh family      is_revoked still false, up to 14 days
access token        remaining 15-minute TTL
step-up window      last_2fa_step_up_at untouched
2FA challenge       not consumed, not deleted
```

An operator who deactivates and later reactivates has not ended the original
session. H122 is filed as a revocation gap, and a flag toggle does not close it.

Revocation is therefore one operation with two effects, and they must succeed
together or fail closed:

```text
membership marked inactive
+
that user's active admin sessions for that tenant revoked
```

`auth_sessions` carries `tenant_id`, so tenant-scoped revocation is expressible.
The existing pattern is `_revoke_active_admin_sessions_for_password_reset` at
`auth.py:535`.

### 4. Every auth-continuation path must honour an inactive membership

The `is_active` check on `users` is duplicated into each of the seven paths
listed in Context rather than shared. Membership state must reach all of them:

```text
admin login
refresh
2FA login challenge verification
2FA step-up issuance and verification
protected-request current-user resolution
sensitive-action resolution
```

An implementation that adds the check to a shared helper must verify that every
path actually routes through it. D041's R.2d note records that the member guard
was deliberately not placed in shared token utilities — that is precedent for
duplication, not for assuming a single choke point exists.

### 5. The mutation target is deliberately narrow

```text
actor            owner only
target           admin membership only
owner target     rejected
member target    rejected — not part of the admin-side lifecycle surface
```

An owner may appear in the list as a non-revocable tenant authority.

This makes owner-count logic unnecessary. If an owner membership cannot be
revoked, this endpoint cannot produce a zero-owner tenant, and no last-owner
guard is required. D004 defers owner transfer, promotion and demotion to future
work, and this decision does not disturb that.

H128 — that no zero-owner invariant exists outside migration `0027` — remains
open. The state is reachable through `0027`'s `downgrade()` or direct database
access, neither of which this decision addresses.

### 6. Reactivation is out of scope, with a fence

Phase 1a does not implement reactivation.

**A future reactivation feature must not revive authority issued before
deactivation.**

Phase 1a guarantees that while the membership is inactive:

- every admin auth-continuation path rejects the membership; and
- every active admin `auth_sessions` row for that tenant and user has been
  permanently revoked.

That does not by itself invalidate every artefact already issued. Access JWTs
remain cryptographically valid until their normal expiry and are not
`auth_sessions` rows, although the inactive-membership check rejects them.
Pending `Auth2FAChallenge` records are also separate from `auth_sessions`.

A future reactivation implementation must therefore establish explicitly how
pre-deactivation access tokens, pending challenges, step-up state, and any other
surviving authority are prevented from becoming usable again. It must not
satisfy reactivation by flipping `tenant_users.is_active` back to true.

A reactivation endpoint requires its own adjudication before it exists.

### 7. Revocation is a sensitive action

Listing tenant users is an ordinary owner-authenticated read.

Revoking an admin's authority is at least as sensitive as granting it. Phase 1a
introduces an admin-user lifecycle mutation of the class D040 identified as its
Tier-1 sensitive-action candidate, so the revoke operation is governed by D040's
step-up boundary.

Whether the existing owner 2FA enrolment and frontend step-up UX are sufficient
to make that boundary usable is not established by this decision and must be
inspected before wiring.

The revoke mutation is owner-only and protected by the **existing**
sensitive-action step-up dependency. No second custom 2FA mechanism is created.

**Open, and to be settled by inspection before wiring:** what
`require_sensitive_admin_action` does when the acting owner has not enrolled
2FA. If it fails closed, an un-enrolled owner cannot revoke anyone, which is a
bootstrap problem D040 already anticipates. If it passes through, the protection
is decorative. The implementing phase must establish which, and this decision
does not presume either.

**Inspection completed 2026-09-03. Result: UX insufficient. Wiring deferred.**

`require_sensitive_admin_action` fails closed. An owner who has never enrolled
2FA receives `403 AUTH_2FA_ENROLMENT_REQUIRED`, decided at `deps.py:279` and
raised at `deps.py:289`. A verified email is a separate, earlier prerequisite at
`deps.py:262`.

Neither gate is passable through the product:

```text
email verification   no frontend surface requests it; the raw token is
                     redacted from the only log that carries it and stored
                     only as a SHA-256 hash, so no human can obtain one;
                     the URL points at /admin/verify-email, a route that
                     does not exist in apps/web
2FA                  zero references to 2fa, totp, step_up or recovery_code
                     anywhere in apps/web; none of the seven 2FA endpoints
                     has a frontend surface
```

Registration leaves `email_verified_at` NULL and nothing changes it
automatically, so every owner starts on the wrong side of the first gate.

The rule stands unamended. D040 defers wiring until the user-management UX
supports owner 2FA enrolment and step-up; that condition is not met, so the
Phase 1a revoke mutation is not wired until Q.5.3c completes. Weakening rule 7
to owner-only-plus-audit was considered and rejected: it would use D040's own
precondition as grounds to skip D040, and audit is a detective control that does
not protect a stolen owner session.

See H130 and H132.

### 8. Admin-side identity stores a name

`users` has no name column of any kind. `full_name` exists in exactly one place
in the backend — the `AdminUserCreate` schema field that discards it. The admin
portal identifies the logged-in user by email (`admin-shell.tsx:889`) and
derives avatar initials from the email address (`admin-shell.tsx:764`).

`users` gains a nullable `full_name`. The create endpoint persists it, and the
list endpoint returns it.

Existing rows are **not** backfilled. Historical names are unknown and must not
be invented, including from email addresses or from `staff_profiles`. Null is a
valid value and the UI falls back to email.

The alternative — removing `full_name` from `AdminUserCreate` — is rejected. The
API already asks for it, the frontend already sends it
(`staff-create-form.tsx:76`), and a user-management page listing humans by email
address is a worse product.

This makes Phase 1a a schema phase. H124's text allows either option but does
not record that persisting requires a migration.

### Not decided here

- Reactivation of a deactivated membership. See rule 6.
- Owner transfer, promotion, demotion, or any owner-lifecycle operation.
  Deferred by D004.
- Any lifecycle operation on `member` memberships.
- Whether `users.is_active` should ever gain a writer, and what a global account
  suspension would mean.
- The audit action vocabulary. `deactivate` already binds to
  `entity_type="store"` in `stores.py`. The `action` and `entity_type` pair
  carries the semantics, so reuse across entity types is ordinary modelling
  rather than a defect; the implementing phase selects the vocabulary.
- Whether `audit_logs` should gain a metadata column. See H127.

### Test to apply

> After an owner revokes an admin's tenant membership:
>
> 1. can any existing admin auth path authorise that user while the membership
>    is inactive; and
> 2. are all server-side admin sessions for that tenant and user permanently
>    revoked rather than merely shadowed by the inactive flag?
