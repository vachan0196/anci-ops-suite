# ForecourtOS Permission Matrix Current v1

> CURRENT-TRUTH is authoritative as of Phase T.2a: Store lifecycle PATCH bypass fix. It supersedes the previous `5b79955` matrix baseline for store lifecycle PATCH behaviour.
> It is derived from backend guards, handlers, response schemas, and tests.
> Re-grep and update this document after any RBAC/auth/session/router change.
> TARGET rows are product direction, not current enforcement.
> GAP rows must be triaged before onboarding real tenants.

## Scope

This document reconciles implemented backend access control into three layers:

- CURRENT-TRUTH: effective backend access today, not just decorators.
- TARGET: intended product/security direction where known.
- GAP / BACKLOG: differences, sensitive unknowns, and follow-up work.

The old/raw `forecourt_os_permission_matrix_v1.md` file was not present in the local repo when this document was created. No stale PRD permission table was copied into this document.

## How CURRENT-TRUTH Was Derived

Sources inspected:

- Guards/dependencies: `require_tenant_role`, `require_tenant_member`, `_require_admin_portal_role`, `get_current_user`, `get_current_employee_account`, `require_sensitive_admin_action`.
- Router handlers: `auth`, `company`, `stores`, `staff`, `admin_users`, `employee`, `sites`, `shifts`, `shift_requests`, `availability`, `hour_targets`, `coverage_templates`, `rota`, `rota_recommendations`.
- Response/request schemas for returned fields and mutation fields.
- Tests, especially `test_phase_t0_tenant_role_security_gate.py`, R.2d auth tests, employee portal tests, and operational-domain tests.

Tenant isolation is app-layer enforced through active tenant membership plus explicit `tenant_id` and site/store filters. PostgreSQL Row Level Security is not used in the current backend.

## Role And Identity Layers

| Identity | CURRENT-TRUTH | TARGET | GAP / Notes |
|---|---|---|---|
| `owner` tenant role | First registered user. Can obtain Admin Portal sessions. Satisfies `require_tenant_role("admin")` and owner-only dependencies. | Governance and sensitive-control role. Owns company profile, tenant security, billing, and sensitive staff/pay/compliance policy. | Owner/admin split is only partially enforced. |
| `admin` tenant role | Can obtain Admin Portal sessions. Satisfies `require_tenant_role("admin")`. Can access most operational setup and staff management endpoints. Cannot access owner-only company profile or sensitive store deactivation gate. | Operational site/admin role, not tenant governance. Should not manage sensitive pay/RTW/compliance unless explicitly granted later. | Several current staff/admin-user powers exceed target. |
| `member` tenant role | Exists in `tenant_users` for current staff-profile FK compatibility. `member is not Admin Portal access`: it cannot obtain/refresh Admin Portal sessions after R.2d. Legacy/member bearer token can satisfy `require_tenant_member` endpoints, but normal login is blocked. | Not a product-facing Admin Portal role. Should eventually disappear from staff identity once employee/staff identity is decoupled. | Accepted temporary bridge. Continue hardening until decoupled. |
| `employee_account` | Separate employee portal identity. Auth token subject is `employee:{employee_account_id}`. Employee-account-only endpoints use `get_current_employee_account` and require active linked staff profile. | Employee can access only own employee-portal data and safe same-site operational data. | Some older `/api/v1/employee` endpoints still use admin-style user tokens, not employee-account tokens. |
| `manager` | Not implemented as a tenant role. Some store model fields and older docs mention manager concepts; current role set is `owner | admin | member`. | Future product role. | needs-product-decision. |
| platform owner / super-admin | No current backend role found in inspected routers. | Possible future support/admin role if product requires it. | needs-product-decision. |

## CURRENT-TRUTH Matrix

