# Phase 17 Employee API Contract (Path A)

## Scope
- Authenticated employee portal API under `/api/v1/employee`
- Derived from existing admin-managed truth only
- No leave/task/attendance/payroll engines in this phase

## Shared Rules
- Auth: bearer token required
- Tenant context: active tenant membership only (`users.active_tenant_id` + `tenant_users`)
- Missing staff profile in tenant: `404 STAFF_PROFILE_NOT_FOUND`
- Cross-tenant access: `404`
- Store access (Path A):
  - Allowed stores are derived from `staff_profiles.store_id`
  - One-store schema returns one `available_stores` item
  - If `store_id` omitted, selected store falls back to assigned/default store
  - Invalid or unauthorized `store_id` returns `404 STORE_NOT_FOUND`
- Employee rota visibility is published-only (`shifts.published_at IS NOT NULL`)

## Endpoints

## Current MVP Addition — Public Site Code Lookup

### `GET /api/v1/public/sites/lookup?code=SITE_CODE`
- Auth: none
- Response:
  - `site_id`
  - `site_code`
  - `site_name`
- Security:
  - Public site lookup must return minimal non-sensitive data only.
  - It must not return tenant ID, staff data, billing data, readiness, opening hours, or operational details.
  - Unknown or inactive sites return a generic not-found response.
  - Duplicate active site codes across tenants return a safe ambiguity response.
- Use:
  - Employee login UI resolves `site_code` to `site_id`.
  - Credential validation still uses `POST /api/v1/auth/employee/login`.

### `GET /api/v1/employee/home`
- Query: `store_id?`, `week_start?`
- Response:
  - `week_start`
  - `available_stores` (always present, list)
  - `selected_store` (always present)
  - `my_rota` (published own scheduled shifts, list)
  - `weekly_rota` (published selected-store scheduled team shifts, list)
  - `today_operators` (published selected-store scheduled operators today, list)
  - `today_tasks` (always explicit `null`)
  - `labour_intelligence` (always present)
- Empty states:
  - No shifts/operators => empty arrays
  - No tasks model => `today_tasks: null`

### `GET /api/v1/employee/me/rota`
- Query: `store_id?`, `week_start?`
- Response:
  - `week_start`
  - `available_stores` (always present)
  - `selected_store` (always present)
  - `shifts` (published own scheduled shifts only)
- Empty state: `shifts: []`

### `GET /api/v1/employee/me/labour-intelligence`
- Query: `store_id?`, `week_start?`
- Response fields (always present):
  - `scheduled_hours_this_week`
  - `scheduled_hours_this_month`
  - `estimated_pay_this_week`
  - `estimated_pay_this_month`
  - `monthly_progress_percent`
- Truthfulness:
  - Scheduled hours are from published scheduled shifts
  - Estimated pay requires hourly profile truth (`pay_type=hourly` and `hourly_rate`)
  - Missing hourly rate => estimated pay fields are `null`
  - Missing hour target => `monthly_progress_percent` is `null`

### `GET /api/v1/employee/me/profile`
- Response:
  - employee-safe profile fields only
  - `roles` always present as list (possibly empty)
- No admin/internal-only rationale fields are exposed

### `GET /api/v1/employee/me/availability`
- Query: `week_start` (required), `store_id?`
- Auth: employee bearer token
- Response:
  - `week_start`
  - `available_stores`
  - `selected_store`
  - `items` (self-only availability rows for selected store)
- Empty state: `items: []`
- Phase L status: implemented for employee-token sessions

### `POST /api/v1/employee/me/availability`
- Query: `store_id?`
- Auth: employee bearer token
- Body:
  - `week_start`, `date`, `start_time?`, `end_time?`, `type`, `notes?`
- Behavior:
  - Self-only write
  - Store fallback as Path A if `store_id` omitted
  - Duplicate rows => `409 AVAILABILITY_DUPLICATE`
  - Published own scheduled rota in selected week => `409 AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA`
  - Past-date create is blocked with safe validation
- Phase L status: implemented for employee-token sessions

### `DELETE /api/v1/employee/me/availability/{entry_id}`
- Query: `store_id?`
- Auth: employee bearer token
- Behavior:
  - Self-only delete
  - Published own scheduled rota in selected week => `409 AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA`
  - Foreign/unknown/cross-tenant rows => `404 AVAILABILITY_NOT_FOUND`
- Phase L status: implemented for employee-token sessions

### `GET /api/v1/employee/me/swaps`
- Query: `store_id?`, `status?`
- Response:
  - `status`
  - `available_stores`
  - `selected_store`
  - `items` (self-only requester/target swap requests)
- Visibility:
  - Selected-store only
  - Published-shift requests only
- Empty state: `items: []`

### `POST /api/v1/employee/me/swaps`
- Query: `store_id?`
- Body:
  - `shift_id`, `target_user_id`, `notes?`
- Behavior:
  - Delegates to existing swap truth/rules in shift request workflow
  - Shift must be in selected store and published
  - Invalid state/ownership follows existing deterministic error contract

