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
- Response:
  - `week_start`
  - `available_stores`
  - `selected_store`
  - `items` (self-only availability rows for selected store)
- Empty state: `items: []`

### `POST /api/v1/employee/me/availability`
- Query: `store_id?`
- Body:
  - `week_start`, `date`, `start_time?`, `end_time?`, `type`, `notes?`
- Behavior:
  - Self-only write
  - Store fallback as Path A if `store_id` omitted
  - Duplicate rows => `409 AVAILABILITY_DUPLICATE`

### `DELETE /api/v1/employee/me/availability/{entry_id}`
- Query: `store_id?`
- Behavior:
  - Self-only delete
  - Foreign/unknown/cross-tenant rows => `404 AVAILABILITY_NOT_FOUND`

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

## Intentional Omissions
- Leave requests backend
- Task engine
- Attendance/timeclock/worked-hours model
- Payroll engine