### Auth / Sessions

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Admin register | `POST /api/v1/auth/register` | Public. Creates tenant and first user as `owner`. | Returns `UserOut` with active tenant fields. | `auth.py` register handler, D004. |
| Admin login | `POST /api/v1/auth/login` | Public credential endpoint, but `_require_admin_portal_role` only permits `owner` or `admin` to receive Admin Portal session/token. `member` is blocked. | May return 2FA challenge instead of access token if TOTP active. | `auth.py`, R.2d tests. |
| Admin refresh / 2FA verify / step-up | `/auth/refresh`, `/auth/2fa/verify`, `/auth/2fa/step-up` | Admin continuation is blocked for `member`; employee portal flow remains separate. | Refresh sessions are portal-aware. | `auth.py`, R.2d tests. |
| Employee login | `POST /api/v1/auth/employee/login` | Public credential endpoint. Requires active store/site, matching employee account in that store, active account, and active linked staff profile. | Returns employee access token, refresh token, and `employee_account` summary: `id`, `display_name`, `tenant_id`, `site_id`. | `auth.py`, `auth.EmployeeLoginResponse`. |
| Employee me | `GET /api/v1/auth/employee/me` | Employee-account token only. Admin token rejected by employee dependency. | Returns `portal`, `employee_account_id`, `tenant_id`, `site_id`, `display_name`. | `get_current_employee_account`, T.0 tests. |

### Company

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Company profile read | `GET /api/v1/company/profile` | Owner-only via `require_tenant_role("owner")`. Admin/member/employee tokens are rejected. Active tenant only. | Returns `tenant_id`, company fields, setup flags. | `company.py`, `CompanyProfileRead`, T.0 tests. |
| Company profile update | `PATCH /api/v1/company/profile` | Owner-only. Mutates active tenant only. | Accepts company name, owner name, business email, phone, registered address. | `company.py`, `CompanyProfileUpdate`, T.0 tests. |

### Stores / Sites Setup

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Create store | `POST /api/v1/stores` | Owner/admin via `require_tenant_role("admin")`. Member cannot normally get admin session; legacy member token would fail role check. | Accepts code, name, timezone, address/city/postcode/phone, `manager_user_id`; manager must be tenant member if set. Returns `StoreOut` including `tenant_id` and `manager_user_id`. | `stores.py`, `StoreCreate`, `StoreOut`. |
| List stores | `GET /api/v1/stores` | Any active tenant member dependency. In normal sessions, owner/admin. Legacy member token can list active-tenant stores. Employee-account token rejected. | Returns `StoreOut` list scoped by `tenant_id`; inactive excluded unless requested. | `stores.py`, T.0 tests. |
| Store detail | `GET /api/v1/stores/{store_id}` | Any active tenant member dependency. Cross-tenant store ID returns `404 STORE_NOT_FOUND`. | Returns full `StoreOut`. | `stores.py`, T.0 tests. |
| Store update | `PATCH /api/v1/stores/{store_id}` | Owner/admin. Cross-tenant store ID returns 404 for valid update fields. Ordinary PATCH cannot change lifecycle/deactivation state; `is_active` is not accepted by `StoreUpdate` and is rejected as an extra field. | Can update normal store profile/config fields such as code, name, timezone, address/city/postcode/phone, and `manager_user_id`. Cannot deactivate or reactivate a store. | `stores.py`, `StoreUpdate`, T.2a tests. |
| Store readiness | `GET /api/v1/stores/{store_id}/readiness` | Any active tenant member dependency. Cross-tenant store ID returns 404. | Returns readiness booleans based on opening-hours and active staff counts; no staff details. | `stores.py`, T.0 tests. |
| Opening hours read/write | `GET/PUT /api/v1/stores/{store_id}/opening-hours` | Read: active tenant member. Write: owner/admin. Store must belong to active tenant. | Returns day, open/close time, closed flag. | `stores.py`, `OpeningHoursResponse`. |
| Store settings read/write | `GET/PATCH /api/v1/stores/{store_id}/settings` | Read: active tenant member. Write: owner/admin. Store must belong to active tenant. | Current setting is `business_week_start_day`. | `stores.py`, `StoreSettingsResponse`. |
| Deactivate store | `POST /api/v1/stores/{store_id}/deactivate` | Sensitive action: owner-only, verified email, active 2FA, fresh step-up, valid admin session, active-tenant store. | Sets `is_active = false`. | `stores.py`, `require_sensitive_admin_action`, Q.5.2a tests. |