### `GET /api/v1/employee/me/requests`
- Query: `store_id?`, `status?`, `request_type?`
- Auth: employee bearer token
- Response:
  - `available_stores`
  - `selected_store`
  - `items` (own requester requests, plus own targeted requests where applicable)
- Supported Phase M request types:
  - `leave`
  - `swap`
  - `cover`
- Empty state: `items: []`
- Phase M status: implemented for employee-token sessions

### `POST /api/v1/employee/me/requests`
- Query: `store_id?`
- Auth: employee bearer token
- Leave body:
  - `request_type=leave`, `start_date`, `end_date`, `reason`
- Swap body:
  - `request_type=swap`, `shift_id`, `target_employee_account_id`, `reason`
- Cover body:
  - `request_type=cover`, `shift_id`, `reason`
- Behavior:
  - Self-only write
  - Store fallback as Path A if `store_id` omitted
  - Creates `pending` request rows only
  - Duplicate pending request => `409 REQUEST_DUPLICATE`
  - Swap/cover shifts must be own published scheduled shifts in selected site
  - Swap target must be active and in same tenant/site
  - Cover target is optional; when provided, target must be active and in same tenant/site
  - Requests do not directly update rota
- Phase M status: implemented for employee-token sessions

### `POST /api/v1/employee/me/requests/{request_id}/cancel`
- Query: `store_id?`
- Auth: employee bearer token
- Behavior:
  - Self-only requester-side cancel
  - Only pending requests can be cancelled
  - Sets status to `cancelled`
  - Unknown/foreign/cross-tenant/cross-site rows => `404 REQUEST_NOT_FOUND`
  - Non-pending rows => `409 REQUEST_NOT_PENDING`
  - Does not update rota
- Phase M status: implemented for employee-token sessions

### `GET /api/v1/employee/me/request-targets`
- Query: `store_id?`, `shift_id?`, `request_type?`
- Auth: employee bearer token
- Response:
  - `available_stores`
  - `selected_store`
  - `items` (safe same-site target employee rows)
- Item fields:
  - `employee_account_id`
  - `display_name`
  - `role_labels`
  - `is_active`
- Behavior:
  - Employee-token only
  - Store fallback as Path A if `store_id` omitted
  - Lists active same-site employee accounts with active linked staff profiles
  - Excludes the requester
  - Excludes inactive accounts, inactive staff profiles, cross-site employees, and cross-tenant employees
  - Does not expose username, email, phone, pay, earnings, compliance data, notes, tenant ID, password/hash, availability, or request history
  - If `shift_id` is provided, the shift must be the requester's own published scheduled shift in the selected site
  - Invalid, foreign, unpublished, or cancelled `shift_id` returns `404 SHIFT_NOT_FOUND`
- Phase P.1 status: implemented for employee-token sessions

### `GET /api/v1/employee/me/inbound-requests`
- Query: `store_id?`, `status?`, `request_type?`
- Auth: employee bearer token
- Response:
  - `available_stores`
  - `selected_store`
  - `items` (target-only inbound swap/cover requests)
- Item fields:
  - `id`
  - `request_type`
  - `status`
  - `requester_display_name`
  - `reason`
  - `shift` with `id`, `start_time`, `end_time`, `role_required`
  - `created_at`
  - `target_decided_at`
- Behavior:
  - Employee-token only
  - Store fallback as Path A if `store_id` omitted
  - Returns only selected-site swap/cover requests where the current employee is `target_employee_account_id`
  - Does not return leave requests
  - Does not expose requester username, email, phone, pay, earnings, availability, compliance data, tenant ID, internal notes, or password/hash data
- Phase P.2 status: implemented for employee-token sessions

### `POST /api/v1/employee/me/inbound-requests/{request_id}/accept`
- Query: `store_id?`
- Auth: employee bearer token
- Behavior:
  - Target employee only
  - Request must be same tenant/site and targeted to current employee
  - Request type must be `swap` or `cover`
  - Request must be pending
  - Sets `status=target_accepted`
  - Writes audit log action `target_accept`
  - Does not approve request
  - Does not update shifts or rota
  - Unknown/foreign/cross-tenant/cross-site/non-target rows => `404 REQUEST_NOT_FOUND`
  - Non-pending rows => `409 REQUEST_NOT_PENDING`
- Phase P.2 status: implemented for employee-token sessions

### `POST /api/v1/employee/me/inbound-requests/{request_id}/decline`
- Query: `store_id?`
- Auth: employee bearer token
- Body:
  - `decline_reason?`
- Behavior:
  - Target employee only
  - Request must be same tenant/site and targeted to current employee
  - Request type must be `swap` or `cover`
  - Request must be pending
  - Sets `status=target_declined`
  - Writes audit log action `target_decline`
  - Does not reject admin-side request
  - Does not update shifts or rota
  - Unknown/foreign/cross-tenant/cross-site/non-target rows => `404 REQUEST_NOT_FOUND`
  - Non-pending rows => `409 REQUEST_NOT_PENDING`
