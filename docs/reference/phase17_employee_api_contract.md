# Phase 17 Employee API Contract (Path A)

## Status Note

This document tracks the employee portal and request-workflow API contract for the current Phase 17 employee/request workflow path.

It includes:

- implemented employee portal endpoints
- implemented admin request approval endpoints
- implemented request-to-rota behaviours
- planned/future employee workflow endpoints

Do not treat every endpoint in this file as implemented unless it is explicitly marked as implemented.

Always confirm current reality from:

1. `IMPLEMENTATION_STATUS.md`
2. `DECISIONS.md`
3. `README.md`

---

## Implemented Summary

### Implemented employee/auth/request endpoints

- Existing admin login flow using `POST /api/v1/auth/login`
- `GET /api/v1/public/sites/lookup?code=SITE_CODE`
- Existing employee login flow using `POST /api/v1/auth/employee/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- Employee published-only rota foundation
- `GET /api/v1/employee/me/availability`
- `POST /api/v1/employee/me/availability`
- `DELETE /api/v1/employee/me/availability/{entry_id}`
- `GET /api/v1/employee/me/requests`
- `POST /api/v1/employee/me/requests`
- `POST /api/v1/employee/me/requests/{request_id}/cancel`
- `GET /api/v1/employee/me/request-targets`
- `GET /api/v1/employee/me/request-target-shifts`
- `GET /api/v1/employee/me/inbound-requests`
- `POST /api/v1/employee/me/inbound-requests/{request_id}/accept`
- `POST /api/v1/employee/me/inbound-requests/{request_id}/decline`

### Implemented admin request approval endpoints

- `GET /api/v1/sites/{site_id}/requests`
- `GET /api/v1/sites/{site_id}/requests/{request_id}`
- `POST /api/v1/sites/{site_id}/requests/{request_id}/approve`
- `POST /api/v1/sites/{site_id}/requests/{request_id}/reject`

### Implemented request-to-rota behaviours

- Approved leave requests open/unassign affected published scheduled shifts.
- Target-accepted targeted cover requests reassign the affected published scheduled shift from requester to target employee.
- Swap requests now store requester shift, target employee, and target shift.
- Target-accepted swap approvals exchange requester shift and target shift assignments.

---

## Planned / Future Summary

Planned or future areas:

- Employee home
- Labour intelligence
- Employee-safe profile endpoint
- Dedicated swap endpoints, unless replaced permanently by generic request endpoints
- Untargeted cover rota handling / open-cover workflow
- Request retargeting after target decline
- Request history hide/restore
- Payroll/earnings recalculation after rota changes
- Attendance/timeclock/worked-hours model
- Payroll engine
- Notifications
- AI Help request actions

---

## Scope

This contract covers the employee portal and employee/request workflow path under:

- `/api/v1/employee`
- `/api/v1/public/sites/lookup`
- admin-side request approval endpoints under `/api/v1/sites/{site_id}/requests`

The employee portal APIs are derived from existing admin-managed truth only.

This contract does not introduce full leave/task/attendance/payroll engines.

---

## Shared Rules

- Auth: bearer token required unless endpoint explicitly says public.
- Tenant context: active tenant membership only.
- Employee account must be active.
- Linked staff profile must be active where required.
- Missing staff profile in tenant: `404 STAFF_PROFILE_NOT_FOUND`.
- Cross-tenant access: safe `404`.
- Store access follows Path A:
  - Allowed stores are derived from `staff_profiles.store_id`.
  - One-store schema returns one `available_stores` item.
  - If `store_id` is omitted, selected store falls back to assigned/default store.
  - Invalid or unauthorized `store_id` returns `404 STORE_NOT_FOUND`.
- Employee rota visibility is published-only.
- Employees must never see draft rota.
- Employees must never see co-worker private data.
- Admin-side request approval requires admin-side token and site-scoped permission.
- Rota mutation from requests must be backend-authoritative and audit logged.

---

## Auth / Session Reality After Phase Q.3.3

Phase Q.3.3 added refresh-token reuse detection and session-family tracking.

Important:
- New login sessions create a non-null session family.
- Refresh rotation creates a child session in the same family.
- Reuse of an already-rotated refresh token revokes the affected session family.
- Reuse/family-revocation events are logged in `auth_security_events`.
- Clients still receive generic refresh failure responses.
- Public response shapes did not change.

## `POST /api/v1/auth/login`

- Auth: none
- Body: form-encoded `username`, `password`
- Compatibility: existing admin login path is preserved.

Response includes:

- `access_token`
- `refresh_token`
- `token_type`

Behaviour:

- Creates a portal-aware `admin` refresh session.
- Stores only a hash of the refresh token server-side.
- Sets the refresh token in an HTTP-only cookie used by the frontend for session restoration.
- Frontend login stores the access token in memory only and clears legacy localStorage token keys.

---

## `POST /api/v1/auth/employee/login`

- Auth: none
- Body:
  - `site_id`
  - `username`
  - `password`
- Compatibility: existing employee login path is preserved.

Response includes:

- `access_token`
- `refresh_token`
- `token_type`
- `employee_account`

Behaviour:

- Requires an active employee account.
- Requires an active linked staff profile.
- Creates a portal-aware `employee` refresh session.
- Stores only a hash of the refresh token server-side.
- Sets the refresh token in an HTTP-only cookie used by the frontend for session restoration.
- Frontend login stores the access token in memory only and clears legacy localStorage token keys.

---

## `POST /api/v1/auth/refresh`

- Auth: refresh token in body or configured HTTP-only refresh cookie

Body:

- `refresh_token?`
- `portal?` — `admin` or `employee`

Response includes:

- `access_token`
- `refresh_token`
- `token_type`
- `portal`

Behaviour:

- Cookie-backed refresh requires `X-Requested-With: ForecourtOS`.
- Body refresh-token compatibility remains supported during the migration window.
- Rotates refresh tokens.
- Revoked, expired, unknown, or wrong-portal refresh sessions return `401`.
- Disabled admin users are blocked.
- Disabled employee accounts are blocked.
- Inactive linked staff profiles are blocked.
- Refresh tokens are not returned in error responses.

---

## `POST /api/v1/auth/logout`

- Auth: optional refresh token in body or configured HTTP-only refresh cookie

Body:

- `refresh_token?`

Response includes:

- `revoked`

Behaviour:

- Cookie-backed logout requires `X-Requested-With: ForecourtOS`.
- Revokes the matching refresh/session token when present.
- Clears the refresh cookie.
- Does not break legacy bearer-only clients during the D036 deprecation window.

---

## Frontend session model after Q.3.1

- Admin and employee frontend flows no longer actively persist access tokens in localStorage.
- Active browser access tokens are held in memory only.
- Page reload/session restoration uses `POST /api/v1/auth/refresh` with `credentials: "include"` and `X-Requested-With: ForecourtOS`.
- Legacy localStorage keys `forecourt_access_token` and `forecourt_employee_access_token` are cleared by the frontend migration/logout paths.
- The stale key `employee_access_token` is not an active key.
- Bearer-token API compatibility remains during the D036 deprecation window.

---

# Public / Auth Support

## Current MVP Addition — Public Site Code Lookup

### `GET /api/v1/public/sites/lookup?code=SITE_CODE`

- Auth: none

Response:

- `site_id`
- `site_code`
- `site_name`

Security:

- Public site lookup must return minimal non-sensitive data only.
- It must not return:
  - tenant ID
  - staff data
  - billing data
  - readiness
  - opening hours
  - operational details
- Unknown or inactive sites return a generic not-found response.
- Duplicate active site codes across tenants return a safe ambiguity response.

Use:

- Employee login UI resolves `site_code` to `site_id`.
- Credential validation still uses `POST /api/v1/auth/employee/login`.

---

# Employee Portal Planned Foundation Endpoints

These endpoints are part of the broader Employee Portal target contract but are not all implemented yet.

## `GET /api/v1/employee/home`

Status: planned / future.

Query:

- `store_id?`
- `week_start?`

Response:

- `week_start`
- `available_stores` — always present, list
- `selected_store` — always present
- `my_rota` — published own scheduled shifts, list
- `weekly_rota` — published selected-store scheduled team shifts, list
- `today_operators` — published selected-store scheduled operators today, list
- `today_tasks` — always explicit `null` until task model exists
- `labour_intelligence` — always present when implemented

Empty states:

- No shifts/operators => empty arrays.
- No tasks model => `today_tasks: null`.

---

## `GET /api/v1/employee/me/rota`

Status: implemented in employee published-only rota foundation.

Query:

- `store_id?`
- `week_start?`

Response:

- `week_start`
- `available_stores` — always present where contract supports it
- `selected_store` — always present where contract supports it
- `shifts` — published own scheduled shifts only

Empty state:

- `shifts: []`

Rules:

- Employee token required.
- Own shifts only.
- Published shifts only.
- Draft/unpublished rota is never exposed.
- Cancelled shifts are excluded.

---

## `GET /api/v1/employee/me/labour-intelligence`

Status: planned / future.

Query:

- `store_id?`
- `week_start?`

Response fields, always present when implemented:

- `scheduled_hours_this_week`
- `scheduled_hours_this_month`
- `estimated_pay_this_week`
- `estimated_pay_this_month`
- `monthly_progress_percent`

Truthfulness:

- Scheduled hours are from published scheduled shifts.
- Estimated pay requires hourly profile truth:
  - `pay_type=hourly`
  - `hourly_rate`
- Missing hourly rate => estimated pay fields are `null`.
- Missing hour target => `monthly_progress_percent` is `null`.

---

## `GET /api/v1/employee/me/profile`

Status: planned / future.

Response:

- employee-safe profile fields only
- `roles` always present as list, possibly empty

Rules:

- No admin/internal-only rationale fields are exposed.
- No pay/compliance/private staff fields are exposed.
- No co-worker data is exposed.

---

# Employee Availability Endpoints — Phase L Implemented

## `GET /api/v1/employee/me/availability`

- Auth: employee bearer token
- Query:
  - `week_start` — required
  - `store_id?`

Response:

- `week_start`
- `available_stores`
- `selected_store`
- `items` — self-only availability rows for selected store

Empty state:

- `items: []`

Behaviour:

- Self-only read.
- Store fallback follows Path A.
- Employee can only read availability for their own selected site.
- Cross-tenant/cross-site access returns safe not-found behaviour.

Phase L status:

- Implemented for employee-token sessions.

---

## `POST /api/v1/employee/me/availability`

- Auth: employee bearer token
- Query:
  - `store_id?`

Body:

- `week_start`
- `date`
- `start_time?`
- `end_time?`
- `type`
- `notes?`

Behaviour:

- Self-only write.
- Store fallback follows Path A if `store_id` omitted.
- Duplicate rows => `409 AVAILABILITY_DUPLICATE`.
- Published own scheduled rota in selected week => `409 AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA`.
- Past-date create is blocked with safe validation.

Phase L status:

- Implemented for employee-token sessions.

---

## `DELETE /api/v1/employee/me/availability/{entry_id}`

- Auth: employee bearer token
- Query:
  - `store_id?`

Behaviour:

- Self-only delete.
- Published own scheduled rota in selected week => `409 AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA`.
- Foreign/unknown/cross-tenant rows => `404 AVAILABILITY_NOT_FOUND`.

Phase L status:

- Implemented for employee-token sessions.

---

# Employee Request Endpoints — Phase M / P.4 Implemented

## `GET /api/v1/employee/me/requests`

- Auth: employee bearer token
- Query:
  - `store_id?`
  - `status?`
  - `request_type?`

Response:

- `available_stores`
- `selected_store`
- `items` — own requester requests, plus own targeted requests where applicable

Supported request types:

- `leave`
- `swap`
- `cover`

Empty state:

- `items: []`

Behaviour:

- Employee-token only.
- Self-only.
- Site-scoped.
- Does not expose co-worker private data.

Phase M status:

- Implemented for employee-token sessions.

---

## `POST /api/v1/employee/me/requests`

- Auth: employee bearer token
- Query:
  - `store_id?`

Leave body:

- `request_type=leave`
- `start_date`
- `end_date`
- `reason`

Swap body:

- `request_type=swap`
- `shift_id`
- `target_employee_account_id`
- `target_shift_id`
- `reason`

Cover body:

- `request_type=cover`
- `shift_id`
- `target_employee_account_id?`
- `reason`

Behaviour:

- Self-only write.
- Store fallback follows Path A if `store_id` omitted.
- Creates `pending` request rows only.
- Duplicate pending request => `409 REQUEST_DUPLICATE`.
- Swap/cover requester shifts must be own published scheduled shifts in selected site.
- Swap target must be active and in same tenant/site.
- Swap target shift is required from Phase P.4 onward.
- Swap target shift must belong to the target employee and be published, scheduled, same-tenant, and same-site.
- Swap request creation stores workflow state only and does not mutate rota.
- Cover target is optional.
- When cover target is provided, target must be active and same tenant/site.
- `target_shift_id` is only supported for swap requests.
- Requests do not directly update rota.

Phase M / P.4 status:

- Generic request creation implemented in Phase M.
- Targeted cover support added by Phase P.2.
- Swap target-shift requirement/storage added by Phase P.4.

---

## `POST /api/v1/employee/me/requests/{request_id}/cancel`

- Auth: employee bearer token
- Query:
  - `store_id?`

Behaviour:

- Self-only requester-side cancel.
- Only pending requests can be cancelled.
- Sets status to `cancelled`.
- Unknown/foreign/cross-tenant/cross-site rows => `404 REQUEST_NOT_FOUND`.
- Non-pending rows => `409 REQUEST_NOT_PENDING`.
- Does not update rota.

Phase M status:

- Implemented for employee-token sessions.

---

# Employee Request Target Discovery — Phase P.1 Implemented

## `GET /api/v1/employee/me/request-targets`

- Auth: employee bearer token
- Query:
  - `store_id?`
  - `shift_id?`
  - `request_type?`

Response:

- `available_stores`
- `selected_store`
- `items` — safe same-site target employee rows

Safe item fields:

- `employee_account_id`
- `display_name`
- `role_labels`
- `is_active`

Behaviour:

- Employee-token only.
- Store fallback follows Path A if `store_id` omitted.
- Lists active same-site employee accounts with active linked staff profiles.
- Excludes requester.
- Excludes inactive accounts.
- Excludes inactive staff profiles.
- Excludes cross-site employees.
- Excludes cross-tenant employees.
- Does not expose:
  - username
  - email
  - phone
  - pay
  - earnings
  - compliance data
  - notes
  - tenant ID
  - password/hash
  - availability
  - request history
- If `shift_id` is provided, the shift must be the requester’s own published scheduled shift in the selected site.
- Invalid, foreign, unpublished, or cancelled `shift_id` returns `404 SHIFT_NOT_FOUND`.

Phase P.1 status:

- Implemented for employee-token sessions.

---

# Employee Swap Target Shift Discovery — Phase P.4 Implemented

## `GET /api/v1/employee/me/request-target-shifts`

- Auth: employee bearer token
- Query:
  - `store_id?`
  - `shift_id`
  - `target_employee_account_id`

Response:

- `available_stores`
- `selected_store`
- `items` — safe target employee shift rows

Safe item fields:

- `shift_id`
- `start_time`
- `end_time`
- `role_required`

Behaviour:

- Employee-token only.
- Store fallback follows Path A if `store_id` omitted.
- `shift_id` must be the requester’s own published scheduled shift in the selected site.
- `target_employee_account_id` must be an active same-site/same-tenant employee account with active linked staff profile.
- Returns only target employee published scheduled shifts in the selected site.
- Invalid, foreign, unpublished, or cancelled requester shift returns `404 SHIFT_NOT_FOUND`.
- Invalid, inactive, foreign, cross-site, or cross-tenant target employee returns `404 TARGET_NOT_FOUND`.
- Does not expose:
  - target username
  - target email
  - target phone
  - target pay
  - target earnings
  - target availability
  - target compliance data
  - notes
  - tenant ID
  - internal details

Phase P.4 status:

- Implemented for employee-token sessions.

---

# Employee Inbound Targeted Request Workflow — Phase P.2 / P.4 Implemented

## `GET /api/v1/employee/me/inbound-requests`

- Auth: employee bearer token
- Query:
  - `store_id?`
  - `status?`
  - `request_type?`

Response:

- `available_stores`
- `selected_store`
- `items` — target-only inbound swap/cover requests

Item fields:

- `id`
- `request_type`
- `status`
- `requester_display_name`
- `reason`
- `shift`
  - `id`
  - `start_time`
  - `end_time`
  - `role_required`
- `target_shift` for swap requests
  - `id`
  - `start_time`
  - `end_time`
  - `role_required`
- `created_at`
- `target_decided_at`

Behaviour:

- Employee-token only.
- Store fallback follows Path A if `store_id` omitted.
- Returns only selected-site swap/cover requests where the current employee is `target_employee_account_id`.
- Does not return leave requests.
- Does not expose:
  - requester username
  - requester email
  - requester phone
  - requester pay
  - requester earnings
  - requester availability
  - requester compliance data
  - tenant ID
  - internal notes
  - password/hash data

Phase P.2 / P.4 status:

- Inbound targeted request workflow implemented in Phase P.2.
- Safe swap `target_shift` summary added in Phase P.4.

---

## `POST /api/v1/employee/me/inbound-requests/{request_id}/accept`

- Auth: employee bearer token
- Query:
  - `store_id?`

Behaviour:

- Target employee only.
- Request must be same tenant/site and targeted to current employee.
- Request type must be `swap` or `cover`.
- Request must be pending.
- Sets `status=target_accepted`.
- Writes audit log action `target_accept`.
- Does not approve request.
- Does not update shifts or rota.
- Unknown/foreign/cross-tenant/cross-site/non-target rows => `404 REQUEST_NOT_FOUND`.
- Non-pending rows => `409 REQUEST_NOT_PENDING`.

Phase P.2 status:

- Implemented for employee-token sessions.

---

## `POST /api/v1/employee/me/inbound-requests/{request_id}/decline`

- Auth: employee bearer token
- Query:
  - `store_id?`

Body:

- `decline_reason?`

Behaviour:

- Target employee only.
- Request must be same tenant/site and targeted to current employee.
- Request type must be `swap` or `cover`.
- Request must be pending.
- Sets `status=target_declined`.
- Writes audit log action `target_decline`.
- Does not reject admin-side request.
- Does not update shifts or rota.
- Unknown/foreign/cross-tenant/cross-site/non-target rows => `404 REQUEST_NOT_FOUND`.
- Non-pending rows => `409 REQUEST_NOT_PENDING`.

Phase P.2 status:

- Implemented for employee-token sessions.

---

# Optional Dedicated Swap Endpoints — Future / Optional

The current Phase M/P flow uses generic request endpoints for swap requests.

Dedicated swap endpoints are future/optional only.

## `GET /api/v1/employee/me/swaps`

Status:

- Future / optional dedicated swap endpoint.

Current implementation uses:

- `GET /api/v1/employee/me/requests?request_type=swap`

Query:

- `store_id?`
- `status?`

Intended future response:

- `status`
- `available_stores`
- `selected_store`
- `items` — self-only requester/target swap requests

Intended visibility:

- Selected-store only.
- Published-shift requests only.

Empty state:

- `items: []`

---

## `POST /api/v1/employee/me/swaps`

Status:

- Future / optional dedicated swap endpoint.

Current implementation uses:

- `POST /api/v1/employee/me/requests` with `request_type=swap`

Query:

- `store_id?`

Intended future body:

- `shift_id`
- `target_employee_account_id`
- `target_shift_id`
- `notes?`

Intended future behaviour:

- Delegates to existing swap truth/rules in shift request workflow.
- Shift must be in selected store and published.
- Target shift must be explicitly modelled and validated.
- Invalid state/ownership follows existing deterministic error contract.
- True shift-for-shift swap must not mutate rota unless both shifts are explicitly stored and validated.

---

# Admin Request Approval Queue — Phase N Implemented

## `GET /api/v1/sites/{site_id}/requests`

- Auth: admin-side bearer token
- Query:
  - `status?`
  - `request_type?`

Response:

- `site_id`
- `items` — safe request queue rows

Behaviour:

- Owner/Admin can access tenant sites.
- Manager can access assigned site where `stores.manager_user_id` matches current user.
- Employee tokens are rejected.
- Defaults to pending requests when `status` is omitted.
- Response includes safe display names only.
- Does not expose:
  - employee usernames
  - password data
  - pay data
  - compliance data
  - unrelated profile fields

Phase N status:

- Implemented.

---

## `GET /api/v1/sites/{site_id}/requests/{request_id}`

- Auth: admin-side bearer token

Behaviour:

- Site-scoped safe request detail.
- Unknown/cross-tenant/cross-site rows return `404 REQUEST_NOT_FOUND`.
- Swap/cover details include safe requester shift summary when available.
- Swap details include safe target shift summary when available.
- Does not expose sensitive employee data.

Phase N / P.4 status:

- Request detail implemented in Phase N.
- Safe swap target shift summary added in Phase P.4 where applicable.

---

## `POST /api/v1/sites/{site_id}/requests/{request_id}/approve`

- Auth: admin-side bearer token

Body:

- `approval_reason?`

General behaviour:

- Pending requests can be approved where applicable.
- `target_accepted` swap/cover requests can also be approved.
- Declined, cancelled, rejected, already approved, or otherwise non-actionable rows return `409 REQUEST_NOT_PENDING`.
- Sets:
  - `status=approved`
  - `approver_user_id`
  - `approval_reason`
  - `decided_at`
  - `updated_at`
- Writes audit log action `request_approved`.
- Response includes:
  - `rota_updated`
  - `affected_shift_count`

Phase N status:

- Implemented approval decision recording.

---

## Phase O Leave Approval Behaviour — Implemented

Endpoint:

- `POST /api/v1/sites/{site_id}/requests/{request_id}/approve`

Behaviour:

- For leave requests, approval opens/unassigns affected published scheduled shifts for the requester in the approved date range.
- Affected shifts remain published.
- Approval does not create replacement shifts.
- Approval does not auto-assign another employee.
- Approval does not unpublish rota.
- Approval does not recalculate payroll/earnings yet.

Phase O status:

- Implemented.

---

## Phase P.3 Cover Approval Behaviour — Implemented

Endpoint:

- `POST /api/v1/sites/{site_id}/requests/{request_id}/approve`

Behaviour:

- For target-accepted targeted cover requests, approval reassigns the published scheduled shift from requester to target employee.
- Affected shift remains published.
- Affected shift remains scheduled.
- Affected shift keeps start/end time.
- Cover approval does not create duplicate shifts.
- Cover approval does not hard-delete shifts.
- Cover approval does not unpublish rota.
- Cover approval does not recalculate payroll/earnings yet.
- Untargeted cover approvals remain decision-only.
- Pending targeted cover rows return `409 REQUEST_TARGET_NOT_ACCEPTED`.
- Cover approvals without target acceptance must not mutate rota.
- Request approval and shift reassignment are audit logged.

Phase P.3 status:

- Implemented target-accepted cover rota application.

---
## Phase P.5 Swap Approval Behaviour — Implemented

Endpoint:

- `POST /api/v1/sites/{site_id}/requests/{request_id}/approve`

Current swap behaviour:

- For target-accepted swap requests, admin approval exchanges requester shift and target shift assignments.
- Requester shift assignment changes from requester employee to target employee.
- Target shift assignment changes from target employee to requester employee.
- Both shifts remain published.
- Both shifts remain scheduled.
- Both shifts keep the same start/end times.
- No duplicate shifts are created.
- No shifts are deleted.
- Employee accept/decline does not mutate rota.
- Admin approval is the final authority that applies the swap.
- Request approval and both shift reassignment actions are audit logged.

Validation:

- Swap request must be `target_accepted`.
- Swap request must have requester shift, target employee, and target shift.
- Requester shift must belong to requester.
- Target shift must belong to target employee.
- Both shifts must be same-site and same-tenant.
- Both shifts must be published and scheduled.
- Swap requests that are not target-accepted return `409 REQUEST_TARGET_NOT_ACCEPTED`.

Response:

- `rota_updated: true`
- `affected_shift_count: 2`
- `message: "Swap request approved and both shifts were exchanged."`

Phase P.5 status:

- Implemented target-accepted swap rota application.
---

## `POST /api/v1/sites/{site_id}/requests/{request_id}/reject`

- Auth: admin-side bearer token

Body:

- `rejection_reason?`

Behaviour:

- Only pending requests can be rejected.
- Non-pending rows return `409 REQUEST_NOT_PENDING`.
- Sets:
  - `status=rejected`
  - `approver_user_id`
  - `rejection_reason`
  - `decided_at`
  - `updated_at`
- Writes audit log action `request_rejected`.
- Returns `rota_updated: false`.
- Does not update shifts or rota.

Phase N status:

- Implemented.

---

# Phase P.0 Swap/Cover Workflow Scoping

Phase P.0 status:

- Documentation/scoping only.
- No backend endpoint, database migration, rota mutation, or frontend UI was added in Phase P.0.

Phase P.0 established:

- Cover request state machine.
- Swap request state machine.
- Target co-worker accept/decline rules.
- Admin approval rules.
- Rota mutation boundaries.
- Phase P implementation breakdown.

Important Phase P.0 rules:

- Target accept/decline is workflow-state only.
- Target accept/decline does not mutate rota.
- Admin approval is still required before rota changes.
- Cover rota application can be implemented before swap.
- Full swap rota mutation must wait until target-shift modelling is explicit.
- Notifications, payroll/earnings recalculation, AI actions, and request history hide/restore remain separate future work.

---

# Implemented Through Phase P.5

Implemented:

- Employee request creation/list/cancel under `/api/v1/employee/me/requests`
- Employee-safe same-site target list under `/api/v1/employee/me/request-targets`
- Employee-safe target employee shift discovery under `/api/v1/employee/me/request-target-shifts`
- Employee target-only inbound request list/accept/decline under `/api/v1/employee/me/inbound-requests`
- Admin request queue/detail/approve/reject under `/api/v1/sites/{site_id}/requests`
- Leave approval rota application
- Target-accepted cover approval rota application
- Swap target-shift modelling
- Target-accepted swap approval rota application

Current rota application behaviour:

- Approved leave requests open/unassign affected published scheduled shifts for the requester.
- Target-accepted cover approvals reassign requester shift to accepted target employee.
- Target-accepted swap approvals exchange requester shift and target shift assignments.
- Untargeted cover approvals remain decision-only.

---

# Planned After Phase P.5

Planned:

- Untargeted cover opening/unassignment, if product chooses to support it.
- Request retargeting after target decline.
- Request history hide/restore.
- Notifications.
- Payroll/earnings recalculation after rota changes.
- AI Help request actions.

---

# Intentional Omissions

The following are intentionally not implemented in this contract/current phase set:

- Employee home endpoint
- Labour intelligence endpoint
- Employee-safe profile endpoint
- Dedicated swap endpoints
- Untargeted cover open-cover workflow
- Request retargeting after target decline
- Request history hide/restore
- Task engine
- Attendance/timeclock/worked-hours model
- Payroll engine
- Payroll/earnings recalculation after rota changes
- Notifications
- AI Help request actions