### Staff And Staff Roles

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Staff list | `GET /api/v1/staff` | Owner/admin. Tenant-scoped. | Returns `StaffProfileOut`, including sensitive `hourly_rate`, `pay_type`, `rtw_status`, `rtw_checked_at`, `rtw_checked_by_user_id`, `employee_account_id`, emergency contact, contract type, notes. No role-specific field filtering found. | `staff.py`, `StaffProfileOut`, T.0 tests. |
| Staff create | `POST /api/v1/staff` | Owner/admin. Requires existing tenant `user_id`. Optional employee account is created if `employee_username` and `employee_password` are supplied together. | Accepts and returns pay/RTW fields. `employee_password` is hashed into `EmployeeAccount` and is not returned. `employee_username` is stored on `EmployeeAccount` and not returned in `StaffProfileOut`; `employee_account_id` is returned. | `staff.py`, `StaffProfileCreate`, `StaffProfileOut`. |
| Staff directory | `GET /api/v1/staff/directory` | Owner/admin. Tenant-scoped. | Returns safer directory fields: id, user_id, display name, email, job title, phone, store, roles, active, created_at. Does not include pay/RTW fields. | `staff.py`, `StaffDirectoryItem`, T.0 tests. |
| Staff detail | `GET /api/v1/staff/{staff_id}` | Active tenant member dependency. Owner/admin can read any staff profile in active tenant. Non-admin member can read only own profile. Cross-tenant returns 404. | Returns full `StaffProfileOut` including pay/RTW fields. | `staff.py`, T.0 tests. |
| Staff self | `GET/PATCH /api/v1/staff/me` | Active tenant member dependency. Reads own profile; patches only phone and emergency contact fields. | GET returns full `StaffProfileOut`, including own pay/RTW fields. PATCH response also returns full `StaffProfileOut`. | `staff.py`, `StaffSelfUpdate`. |
| Staff update | `PATCH /api/v1/staff/{staff_id}` | Owner/admin. Tenant-scoped. | Can update pay/RTW fields, contract, notes, active state, store, and basic profile. No owner-only or field-level sensitive gate found. | `staff.py`, `StaffProfileUpdate`, T.0 tests. |
| Staff roles | `GET/POST /api/v1/staff/{staff_id}/roles`, `DELETE /api/v1/staff/{staff_id}/roles/{role}` | Owner/admin. Tenant-scoped by staff profile and staff role rows. | Role labels are free-form normalized strings in `staff_roles`, separate from tenant role. | `staff.py`, `StaffRoleOut`. |

### Admin Users

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Create tenant user | `POST /api/v1/admin/users` | Owner/admin via `require_tenant_role("admin")`. | Allowed tenant roles today are `admin` and `member`; `owner` cannot be created here. Creates `users` row and `tenant_users` membership in active tenant. | `admin_users.py`, `AdminUserCreate`. |
| Member creation | `POST /api/v1/admin/users` with `role=member` | Allowed today for staff FK compatibility. Created member cannot obtain Admin Portal token through normal auth. | Current staff flow often creates member user first, then staff profile. | R.2d docs/tests, `admin_users.py`, `staff.py`. |