- Phase P.2 status: implemented for employee-token sessions

## Phase N Admin Request Approval Queue

### `GET /api/v1/sites/{site_id}/requests`
- Auth: admin-side bearer token
- Query: `status?`, `request_type?`
- Response:
  - `site_id`
  - `items` (safe request queue rows)
- Behavior:
  - Owner/Admin can access tenant sites.
  - Manager can access assigned site where `stores.manager_user_id` matches current user.
  - Employee tokens are rejected.
  - Defaults to pending requests when `status` is omitted.
  - Response includes safe display names only.
  - Does not expose employee usernames, password data, pay data, compliance data, or unrelated profile fields.
- Phase N status: implemented

### `GET /api/v1/sites/{site_id}/requests/{request_id}`
- Auth: admin-side bearer token
- Behavior:
  - Site-scoped safe request detail.
  - Unknown/cross-tenant/cross-site rows return `404 REQUEST_NOT_FOUND`.
  - Swap/cover details include safe shift summary when available.
- Phase N status: implemented

### `POST /api/v1/sites/{site_id}/requests/{request_id}/approve`
- Auth: admin-side bearer token
- Body:
  - `approval_reason?`
- Behavior:
  - Pending requests can be approved.
  - `target_accepted` swap/cover requests can also be approved.
  - Declined, cancelled, rejected, already approved, or otherwise non-actionable rows return `409 REQUEST_NOT_PENDING`.
  - Sets `status=approved`, `approver_user_id`, `approval_reason`, `decided_at`, and `updated_at`.
  - Writes audit log action `request_approved`.
  - For leave requests, opens/unassigns affected published scheduled shifts for the requester in the approved date range.
  - For target-accepted targeted cover requests, reassigns the published scheduled shift from requester to target employee.
  - For untargeted cover requests, returns `rota_updated: false` and does not update shifts or rota.
  - Pending targeted cover rows return `409 REQUEST_TARGET_NOT_ACCEPTED`.
  - For swap requests, returns `rota_updated: false` and does not update shifts or rota.
  - Response includes `rota_updated` and `affected_shift_count`.
- Phase N status: implemented approval decision recording
- Phase O status: implemented leave-only rota application
- Phase P.3 status: implemented target-accepted cover rota application

### `POST /api/v1/sites/{site_id}/requests/{request_id}/reject`
- Auth: admin-side bearer token
- Body:
  - `rejection_reason?`
- Behavior:
  - Only pending requests can be rejected.
  - Non-pending rows return `409 REQUEST_NOT_PENDING`.
  - Sets `status=rejected`, `approver_user_id`, `rejection_reason`, `decided_at`, and `updated_at`.
  - Writes audit log action `request_rejected`.
  - Returns `rota_updated: false`.
  - Does not update shifts or rota.
- Phase N status: implemented

## Phase P.0 Swap/Cover Workflow Scoping

Phase P.0 status: documentation/scoping only. No backend endpoint, database migration, rota mutation, or frontend UI is added in this phase.

### Implemented Through Phase P.3
- Employee request creation/list/cancel under `/api/v1/employee/me/requests`
- Employee-safe same-site target list under `/api/v1/employee/me/request-targets`
- Employee target-only inbound request list/accept/decline under `/api/v1/employee/me/inbound-requests`
- Admin request queue/detail/approve/reject under `/api/v1/sites/{site_id}/requests`
- Leave approval rota application:
  - approved leave requests open/unassign affected published scheduled shifts for the requester
  - affected shifts remain published
  - request approval and shift updates are audit logged
- Swap approval and untargeted cover approval remain decision-only:
  - `status=approved`
  - `rota_updated=false`
  - `affected_shift_count=0`
- Target-accepted cover approval rota application:
  - approved targeted cover reassigns requester shift to accepted target employee
  - affected shift remains published and scheduled
  - request approval and shift reassignment are audit logged

### Planned After Phase P.3
- Untargeted cover opening/unassignment, if product chooses to support it.
- Swap approval behaviour:
  - full shift-for-shift swap requires explicit target shift modelling
  - current `shift_requests` stores one `shift_id` and one `target_employee_account_id`, but no target shift
  - full swap rota mutation remains deferred until the schema/workflow can represent both sides safely
- Any schema additions needed for target workflow state, target shift selection, or audit detail.

### Phase P Guardrails
- Employee tokens must not access admin request queue endpoints.
- Admin tokens must not access employee-only request endpoints.
- Target acceptance/decline changes request workflow state only.
- Owner/Admin/Manager approval remains tenant-scoped and site-scoped.
- Swap/cover rota mutation must be audit logged when implemented.
- No notifications, payroll/earnings recalculation, AI actions, or request history hide/restore are included in Phase P.0.

## Intentional Omissions
- Task engine
- Attendance/timeclock/worked-hours model
- Payroll engine
- Automatic rota update for swap requests
- Untargeted cover rota application
- Notifications
- AI Help request actions