### Employee Portal

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Employee-account rota | `GET /api/v1/employee/rota/my` | Employee-account token only. Self-only by employee account -> staff profile -> assigned user. Published scheduled shifts only. | Returns `week_start`, `site_id`, `employee_account_id`, shift id/start/end/role/status. | `employee.py`, `EmployeeMyRotaRead`. |
| Employee availability | `GET/POST/DELETE /api/v1/employee/me/availability` | Employee-account token only. Self-only by `employee_account_id`, staff user, tenant, and selected store. Wrong site/store or cross-tenant store returns 404. | Returns availability rows with `employee_account_id`, site/store IDs, dates/times/type/notes. | `employee.py`, T.0 tests. |
| Employee requests | `GET/POST /api/v1/employee/me/requests`, cancel endpoint | Employee-account token only. Lists requester/target requests for that employee account in selected site. Creates leave/swap/cover requests only for own eligible shifts and same-site targets. | Returns request IDs, type/status, site ID, shift IDs, requester/target employee account IDs, dates, reason, timestamps. | `employee.py`, T.0 tests, Phase M/P tests. |
| Employee request targets | `GET /api/v1/employee/me/request-targets` | Employee-account token only. Same selected site, active staff profile/account, excludes self. | Returns employee account ID, display name, role labels, active. No pay/RTW fields. | `employee.py`, `EmployeeRequestTargetRead`. |
| Employee inbound requests | `GET/POST /api/v1/employee/me/inbound-requests/...` | Employee-account token only. Target-only for swap/cover inbound requests in selected site. | Returns requester display name, reason, shift summaries; no pay/RTW fields. | `employee.py`, `EmployeeInboundRequestRead`. |
| Employee profile | `GET /api/v1/employee/me/profile` | CURRENT-TRUTH: uses admin-style `get_current_user` + `require_tenant_member`, not employee-account token. Normal `member` cannot login after R.2d, but a legacy member bearer token can call it. | Returns `pay_type` and `hourly_rate` for own staff profile; does not return `rtw_status`, `rtw_checked_at`, `rtw_checked_by_user_id`, notes, or employee account ID. | `employee.py`, `EmployeeProfileRead`. |
| Employee home / me rota / labour intelligence | `GET /api/v1/employee/home`, `/employee/me/rota`, `/employee/me/labour-intelligence` | CURRENT-TRUTH: use admin-style user token + tenant membership, not employee-account token. Self staff-profile/store scoping. | Labour intelligence returns estimated pay derived from `pay_type` and `hourly_rate`; weekly rota exposes same-site published team shift names. | `employee.py`, `EmployeeHomeRead`, `EmployeeLabourIntelligenceRead`. |

### Operational Rota / Shifts / Requests

| Area | Endpoint(s) | CURRENT-TRUTH | Field / Data Notes | Evidence |
|---|---|---|---|---|
| Site request queue | `GET /api/v1/sites/{site_id}/requests`, detail | Active tenant member dependency plus `_get_authorized_site_or_404`. Owner/admin and legacy member tokens can read site requests if authorized. | Returns requester/target employee account IDs/display names, reason, shift IDs, dates, approver fields. No pay/RTW. | `sites.py`, `site_request.py`. |
| Site request approve/reject | `POST /api/v1/sites/{site_id}/requests/{request_id}/approve|reject` | Active tenant member dependency, not admin-only. `_get_authorized_site_or_404` limits site access; manager-specific behavior exists only if `manager_user_id` matches current user. | Mutates request status and can mutate rota for leave/cover/swap approval. | `sites.py`. TARGET is needs-product-decision. |
| Site weekly rota | `GET /api/v1/sites/{site_id}/rota/week` | Active tenant member dependency, site must belong to active tenant. | Returns shift ID, assigned employee account ID, role, start/end; no pay/RTW. | `sites.py`, `WeeklyRotaRead`. |
| Site rota publish/unpublish | `POST /api/v1/sites/{site_id}/rota/publish|unpublish` | Owner/admin. Tenant/site-scoped. | Mutates published flags. | `sites.py`. |
| Site shift CRUD | `POST/PATCH/CANCEL /api/v1/sites/{site_id}/shifts...` | Owner/admin. Tenant/site-scoped. Assigned employee account must belong to same tenant/site. | Returns weekly rota shift fields only. | `sites.py`, `rota.py`. |
| Core shifts | `/api/v1/shifts` family | Create/update/assign/cancel/publish/unpublish/status: owner/admin. List/detail: active tenant member; non-admin sees own assigned shifts, optionally open shifts on list. | `ShiftRead` includes tenant/store/user IDs, role, status, published, override flags/reasons. | `shifts.py`, `shift.py`. |
| Core shift requests | `/api/v1/shift-requests` family | Create/list/cancel/accept/decline: active tenant member with ownership/target filters. Approve/reject: owner/admin. Tenant-scoped through shift/request joins. | `ShiftRequestRead` includes tenant ID, requester/target user IDs, notes. | `shift_requests.py`, `shift_request.py`. |
| Availability admin/member API | `/api/v1/availability` | Create/delete own availability: active tenant member. List: owner/admin can list tenant availability and filter by user; non-admin sees own only. | `AvailabilityRead` includes tenant ID and user ID. | `availability.py`, `availability.py` schema. |
| Hour targets | `/api/v1/hour-targets` | Put/list/delete: owner/admin. `/me`: active tenant member self-only. | Returns min/max/target hours and notes. May be sensitive scheduling/labour data. | `hour_targets.py`, `HourTargetRead`. |
| Coverage templates | `/api/v1/coverage-templates` | Owner/admin only, tenant/store-scoped. | Returns required headcount/role/time windows. | `coverage_templates.py`. |
| Rota generation | `POST /api/v1/rota/generate-week` | Owner/admin, store must belong to active tenant. | Generates draft shifts from coverage templates. | `rota.py`. |
| Rota recommendations | `/api/v1/rota-recommendations` | Owner/admin only. Tenant/store/draft scoped. | Can propose/apply shift assignments. Detailed target policy not reviewed in T.1. | `rota_recommendations.py`. |

## TARGET Matrix

| Area | TARGET |
|---|---|
| Member identity | `member` is not a product-facing Admin Portal role and should eventually disappear from normal staff/employee identity after staff profile identity is decoupled. |
| Owner/admin split | Owner handles governance, security, billing, company profile, and sensitive staff/pay/compliance controls. Admin handles site operations. |
| Company | Owner manages company profile. Admin should not manage tenant governance profile by default. |
| Stores/sites | Admin operational access is accepted for normal site setup/configuration. Destructive or governance-sensitive site actions should use owner/sensitive-action gates. |
| Staff pay/RTW | Pay and right-to-work/compliance fields should be owner-only for MVP unless explicitly changed. |
| Admin users | Creating privileged users is a governance/security-sensitive action and should move toward owner plus verified email/2FA/step-up when UX supports it. |
| Employee data | Employee can access only own employee-portal data. Employee should not access co-worker private data. Employee should not see full staff pay/RTW/compliance profile. Future pay visibility may expose employee-safe earnings/pay summaries, not full compliance/pay administration fields. |
| Rota/shifts/requests | Admin operational access scope needs product decision. Do not infer detailed target rules beyond tenant/site isolation and employee self/target constraints. |
| Manager | Future `manager` role needs explicit product decision before implementation or test oracle use. |
| Platform owner | Future platform/support role needs explicit product decision before implementation or test oracle use. |

## GAP / BACKLOG Matrix

| Area | CURRENT-TRUTH | TARGET | Risk | Triage | Suggested phase/backlog |
|---|---|---|---|---|---|
| Staff pay/RTW admin read | Owner/admin can read `hourly_rate`, `pay_type`, `rtw_status`, `rtw_checked_at`, `rtw_checked_by_user_id` via `GET /staff`, `GET /staff/{id}`, `GET /staff/me` response shape for own profile. | Pay/RTW owner-only for MVP unless explicitly granted. | Sensitive employee data exposure to operational admins. | fix-before-onboarding | H081 / T.2 field-level gate or response split. |
| Staff pay/RTW admin write | Owner/admin can create/update pay and RTW fields through `POST /staff` and `PATCH /staff/{id}`. | Owner-only or explicit sensitive permission; likely step-up for writes. | Unauthorized pay/compliance changes by operational admins. | fix-before-onboarding | H060/H073/H081; dedicated pay/compliance endpoint or conditional field gate. |
| Staff self full response | Legacy member-token `GET /staff/me` and `PATCH /staff/me` return full `StaffProfileOut`, including pay/RTW fields. | Employee/member self APIs should return employee-safe fields only, with any pay display intentionally designed. | Sensitive-field leakage through legacy bearer tokens. | unverified-sensitive-field | T.2/T.3 after staff identity decision. |
| Employee profile own pay fields | `/employee/me/profile` returns own `pay_type` and `hourly_rate`; labour intelligence returns estimated pay. It does not return RTW fields. | Employee pay visibility needs product decision; no full compliance/pay administration fields. | Could be acceptable self-pay transparency or unintended exposure. | needs-product-decision | Product decision before using as oracle. |
| Employee route identity split | Some `/api/v1/employee` endpoints use employee-account tokens; others use admin-style user token plus `tenant_users`. | Employee portal should consistently use employee-account identity. | Confusing token boundary and legacy member-token surface. | fix-before-onboarding | Staff identity decoupling / employee API consolidation. |
| Admin user creation | Owner/admin can create `admin` and `member` users. | Privileged user creation should be owner/governance-controlled and likely sensitive-action gated. | Admin can create another admin. | fix-before-onboarding | H060/H073/H081; T.2 tests after decision. |
| Member FK bridge | `member` tenant users can still be created for staff setup because `staff_profiles.user_id` is required. | Remove product-facing `member` from staff identity path. | Identity model complexity and accidental auth surface. | accepted-temporary-MVP | H080 / R.2e. |
| Store update `is_active` | RESOLVED in T.2a: ordinary `PATCH /stores/{id}` rejects `is_active` and cannot change lifecycle state. Deactivation remains through the protected sensitive-action endpoint. | Destructive/deactivation semantics should consistently use sensitive-action gate. Reactivation remains undesigned. | Bypass closed; no current reactivation workflow. | accepted-temporary-MVP | Future lifecycle/reactivation design if product needs it. |
| Site request approve/reject | `/sites/{site_id}/requests/{request_id}/approve|reject` uses active tenant member plus site authorization, not admin-only. | Operational approval target policy is unclear. | Legacy member token could approve/reject if site-authorized; role intent unclear. | needs-product-decision | T.2/T.3 operational RBAC decision. |
| Operational admin scope | Rota, shifts, requests, availability admin APIs, hour targets, coverage templates, rota recommendations mostly allow owner/admin; some list/self actions allow member-scoped access. | Detailed admin/manager/member operational policy needs product decision. | Tests may codify broad admin/member behavior without intended policy. | needs-product-decision | T.2/T.3 matrix-backed expansion. |
| Hour targets sensitivity | Owner/admin can manage hour targets; members can read own targets. | Labour/scheduling target sensitivity policy not decided. | Potential sensitive labour-planning exposure. | needs-product-decision | Product/security review. |
| Manager role | Store `manager_user_id` exists, but no current tenant `manager` role. Some site helper logic treats manager assignment specially. | Future manager role must be explicit. | Ambiguous site-scope authority. | needs-product-decision | Manager role design phase. |
| Platform owner | No current implementation. | Future support role may be needed. | None current; future support access can become high-risk. | future-hardening | Future platform admin design. |

## UNVERIFIED Rows

UNVERIFIED is used only where T.1 did not fully prove effective field-level or policy intent.

| Area | Status | Reason | Triage |
|---|---|---|---|
| Rota recommendation detail field sensitivity | UNVERIFIED | T.1 confirmed owner/admin guards and tenant scoping, but did not fully enumerate every `DraftDetailRead` nested field and recommendation item exposure. | needs-product-decision |
| Operational rota/request target policy | UNVERIFIED | Current guards are clear, but target policy for which roles should approve/publish/reassign rota is not defined in local docs. | needs-product-decision |
| Employee own pay visibility | UNVERIFIED | Current code returns own `pay_type`, `hourly_rate`, and estimated pay, but local target docs do not decide whether this is intended MVP self-service pay visibility. | needs-product-decision |
| Staff self pay/RTW legacy surface | UNVERIFIED | `StaffProfileOut` includes sensitive fields and `/staff/me` can return it for tenant-member tokens; intended legacy-member behavior is not product-decided after R.2d. | unverified-sensitive-field |

## T.2 Test Oracle Guidance

Use CURRENT-TRUTH as the initial T.2 oracle only for behavior explicitly marked verified above. Do not turn TARGET or UNVERIFIED rows into tests without a product/security decision. Cross-tenant isolation remains absolute and should fail as a bug wherever found.
