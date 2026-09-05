# HARDENING_BACKLOG.md — ForecourtOS / Anci Ops Suite

**Last updated:** 2026-09-05

## Purpose

This file tracks commercial SaaS hardening work required before and after first paying customer onboarding.

ForecourtOS is a real multi-tenant commercial SaaS product. It handles employee data, rota decisions, future billing, and future AI-assisted workflows. Hardening work must be treated as product-critical, not optional cleanup.

## Severity Legend

- 🔴 Critical / launch-blocking
- 🟡 Important / near-term hardening
- 🟢 Later / scale or maturity improvement

## Current Focus

The availability and recommendation input chain is complete and E2E-tested, and the admin recommendation loop is now self-service for generate, discard/regenerate, apply, and publish. Current follow-ups are future employee/admin availability precedence rules, availability date/timezone boundary hardening, Rota.2 editor polish, H085 rota assignment identity contract cleanup before EP.0, RecommendationUI regenerate atomicity, employee-portal test failures surfaced after rate-limit noise was cleared, Staff.1L staff lifecycle design, H083 owner-only staff pay/RTW UI with step-up/audit, and future staff identity decoupling.

## Items

### H047 — Fix passlib `crypt` deprecation warning

**Severity:** 🔴
**Status:** Done
**Area:** Authentication / password hashing
**Concern:** Recent test runs repeatedly emitted passlib `crypt` deprecation warnings under Python 3.12, touching password hashing and creating launch risk.
**Fix:** Removed passlib from the active password hashing path and use the maintained `bcrypt` package directly while preserving bcrypt hash format, 72-byte password validation, admin login, and employee login behavior.
**Suggested phase:** Phase Q.0

---

### H048 — Baseline Sentry/error tracking

**Severity:** 🟡
**Status:** Done
**Area:** Observability / error tracking
**Concern:** Commercial launch needs a safe error tracking hook without requiring local developers to configure third-party services.
**Fix:** Added optional backend Sentry initialization controlled by `SENTRY_DSN`, with request header/cookie/body redaction and `send_default_pii=False`. Frontend Sentry setup remains separate future work.
**Suggested phase:** Phase Q.0

---

### H049 — Auth/public endpoint rate limiting

**Severity:** 🔴
**Status:** Done
**Area:** Auth / abuse protection
**Concern:** Public auth and site lookup endpoints must slow password spraying and brute-force lookup patterns before commercial use.
**Fix:** Verified the existing SlowAPI limiter is configurable with `RATE_LIMIT_ENABLED`, uses deterministic `429 RATE_LIMIT_EXCEEDED` responses, and protects admin login, employee login, and public site lookup endpoints. Q.5.1a added explicit `POST /api/v1/auth/2fa/verify` route limiting with `RATE_LIMIT_2FA_VERIFY=5/minute`. Redis-backed distributed limiting remains a future production scaling item.
**Suggested phase:** Phase Q.0

---

### H050 — Secret scanning baseline

**Severity:** 🟡
**Status:** Done
**Area:** Secrets / developer workflow
**Concern:** Commercial development needs a documented way to scan for accidentally committed secrets before production-like deployment.
**Fix:** Added README hardening commands for local `gitleaks detect --source . --log-opts="--all"` usage and added a GitHub Actions gitleaks secret-scan job. No production secrets or `.env` files were added.
**Suggested phase:** Phase Q.0 / Q.1

---

### H051 — Minimal CI hardening gate

**Severity:** 🔴
**Status:** Done
**Area:** CI/CD / release safety
**Concern:** Without CI, production safety depends on manual local checks.
**Fix:** Added GitHub Actions workflow for backend Docker build, Alembic migration check, backend pytest suite, frontend build, TypeScript check, and secret scanning.
**Suggested phase:** Phase Q.1

---

### H052 — Phase 17 P.5 contract cleanup

**Severity:** 🟡
**Status:** Done
**Area:** API contract / documentation truth
**Concern:** Phase 17 API contract summaries must reflect that target-accepted swap approval now exchanges both shift assignments.
**Fix:** Verified and kept the Phase 17 summary at Implemented Through Phase P.5, Planned After Phase P.5, and removed completed swap rota update omission.
**Suggested phase:** Phase Q.0

---

### H053 — Frontend Sentry/error tracking foundation

**Severity:** 🟡
**Status:** Deferred
**Area:** Observability / frontend
**Concern:** Frontend runtime errors are invisible without browser-side error tracking.
**Fix:** Deferred to a later hardening phase because adding Next.js Sentry requires new frontend package/configuration and source-map decisions. Backend Sentry remains enabled via H048; README documents the future `NEXT_PUBLIC_SENTRY_DSN` convention.
**Suggested phase:** Phase Q.4 or later

---

### H054 — Dependency update monitoring

**Severity:** 🟡
**Status:** Done
**Area:** Supply chain security
**Concern:** Python/npm/GitHub Actions dependencies need ongoing review.
**Fix:** Added Dependabot configuration for API Python requirements, frontend npm dependencies, and GitHub Actions.
**Suggested phase:** Phase Q.1

---

### H055 — Request ID / structured logging baseline

**Severity:** 🟡
**Status:** Done
**Area:** Observability / operations
**Concern:** Incident response needs request correlation across logs, API responses, and Sentry events.
**Fix:** Verified request IDs are attached to logs, added `X-Request-ID` response header propagation, and added API tests for generated and propagated request IDs.
**Suggested phase:** Phase Q.1

---

### H056 — Replace localStorage token storage with production-safe session model

**Severity:** 🔴
**Status:** Done
**Area:** Authentication / session security
**Concern:** Admin and employee access tokens were stored in browser localStorage during the compatibility window, which was not production-safe for commercial SaaS because XSS could expose tokens.
**Fix:** Phase Q.2 added the backend production-safe session foundation: `auth_sessions` with hashed refresh/session tokens, portal-aware admin/employee sessions, refresh rotation, logout revocation, additive HTTP-only refresh cookie support, and disabled user/employee/staff-profile blocking. Phase Q.3.1 migrated active frontend access-token handling to memory-only storage restored through the HTTP-only refresh cookie, clears legacy localStorage token keys `forecourt_access_token` and `forecourt_employee_access_token`, and preserves bearer-token compatibility during the deprecation window.
**Suggested phase:** Phase Q.2 / Q.3

---

### H057 — Refresh token and logout revocation model

**Severity:** 🔴
**Status:** Done
**Area:** Authentication / session lifecycle
**Concern:** Production sessions need revocable refresh tokens and clear logout behaviour. Without this, disabled users or compromised sessions may remain risky until token expiry.
**Fix:** Phase Q.2 added server-side `auth_sessions` persistence using hashed refresh/session tokens, `POST /api/v1/auth/refresh` with portal-aware refresh rotation, and `POST /api/v1/auth/logout` with refresh/session revocation. Revoked refresh/session tokens cannot be reused, and disabled admin users, disabled employee accounts, and inactive linked staff profiles are blocked on protected requests.
**Suggested phase:** Phase Q.2

---

### H058 — Password reset flow

**Severity:** 🟡
**Status:** Done — backend foundation; product flow incomplete
**Area:** Authentication / account recovery
**Concern:** Admin users need a secure password reset flow before production onboarding.
**Fix:** Phase Q.4.2 added the admin-side password reset backend with generic request responses, hashed single-use `password_reset` tokens, 1-hour expiry, atomic token consumption, safe rejection classification, Q.4.1 email service usage, and active admin session revocation after successful reset.
**Suggested phase:** Phase Q.4

**2026-09-03.** The Q.4.2 backend is complete and correct. The product flow is
not completable by a human at HEAD, for two independent reasons:

1. human-reachable delivery does not exist — tracked by H132; and
2. `/admin/reset-password?token=...` is not implemented in `apps/web`, as
   Q.4.2's own record states.

`local_log` is the active EmailService and redacts `reset_url`; the raw token
exists only in request memory and `auth_tokens` stores only a SHA-256 hash.

H132 owns the delivery gap. Closing H132 alone does not complete password reset
— the missing frontend reset route is the second blocker. Delivery closes in
Q.5.3a-1; the frontend reset route closes in Q.5.3a-2. H058 is not
product-complete until H138 closes, because recovery currently works only for
lowercase addresses: an account registered with any uppercase character can log
in but cannot recover.

---

### H059 — Email verification for admin-side accounts

**Severity:** 🟡
**Status:** Done — backend foundation; product flow incomplete
**Area:** Authentication / onboarding security
**Concern:** Owner/Admin accounts should verify email ownership before production use, especially before billing and sensitive access.
**Fix:** Phase Q.4.3 added the admin-side email verification backend foundation with `users.email_verified_at`, authenticated request/resend, public confirm, hashed single-use `email_verification` tokens, 24-hour expiry, atomic token consumption, safe rejection classification, already-verified handling, Q.4.1 email service usage, and safe auth security events. Per D038, unverified admin users can still log in; sensitive-action enforcement was deferred to H073 at the time of Q.4.3. **Corrected 2026-09-03:** that enforcement landed in Q.5.2a, which checks `email_verified_at` at `deps.py:262`. H073 remains Partial, and H130 records that the gate is live but unreachable through the product.
**Suggested phase:** Phase Q.4

**2026-09-03.** Q.4.3's email-verification backend is complete. The product
journey is not complete at HEAD: human-reachable delivery is blocked by H132,
and the verification frontend journey is tracked by H130. Delivery closes in
Q.5.3a-1; the verification frontend journey closes in Q.5.3a-2.

---

### H060 — 2FA for Owner and sensitive actions

**Severity:** 🔴
**Status:** Partial
**Area:** Authentication / sensitive action protection
**Concern:** Owner-only areas such as payroll, billing, compliance documents, destructive actions, and tenant-level settings require stronger protection before commercial launch.
**Fix:** Add 2FA baseline for Owner login and/or sensitive action re-authentication, with audit logging and recovery rules. Phase Q.4.4 resolved the prerequisite Owner/Admin role split. D039 records the Q.5 design. Q.5.1 implemented the backend TOTP enrolment, login challenge verification, encrypted TOTP secret storage, and recovery-code use loop. Q.5.1b added rate-limited disable 2FA and recovery-code regeneration endpoints with recovery-code consumption, old-code invalidation, and safe auth security events. Q.5.2a added the server-side step-up mechanism and wired it to store deactivation. Q.5.2b inspected remaining current endpoints and decided not to wire additional endpoints yet. Remaining work includes admin-user privilege creation/change when onboarding/frontend step-up UX is available; staff pay/compliance conditional or dedicated gating when those flows are built; and future billing, payroll, compliance, export, audit-log, and erasure modules at build time. 
Staff.2 and Staff.2b hardened current staff pay/RTW read and write exposure by making `hourly_rate`, `pay_type`, and `rtw_status` Owner-only in staff admin APIs. Fresh 2FA/step-up for future owner-only pay/RTW UI remains future work when that UI is built.

**Suggested phase:** Future product/security phase
---

### H061 — CSRF protection for cookie-based session model

**Severity:** 🔴
**Status:** Done
**Area:** Authentication / browser session security / CSRF
**Concern:** Phase Q.2 added HTTP-only refresh cookie support, and D036 chose cookie-backed frontend session migration. Cookie-backed frontend auth must not ship without CSRF protection, because browser cookies can be sent automatically with cross-site requests depending on deployment/cookie settings.
**Fix:** Implemented D036 in Q.3.1. Cookie-backed `/api/v1/auth/refresh` and `/api/v1/auth/logout` now require the custom header `X-Requested-With: ForecourtOS`. The refresh cookie uses `SameSite=Strict`, `HttpOnly`, path `/api/v1/auth`, host-only domain behaviour, and TTL from `REFRESH_TOKEN_EXPIRE_DAYS`. Body refresh-token compatibility remains available where supported, and bearer-token protected endpoints are not broadly gated by CSRF header enforcement.
**Suggested phase:** Phase Q.3.1
**Blocking:** Resolved in Q.3.1 for cookie-backed refresh/logout.

---

### H062 — Frontend auth cookie/session migration

**Severity:** 🔴
**Status:** Done
**Area:** Authentication / frontend session security
**Concern:** Phase Q.2 added the backend refresh/session foundation, but the frontend still used localStorage token storage during the compatibility window. Browser localStorage access tokens were exposed to XSS and were not production-safe for commercial SaaS.
**Fix:** Implemented D036 in Q.3.1. Admin Portal and Employee Portal active access tokens are now memory-only and restored through the HTTP-only refresh cookie. Legacy localStorage keys `forecourt_access_token` and `forecourt_employee_access_token` are cleared during migration/login/logout paths. The stale key `employee_access_token` is not used as an active key. Refresh uses `credentials: "include"` and `X-Requested-With: ForecourtOS`; refresh-on-401 retries once and shares one in-flight refresh attempt per portal; logout calls `/api/v1/auth/logout`, revokes the server-side session, and clears local auth state. Admin and employee flows both restore sessions through the refresh cookie.
**Suggested phase:** Phase Q.3.1

---

### H064 — Supply chain hardening against slopsquat / hallucinated packages

**Severity:** 🟡
**Status:** Done
**Area:** Supply chain security
**Concern:** AI-assisted development can introduce hallucinated package names that attackers register on PyPI/npm with malicious code. Dependabot and gitleaks do not fully protect against this attack vector.
**Fix:** Phase Q.2.2 added a written dependency verification policy in D035, GitHub Dependency Review Action for pull requests, Python dependency audit via `pip-audit`, npm high-severity audit gate via `npm audit --audit-level=high`, and README supply-chain hardening checks. Phase Q.2.2.1 then audited existing direct Python/npm dependencies and found no slopsquat-style anomalies.
**Suggested phase:** Phase Q.2.2 / Q.2.2.1

---

### H065 — Audit logging for auth/session events

**Severity:** 🟡
**Status:** Done
**Area:** Authentication / auditability / incident response
**Concern:** Refresh/session issued, rotated, revoked, rejected, and blocked events were not clearly audit-logged. The existing `audit_logs` table requires non-null `tenant_id` and `user_id`, so it cannot safely represent unresolved auth/security events such as unknown invalid refresh tokens without fake tenant/user values.
**Fix:** Implemented D037 by adding a dedicated `auth_security_events` table and writing auth/session lifecycle events to it. Events use the exact Q.3.2.1 vocabulary, nullable subject/session references, safe request context, rejection reason where applicable, and never store raw tokens, token hashes, passwords, cookies, authorization headers, or secret material.
**Suggested phase:** Phase Q.3.2.1

---
### H066 — Refresh token reuse detection / session family pattern

**Severity:** 🟡
**Status:** Done
**Area:** Authentication / session compromise detection
**Concern:** Refresh rotation exists, but reuse detection is not yet implemented. If an already-rotated refresh token is reused, that can indicate token theft.
**Fix:** Phase Q.3.3 added nullable session-family tracking to `auth_sessions`, creates a new family on login, preserves the family and parent link on refresh rotation, detects reuse of already-rotated refresh tokens, revokes the affected family, and records reuse/family-revocation events in `auth_security_events` without logging raw tokens or token hashes.
**Suggested phase:** Phase Q.3.3

---

### H067 — All-sessions logout / logout-all endpoint

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / session management
**Concern:** D036 keeps Q.3.1 focused on single-session logout using existing `/api/v1/auth/logout`, but commercial users may later need “log out everywhere” after suspected compromise or device loss.
**Fix:** Add an all-sessions logout endpoint in a later hardening phase, with portal-aware session revocation, audit logging, and careful admin/employee behaviour.
**Suggested phase:** After Q.3.1

---

### H068 — Same-origin deployment/session routing validation

**Severity:** 🔴
**Status:** Open
**Area:** Deployment / session security / CSRF
**Concern:** D036 chooses same-origin MVP deployment so `SameSite=Strict`, omitted cookie domain, and custom-header CSRF protection remain simple and safe. Q.3.1 must validate that local/staging/prod routing supports this model.
**Fix:** Validate the same-origin routing plan before cookie-backed frontend auth is considered production-safe. API should be path-proxied under the app origin where practical; avoid cross-subdomain cookie/session complexity in MVP.
**Suggested phase:** Phase Q.3.1 / deployment hardening

---

### H069 — Bearer-token deprecation/removal after migration

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / compatibility cleanup
**Concern:** Q.2 preserved bearer-token compatibility for migration. After Q.3.1 moves browser auth to cookie-backed refresh plus in-memory access tokens, legacy bearer-only browser usage should be deprecated and eventually restricted or removed.
**Fix:** Follow the D036 deprecation timeline: log warnings after Q.3.1, stop normal browser issuance/usage after the chosen window, and later remove or restrict bearer compatibility to internal/dev/API clients where needed.
**Suggested phase:** After Q.3.1

---

### H070 — Password reuse/history enforcement

**Severity:** 🟢
**Status:** Open
**Area:** Authentication / password security
**Concern:** Users can reset a password to the same value or a previously used value, weakening the security benefit of password reset.
**Fix:** Add password history storage and enforce N-most-recent-password prevention. Out of scope for Q.4.2 to keep the password reset phase focused.
**Suggested phase:** Future Q.x hardening / post-MVP hardening

---

### H071 — Identifier-specific password reset rate limiting

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / abuse protection
**Concern:** Q.4.2 has route/IP-level password reset limiting through `RATE_LIMIT_PASSWORD_RESET_REQUEST=10/hour`, but does not yet enforce 3 reset requests per email per hour.
**Fix:** Add repo-consistent identifier-level reset throttling without leaking account existence and without adding unsafe infrastructure shortcuts.
**Suggested phase:** Future Q.x hardening

---

### H072 — Backend test suite execution time

**Severity:** 🟡
**Status:** Done
**Area:** Developer velocity / CI reliability
**Concern:** Full backend suite takes several hours locally, making developers less likely to run full verification before commits and slowing CI feedback.
**Fix:** Phase Q.5.1c profiled the Q.5.1/Q.5.1b auth tests and restored the full backend regression gate. Test infrastructure now explicitly opts into fast bcrypt rounds with `BCRYPT_TEST_FAST=true` while production remains default-secure at bcrypt cost 12, and file-backed SQLite test engines are normalized to isolated in-memory engines under pytest. The full backend suite passed with `354 passed, 5 skipped in 303.18s (0:05:03)`.
**Suggested phase:** Completed in Phase Q.5.1c

---

### H073 — Restrict sensitive actions until admin email verified

**Severity:** 🟡
**Status:** Partial
**Area:** Authentication / email verification / sensitive action protection
**Concern:** D038 allows unverified admin users to log in for now, but future sensitive actions should require verified admin email before commercial launch. Without this, an unverified email account may access sensitive Owner/Admin actions.
**Fix:** Add backend enforcement so unverified admin users are blocked from sensitive actions such as billing, payroll, compliance documents, staff profile changes, tenant/site settings, exports, destructive actions, role/permission changes, and other Owner-only governance actions. Per D039/D040, combine this with the sensitive-action gate so email verification, enrolled 2FA where required, and recent step-up state are enforced through one path. Q.5.2a applied the gate to store deactivation. Q.5.2b closed the inspection by keeping current additional endpoints ungated unless they are session-only sensitive actions. Future sensitive actions must use the dependency at build time. Remaining categories include admin-user privilege management, billing/subscription, payroll/pay-rule management, compliance documents, sensitive exports, sensitive audit logs, and erasure flows.
Staff.2 and Staff.2b also closed the current staff pay/RTW read/write exposure by enforcing Owner-only staff pay/RTW read/write behaviour. Future owner-only pay/RTW UI, payroll/pay-rule management, compliance documents, sensitive exports, and sensitive audit-log views must still use the sensitive-action dependency or an equivalent gate when built.

**Suggested phase:** Future product/security phase

---

### H074 — Identifier-specific email verification resend rate limiting

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / abuse protection
**Concern:** Q.4.3 has route/IP-level email verification request limiting, but does not yet enforce 3 verification emails per user per hour.
**Fix:** Add repo-consistent user-level verification resend throttling without adding unsafe infrastructure shortcuts.
**Suggested phase:** Future Q.x hardening

---

### H075 — Production-grade TOTP secret encryption/key rotation/KMS hardening

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / secrets management
**Concern:** Q.5.1 implements AES-256-GCM with environment-injected `TOTP_ENCRYPTION_KEY` as MVP-acceptable encrypted TOTP secret storage, but production maturity should support managed secrets, key rotation, and KMS/Secrets Manager.
**Fix:** Add production-grade TOTP encryption key management, rotation planning, operational runbooks, managed secret/KMS integration, and key-version rotation procedures before higher-scale production rollout.
**Suggested phase:** Post-Q.5.1 production hardening

---

### H076 — Tenant-level 2FA policy for all admins

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / tenant security policy
**Concern:** D039 requires owner 2FA first, but tenant-level policy to require 2FA for all admins is deferred.
**Fix:** Add tenant-level require-2FA-for-all-admins policy controls, rollout behavior, status reporting, and safe exceptions/recovery rules.
**Suggested phase:** Future Q.x hardening

---

### H077 — Employee 2FA enrolment

**Severity:** 🟢
**Status:** Open
**Area:** Employee identity / authentication
**Concern:** Employee identity is site-scoped and separate from admin-side users; employee 2FA needs its own design and operational model.
**Fix:** Design employee 2FA separately from owner/admin 2FA, accounting for site-scoped credentials, manager workflows, device loss, and employee support processes.
**Suggested phase:** Future employee identity hardening

---

### H078 — WebAuthn / passkey support

**Severity:** 🟢
**Status:** Open
**Area:** Authentication / future security
**Concern:** WebAuthn/passkeys are a stronger long-term authentication option, but D039 defers them to v2 due to frontend/browser API, device, and recovery complexity.
**Fix:** Add WebAuthn/passkey support after TOTP is stable, including enrolment, device management, recovery, and cross-browser UX design.
**Suggested phase:** v2 authentication hardening

---

### H079 — 2FA disaster recovery process

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / support operations
**Concern:** Lost authenticator device plus lost recovery codes requires a documented support process with strict identity verification and audit controls before production.
**Fix:** Design and implement a disaster-recovery/support process for 2FA lockouts, including approval rules, audit logging, abuse prevention, and operational runbooks.
**Suggested phase:** Before broad commercial rollout

---

### H080 — Decouple staff profile identity from Admin Portal users

**Severity:** 🟡
**Status:** Open
**Area:** Staff identity / RBAC
**Concern:** Current staff setup may create `users` plus `tenant_users.role = "member"` records because `staff_profiles.user_id` is required. R.2d blocks `member` from obtaining or refreshing Admin Portal sessions, but the schema-level coupling remains and should be removed or made explicitly intentional before broader onboarding.
**Fix:** Redesign staff profile and employee account creation so normal employees do not require Admin Portal identity records, or document and harden the bridge with explicit lifecycle cleanup and provisioning rules.
**Suggested phase:** Phase R.2e / staff identity decoupling

---

### H081 — Reconcile permission matrix and expand role-boundary tests

**Severity:** 🔴
**Status:** Partial
**Area:** RBAC / tenant isolation / pre-onboarding security
**Concern:** T.0 confirmed tenant isolation and employee self-only boundaries, but full role-boundary testing could not be completed because the local repo did not contain a current permission matrix source of truth. A stale PRD matrix cannot be used directly as the test oracle because current implementation diverges from old PRD assumptions in routes, roles, permissions, and field-level exposure.
**Fix:** Phase T.1 created the current permission matrix source of truth. Phase T.2 added matrix-backed role-boundary tests. Phase T.2a fixed the store lifecycle PATCH bypass. Staff.2 hardened staff pay/RTW read exposure, and Staff.2b restricted staff pay/RTW writes to Owner. Remaining H081 work is to keep expanding matrix-backed tests as new modules and target roles are implemented, especially future manager/site-scope behaviour, owner-only sensitive UI, payroll/pay-rules, compliance documents, billing, exports, sensitive audit logs, and erasure flows.
**Suggested phase:** T.1 / T.2

---

### H082 — Store reactivation lifecycle design

**Severity:** 🟡
**Status:** Open
**Area:** Store/site lifecycle / UX / sensitive actions
**Concern:** Phase T.2a intentionally closed the generic `PATCH /api/v1/stores/{store_id}` lifecycle bypass by preventing ordinary PATCH from changing `is_active`. Store deactivation now only goes through the protected sensitive-action endpoint, but there is currently no dedicated reactivation endpoint or UI. This means deactivation is effectively one-way in the MVP unless restored manually through support/database intervention.
**Fix:** Decide and implement a dedicated store reactivation lifecycle flow if the product needs owners to self-restore inactive stores. Reactivation should be owner-only, audit logged, and may require step-up/2FA depending on sensitivity. Until then, document deactivation as a controlled one-way MVP action or define a manual support recovery process.
**Suggested phase:** Future lifecycle/UX hardening

---

### H083 — Owner-only staff pay/RTW UI with step-up and audit

**Severity:** 🟡
**Status:** Open
**Area:** Staff / payroll visibility / right-to-work / sensitive UI
**Concern:** Staff.2 and Staff.2b now enforce Owner-only staff pay/RTW read/write access in backend APIs, and Staff.1 added the normal safe staff profile edit UI without pay/RTW fields. There is still no dedicated Owner-only UI for viewing or editing `hourly_rate`, `pay_type`, or `rtw_status` after staff creation. Building this inside the normal staff edit form would risk exposing sensitive fields to Admin/non-owner roles and would mix sensitive actions with safe staff profile editing.
**Fix:** Add a dedicated Owner-only staff pay/RTW section or page. The UI must not be visible to Admin/non-owner roles. Backend must remain authoritative. Sensitive view/edit actions should require 2FA/step-up where applicable and should be audit logged where implemented. Do not add NI numbers, passport/BRP/share-code documents, compliance document uploads, weekly hour cap, base hours threshold, overtime rate, or payroll rules in this phase; those require separate secure storage/payroll design.
**Suggested phase:** Future owner-only staff pay/RTW UI

---

### H084 — Staff deactivate/reactivate lifecycle design

**Severity:** 🟡
**Status:** Open
**Area:** Staff lifecycle / UX / sensitive actions
**Concern:** Staff.1 intentionally excludes `is_active`, deactivate, reactivate, archive, and delete from the normal safe staff profile edit UI. Staff activation/deactivation is a lifecycle action and should not be mixed into routine safe profile editing.
**Fix:** Design and implement a dedicated staff lifecycle flow if the product needs admin/owner self-service activation changes. The flow should define owner/admin permissions, employee-login impact, rota/request impact, audit logging, whether step-up is required, and any reactivation rules.
**Suggested phase:** Staff.1L

---

### H085 — Rota assignment identity contract cleanup before EP.0

**Severity:** 🟡
**Status:** Open
**Area:** Rota / employee identity / API contract
**Concern:** Rota.1 preserved the current weekly rota frontend contract, where `WeeklyRotaShift.assigned_employee_account_id` is used by the UI as a staff `user_id` for safe staff-directory lookup. Rota.0 confirmed the backend site weekly rota maps this response field from `Shift.assigned_user_id`, not from a true `employee_accounts.id`. The name is misleading and can cause employee-portal or future rota work to mix admin-user identity with employee-account identity.
**Fix:** Before EP.0 or any employee-portal-facing rota contract expansion, decide whether the site weekly rota should expose `assigned_user_id`, `assigned_employee_account_id`, both with clear semantics, or a safer staff/employee summary object. Update backend schemas, frontend types, tests, and docs together. Do not paper over this in frontend-only code.
**Suggested phase:** Before EP.0 / rota identity contract cleanup

---

### H086 — Surface recommendation reasons in admin recommendation UX

**Severity:** 🟡
**Status:** Open
**Area:** Rota recommendations / UX
**Concern:** The recommendation engine can now keep StaffProfile-over-soft-cap candidates eligible while flagging them with `over_weekly_soft_cap`. Admins need visible recommendation reasons to understand why candidates are ranked, flagged, or skipped.
**Fix:** Add recommendation UX that surfaces candidate/item reasons such as `over_weekly_soft_cap` without changing recommendation engine semantics.
**Suggested phase:** Recommendation UX polish

---

### H087 — Define employee/admin availability precedence and merge rules

**Severity:** 🟡
**Status:** Open
**Area:** Availability / rota recommendations
**Concern:** Admin replace-week is authoritative for the selected staff member/week and can overwrite employee-set rows. The product still needs future rules for employee/admin precedence, merge behaviour, and audit/UX messaging beyond the MVP replace-week model.
**Fix:** Decide and implement explicit precedence and merge rules for employee-set and admin-set availability if the product needs concurrent self-service and admin planning workflows.
**Suggested phase:** Future availability workflow hardening

---

### H088 — Harden availability date/timezone boundary conventions

**Severity:** 🟡
**Status:** 🟡 Partially addressed 2026-08-11 (H088a complete; H088b folded into Availability.1)
**Area:** Availability / scheduling correctness
**Concern:** Availability dates and times are treated as site-local wall-clock inputs. Future multi-timezone or cross-site workflows could expose boundary issues if the convention is not consistently documented, validated, and tested.
**Fix:** Add focused boundary tests and documentation for site-local availability dates/times before introducing timed windows, recurring availability, or multi-timezone scheduling workflows.
**Progress (H088a, commit `eb6840c`):** The date and convention half is complete. D054 records the site-local wall-clock convention, its two assumptions, and the exit condition that triggers real timezone support. The convention is stated in `docs/AI_WORKFLOW.md`, `README.md`, and the `apps/api/routers/availability.py` module docstring. Fourteen boundary cases in `apps/api/tests/test_h088a_availability_date_boundaries.py` lock the Monday `week_start` rule, the half-open date window, the employee past-date guard, and submitted row shape, at both unit and HTTP level, across the employee create path and admin replace-week. No production behaviour changed.
**Finding during H088a:** Half-open rows — exactly one of `start_time` or `end_time` set — fall outside BOTH partial unique indexes on `availability_entries` and have no check constraint. `_validate_availability_payload` is the only guard against them. Now tested, but a single point of failure if a third availability writer is ever added. A check constraint or third partial index is the defence-in-depth option.
**Remaining (H088b):** Timed-window boundary tests — containment versus partial overlap, overnight shifts crossing midnight, contradictory rows on one date, and multiple windows per date. Deliberately folded into Availability.1 rather than done ahead of it: those are undecided product rules Availability.1 must settle, not existing behaviour to characterise.
**Suggested phase:** H088b within Availability.1

---

### H089 — Make pytest rate-limit bootstrap deterministic

**Severity:** 🔴
**Status:** Resolved (2026-07-24)
**Area:** Test infrastructure / rate limiting
**Concern:** `rate_limit.py` binds the active limiter at import time. The test `conftest.py` already set `RATE_LIMIT_ENABLED=false` before every project/application import, but the Compose `api` service injected `RATE_LIMIT_ENABLED=true`; `setdefault` correctly preserved that explicit value. Full-suite runs therefore accumulated auth requests under SlowAPI's `20/minute` default and produced cascading `429` responses. Per-file test runs could mask the failure because they did not accumulate enough requests to trip the limit.
**Fix:** Removed the service-level `RATE_LIMIT_ENABLED` injection from the normal Compose `api` service. Pytest now owns its default through the existing early `setdefault`, while ordinary application processes retain the `Settings` production default of `true` and explicit `-e RATE_LIMIT_ENABLED=true` still enables rate-limit tests. The canonical verification command and CI must run the full `apps/api/tests/` directory because per-file runs can mask cross-test counter accumulation. CI's explicit `false` override is harmless but redundant.
**Suggested phase:** Test infrastructure hardening

---

### H090 — Employee-portal test failures after rate-limit noise clears

**Severity:** 🟡
**Status:** ✅ Resolved 2026-08-10
**Area:** Employee portal / tests
**Concern:** Once rate-limit noise was avoided by setting `RATE_LIMIT_ENABLED=false` before the test process, the full backend suite surfaced two employee-portal failures in `apps/api/tests/test_phase17_employee_portal.py`: `test_employee_availability_crud_self_only` returned `422` instead of `201`, and `test_employee_swaps_create_and_list_follow_existing_rules` returned `400` instead of `201`.
**Root cause:** Test-data expiry. Not a production defect, and unrelated to the H085 rota assignment identity seam — the original suspicion was wrong and cost an investigation branch. Both tests used absolute calendar dates that were future when written and have since passed. `test_employee_availability_crud_self_only` posted availability for `2026-06-01` and was rejected by `apps/api/routers/employee.py::_ensure_availability_is_future` (`422 VALIDATION_ERROR`). `test_employee_swaps_create_and_list_follow_existing_rules` created a shift at `2026-06-20` and was rejected by `apps/api/routers/shift_requests.py::_enforce_shift_change_min_hours` (`400 SHIFT_REQUEST_TOO_CLOSE_TO_START`). Employee login and `/auth/employee/me` both returned `200` in the failing runs, confirming identity resolution was never involved.
**Fix:** Dates in both tests now derive from a single per-test anchor computed from `date.today()` via a `_future_monday()` helper. Swap lead time is computed from `settings.SHIFT_CHANGE_MIN_HOURS` rather than assumed. Production validation is unchanged; the guards were correct and the fixtures were stale. Backend suite moved from `453 passed, 2 failed, 6 skipped` to `455 passed, 0 failed, 6 skipped`.
**Follow-up:** Other tests in `test_phase17_employee_portal.py` still use absolute past dates. They pass only because those code paths have no past-date guard. Any future guard added to a shift or request path will fail them simultaneously. A repository-wide sweep for hardcoded `20\d\d-` dates in `apps/api/tests/` would size this.

---

### H091 — Add atomic recommendation regenerate endpoint

**Severity:** 🟡
**Status:** Open
**Area:** Rota recommendations / workflow reliability
**Concern:** RecommendationUI.3 regenerates by calling discard, then create, then load. This uses existing public HTTP contracts, but it is non-atomic. If discard succeeds and create/load fails, the manager is left with no active recommendation draft. The frontend shows a safe error, but the workflow is less robust than a single backend operation.
**Fix:** Add a dedicated atomic regenerate endpoint or expose a carefully designed create/replace contract that preserves tenant isolation, admin RBAC, audit logging, and clear failure semantics. Cover the partial-failure case with backend tests.
**Suggested phase:** Future recommendation workflow hardening

---

### H092 — Add immutable demand-generation input snapshots

**Severity:** 🟡
**Status:** Open
**Area:** Coverage generation / provenance
**Concern:** Coverage.1a records shift-to-run and shift-to-template lineage, while template IDs continue to resolve to mutable template rows. Historical timing, role, and work area remain on the shift, but a generation run does not retain an immutable copy of all template inputs used for that run.
**Fix:** Add an immutable per-run input snapshot if audit or replay requirements need full historical reproducibility. Preserve the existing shift lineage and do not infer past inputs from a subsequently edited template row.
**Suggested phase:** Future provenance hardening

---

### H093 — Decide generic shift-list history defaults

**Severity:** 🟡
**Status:** Open
**Area:** Shifts / history API contract
**Concern:** Generic `GET /shifts` applies a status filter only when the caller supplies one. Its default response can therefore include scheduled, cancelled, completed, and soft-superseded historical shifts. The admin weekly rota grid does not use this endpoint and already filters to scheduled shifts, so this is not a Coverage.1a blocker.
**Fix:** Decide whether generic shift listing should default to scheduled shifts only, require an explicit `include_cancelled` or history option, or retain and clearly document the current all-status default. Update the contract and consumers together in a dedicated phase.
**Suggested phase:** Future shift-history API hardening

---

### H094 — Multi-store staff assignment and cross-store hour aggregation

**Severity:** 🔴
**Status:** Open
**Area:** Staff identity / hours / pay
**Depends on / relates to:** H085 (identity seam), Coverage.1b (overnight shifts)
**Concern:** Two model and calculation gaps prevent correct multi-store employment and pay-facing totals:

1. `staff_profiles.store_id` is one nullable value. A person is either homed to one store or has `NULL`, meaning eligible everywhere; there is no way to express “works at Store A and Store B, but not Store C.” Recommendation candidates currently rely on `or_(StaffProfile.store_id == store_id, StaffProfile.store_id.is_(None))`.
2. `_build_assigned_hours_map` filters `Shift.store_id == store_id`, so it calculates assigned hours within one store and nothing computes person-level totals across all stores.

**Worked example:** A person works 50 hours at Store A, 40 hours at Store B, and 30 hours at Store C in one calendar month: 120 hours against a 100-hour threshold. Correct chronological aggregation produces 100 standard hours and 20 overtime hours. If the person has accumulated 96 hours before an eight-hour threshold-crossing shift, the crossing store bears four standard and four overtime hours from that shift; later qualifying hours are overtime. The current broken per-store calculation sees three sub-threshold totals and never detects overtime.

**Locked semantics inherited from D053:**

1. Count only published scheduled shifts: `status == 'scheduled' AND published_at IS NOT NULL`. Draft/unpublished, cancelled, and superseded shifts do not qualify.
2. Use scheduled hours, not actual attendance. Clocked-hour calculations are future work.
3. Use the calendar month in the tenant payroll timezone, Europe/London for the UK-first MVP. Thresholds and pay share that one window.
4. Aggregate chronologically by shift start time, tie-broken by shift ID. The crossing store bears any threshold split, including a split within one shift.
5. Detect overlapping shifts and surface them for human resolution; never silently sum them.
6. Keep `monthly_threshold_hours` as tenant-level policy and standard `hourly_rate` plus `overtime_rate` as employee-level terms. Hours remain operational/scheduler-visible; money remains owner-only.
7. Migrate an existing non-null `staff_profiles.store_id` to exactly one assignment for that store. Put an existing `NULL` into a reviewed legacy-global state requiring explicit human resolution. Never translate `NULL` into assignments to all current stores, because doing so would silently grant access to stores created later.
8. Keep employment identity separate from portal credentials. One tenant-level login with selectable stores versus store-specific accounts linked to one staff profile remains an H085 decision.

**Suggested model:** Add `staff_store_assignments` with `tenant_id`, `staff_profile_id`, `store_id`, `is_primary`, `is_active`, `created_at`, and `ended_at`. Implementation must first lock whether every active employee requires at least one active assignment; enforce at most one primary assignment per profile; decide whether primary affects anything beyond the default UI selection; preserve historical shifts when an assignment is deactivated; and restrict recommendations to staff actively assigned to the requested store.

**Open questions:**

* **Effective dating / frozen history:** Changing a rate on 20 July would silently recalculate all July shifts if calculations read current mutable profile values. Closed periods must not be recalculated from current values. Effective-dated terms, frozen monthly snapshots, or both are required before any pay-facing feature. A full payroll-ledger design is outside H094.
* **Cross-month shift splitting:** A shift from 31 July 22:00 to 1 August 06:00 should split into two July hours and six August hours. Coverage templates currently reject `end_time <= start_time`, so overnight shifts are impossible. This is a Coverage.1b dependency, not H094 scope.
* **Cost attribution labelling:** Chronological attribution can cause a late-month store to bear most overtime despite scheduling fewer hours. Reports must use “attributed payroll cost,” not “cost caused by this store,” and show it alongside “hours scheduled at this store.” A management-allocation view is a separate concern.

**Fix:** Implement explicit multi-store assignments and person-level cross-store hour aggregation under the D053 semantics. This must land before any earnings, payroll, or pay-facing feature, or those features will be built on incorrect per-store totals.
**Gate:** Cover assignment eligibility, tenant isolation, reviewed `NULL` migration, chronological/tie-break ordering, within-shift threshold splitting, overlap detection, published-only qualification, cross-store aggregation, store attribution, and owner-only money visibility.
**Suggested phase:** Before any earnings, payroll, or pay-facing feature

---

### H095 — Tenant-defined minimum average hourly benchmark warning

**Severity:** 🟡
**Status:** Open
**Area:** Pay / warnings
**Depends on:** H094
**Concern:** A tenant may configure rates that produce an average hourly figure below a floor the tenant cares about. The product could surface a non-blocking “tenant-defined minimum average hourly benchmark” warning.
**Constraint:** The product is a calculator. The tenant supplies the benchmark figure; the product must not hardcode statutory rates or present the warning as legislative compliance or pay/legal advice.
**Open questions:** Decide whether the comparison uses gross pay before or after adjustments; which paid amounts are included; scheduled or paid hours; how bonuses are handled; how a shift crossing the threshold is treated; and whether comparison is scoped per month, employee, or store.
**Fix:** After H094, design an owner-controlled benchmark setting and non-blocking warning with explicit calculator-only language and tests for the agreed calculation scope.
**Suggested phase:** Future pay warnings, after H094

---

### H096 — Dedicated work-area reactivation lifecycle

**Severity:** 🟢
**Status:** Open
**Area:** Work areas / lifecycle
**Concern:** Work-area deactivation is currently one-way through the public API. Generic work-area PATCH intentionally accepts `label` only; adding `is_active` there would bypass a dedicated, validated lifecycle boundary. Creating a new active work area is the current acceptable workaround, so reactivation is low priority.
**Fix:** If restoration becomes necessary, add a dedicated action such as `POST /api/v1/sites/{site_id}/work-areas/{work_area_id}/reactivate`. It must preserve tenant and site scoping, audit-log the lifecycle change, and check for an active case-insensitive label collision before reactivation. Active-label uniqueness is scoped by tenant, store, and lower-cased label for active rows. For example, deactivate `Bakery`, create a new active `Bakery`, then attempt to reactivate the old record: the action must return a clean domain `409` rather than leak an `IntegrityError`.
**Gate:** Add backend lifecycle, collision, audit, and tenant/site-isolation tests, including the deactivate → recreate same label → reactivate collision.
**Suggested phase:** Future low-priority work-area lifecycle hardening

---

### H097 — Weekly rota mobile layout and overflow

**Severity:** 🟡
**Status:** Open
**Area:** Rota UI / responsive layout
**Concern:** Browser testing confirmed the Coverage rules tab works at approximately 390px width, but the existing Weekly rota surface is not mobile-suitable. The rota grid and/or controls overflow horizontally, and the selected-site control can exceed the mobile viewport because of existing sizing and layout assumptions. This is separate from CoverageUI.1.
**Fix:** Design an intentional responsive Weekly rota representation without weakening desktop usability. Options to evaluate include stacked days, controlled horizontal scrolling, or another approved compact rota view. Do not treat CoverageUI.1's responsive coverage grid as a fix for the existing rota surface.
**Suggested phase:** Future Weekly rota responsive UX

---

### H098 — Absolute calendar dates in backend test fixtures

**Severity:** 🟡
**Status:** Open
**Area:** Tests / maintainability
**Concern:** Roughly 320 absolute date literals span 21 backend test source files. Tests pass only while the code paths they exercise have no guard comparing against `now()`. H090 demonstrated the failure mode: two literals sat inert for months, then failed simultaneously once real time crossed them, and the cause was initially misattributed to the H085 identity seam. Any future notice-period, lead-time, or past-date guard will detonate an unknown subset at once, in files unrelated to the phase that added the guard. The wider risk is not a product defect but alarm fatigue: normalised known-failing tests stop being read, and a real regression can hide behind them.
**Exposure (verified 2026-08-10):** Eight source files combine absolute dates with calls to time-guarded endpoints (`shift_requests`, `me/availability`, `/api/v1/shifts`): `test_rota_recommendations.py`, `test_rota_recommendations_e2e_availability.py`, `test_phase_coverage_1a.py`, `test_phase_i1_rota_week_read.py`, `test_phase17_employee_portal.py`, `test_shifts.py`, `test_phase16_role_constraints_and_overrides.py`, `test_phase15_coverage_and_generation.py`. Most use `/api/v1/shifts` only for setup, and shift creation currently has no past-date guard, so they are inert today.
**Fix:** Do not sweep all files at once; churn and regression risk outweigh the benefit, and a sweep would collide with Availability.1 in the same files. Instead: (1) record in `docs/AI_WORKFLOW.md` that test dates must derive from `date.today()` and absolute calendar dates are not permitted in new or modified tests; (2) promote `_future_monday()` from `test_phase17_employee_portal.py` into a shared test helper; (3) convert literals opportunistically in files a phase already touches. `test_rota_recommendations_e2e_availability.py` is the natural first candidate, since Availability.1 will touch the availability-to-recommendation chain regardless.
**Suggested phase:** Opportunistic, alongside phases touching the affected files

---

### H099 — Manual shift assignment bypasses override machinery

**Severity:** 🟠
**Status:** Open
**Area:** Shift assignment / audit integrity
**Concern:** The live admin UI assigns staff via create-shift and update-shift, which
bypass `_apply_assignment` and the override-aware `PATCH /shifts/{id}/assign` endpoint
entirely. An assignment made outside an employee's declared availability can therefore
persist with `availability_override = False`, no `override_reason`, and no override
audit provenance. The audit field affirmatively records a false negative rather than
merely omitting the record.
**Fix:** Converge all manual assignment paths on shared override-aware logic. Decide
whether a reason becomes mandatory. Add frontend acknowledgement. Tracked as
Availability.Override.1, per D056 rule 3.
**Suggested phase:** Availability.Override.1

---

### H100 — Availability editability after publication is asymmetric

**Severity:** 🟡
**Status:** Open
**Area:** Availability / rota lifecycle
**Concern:** `_ensure_availability_week_is_editable` blocks an employee's availability
writes only when that employee has at least one published, scheduled shift assigned in
that store and week. An employee with no published shift may still edit availability
for a week whose rota is live. Admin replace-week applies no equivalent check and may
overwrite availability for any week regardless of publication. This is not a
week-level publication lock, and no submission window, deadline, or lead-time concept
exists anywhere in the codebase.
**Fix:** Undecided. The underlying question — what effect changing availability after
publication should have — is a product decision. Changing availability should probably
not mutate a published assignment, but may warrant a conflict warning. Related
proposed design in `docs/design/availability_product_area.md`, not adjudicated.
**Suggested phase:** Availability.2 or later

---

### H101 — 24-hour site operation is unrepresentable at three layers

**Severity:** 🔴
**Status:** Open
**Area:** Site model / coverage generation / availability / scheduling correctness
**Relates to:** Coverage.1b, D057 rule 6, H094 (cross-month shift splitting)

**AMENDED 2026-08-18 — governed by D061.** The original entry is preserved intact
below. Where the two differ, D061 and the corrections here are authoritative.

- **Now split across three phases**, not one. **Coverage.1bA** — overnight
  intervals become creatable and schedulable (coverage templates, generation
  anchoring, admin overnight shift creation, overnight display).
  **Coverage.1bB** — overnight declared availability becomes matchable
  (`_entry_interval`, both availability loaders, cross-date and cross-week
  contradiction detection, replacement of D057 rule 6). **SiteHours.24h** —
  truthful continuous-opening representation. D057 rule 6 remains controlling
  until Coverage.1bB completes.
- **The premise that three layers share one constraint is wrong.** Inspection on
  2026-08-18 found **nine enforcement points across five distinct mechanisms**
  (model CheckConstraint, migration CHECK, Pydantic validator, route-handler
  checks, frontend validation), with **no shared helper crossing a layer**. The
  only genuine shared helper, `_validate_availability_payload`, is internal to
  the availability layer. Coverage templates carry two independent duplicates
  that are unaware of each other.
- **Opening hours have no scheduling consumer.** Nothing in `rota.py`,
  `shifts.py`, `rota_recommendations.py`, or `apps/api/services/` reads
  `open_time` or `close_time`. The only consumers are two duplicated readiness
  `COUNT(*)` predicates and a display round-trip. Relaxing that layer alone
  changes no scheduling behaviour — which is why SiteHours.24h is separable.
- **"Overnight shifts remain creatable manually" is true of the API and false of
  the product.** The admin UI blocks it twice: `validateCreateShiftDraft` rejects
  `endTime <= startTime`, and `buildShiftDateTime` derives both endpoints from a
  single day index, so it structurally cannot emit a cross-date shift. Manual
  overnight creation today requires direct API access.

**Concern:** The first customer operates a mix of 24-hour and non-24-hour sites under one
tenant. 24-hour operation cannot currently be expressed anywhere in the system, and the
same constraint blocks it at three independent layers:

1. **Store opening hours.** `store_opening_hours` carries a database CHECK constraint,
   `is_closed OR (open_time IS NOT NULL AND close_time IS NOT NULL AND close_time >
   open_time)`, and `OpeningHoursDay` enforces `close_time > open_time` at the API
   boundary. A continuously open site cannot be declared. The nearest expressible value,
   00:00–23:59, is a different declaration and is indistinguishable from a site that
   closes for one minute.
2. **Coverage templates.** Template validation rejects `end_time <= start_time`, so an
   overnight staffing demand pattern cannot be defined and overnight shifts can never be
   generated.
3. **Availability.** `_validate_availability_payload` rejects `end_time <= start_time`, so
   a 22:00–06:00 availability window cannot be declared. Retained deliberately by D055
   rule 6.

There is no 24-hour indicator on `stores` and no operating-pattern field anywhere. A
repository-wide search for `is_24`, `24_hour`, `24h`, `twenty_four`, `open_24`,
`always_open`, and `overnight` returns only documentation describing the absence of
support and one frontend error string.

**Consequence already realised:** D057 rule 6 had to be adjudicated as an unconditional
fail-closed for cross-midnight automatic matching, because the intended site-dependent
rule — preserve current behaviour for 24-hour sites, fail closed for the rest — depended
on a discriminator that does not exist. Overnight shifts remain creatable manually, since
shift validation compares full datetimes and only requires `end_at > start_at`, but they
receive no automatic recommendation.

**Priority note:** Coverage.1b is recorded elsewhere as unscheduled and in no fixed order.
That understates it. This is a live gap for the current customer, not a future
enhancement, and it is the common blocker behind all three layers above.

**Fix:** Decide how 24-hour and overnight operation is represented, then implement it
consistently across opening hours, coverage templates, and availability together. Piecemeal
relaxation of one `close_time > open_time` constraint without the others will produce a
site that can declare a pattern it cannot staff, or staff a pattern it cannot declare.
Continuous cross-calendar-day availability matching is the dependent piece and must be
designed with it, per D055 rule 6's recorded semantic direction: an overnight shift is
eligible only when availability continuously covers the complete shift interval across the
relevant calendar dates.
**Gate:** Cover opening-hours representation, overnight coverage templates, overnight shift
generation, cross-midnight availability declaration and matching, and the D057 rule 6
transition from fail-closed back to real matching.
**Suggested phase:** Coverage.1b, elevated from unscheduled

---

### H102 — Employee credential management has no admin surface

**Severity:** 🔴
**Status:** Open
**Area:** Employee identity / operations
**Concern:** There is no admin-side surface to reset a forgotten employee
password, change an employee username, or deactivate portal access. D038
Decision 1 deferred employee account recovery from Q.4 on the grounds that
employees authenticate through site-scoped credentials and recovery "must be
designed later with site/manager operational workflows in mind." That design was
never scheduled and no backlog item was raised. H058/H059 cover admin-side users
only; H077 and H079 cover employee 2FA, not credential lifecycle. Employee
accounts are currently created at staff-creation time via `employee_username` /
`employee_password`. A forgotten password today requires direct database access,
which makes the employee portal unoperable by a customer.
**Fix:** Decision entry satisfying D038's named requirement, then
EmployeeCredentials.1. Candidate capabilities: set temporary password (shown
once, stored hashed), revoke active employee sessions on reset mirroring the
Q.4.2 admin pattern, change username with deterministic 409 on collision,
deactivate/reactivate portal access.
**Authority is not settled by this entry.** Which admin-side role(s) may perform
each credential action must be decided in the required decision before
implementation. Do not infer Owner/Admin/Manager authority from existing generic
admin dependencies; `manager` is not in the implemented tenant-role set
(`owner | admin | member`).
**Open inspection question:** whether an employee account can be created for an
existing staff profile that lacks one. D016 mandates a 1:1 staff ↔ employee
account mapping with no orphan accounts, while account creation historically
occurs at staff-creation time when credentials are supplied. Live inspection must
establish whether staff profiles without employee accounts exist and whether a
create path is warranted, before it is scoped as a feature.
**Suggested phase:** EmployeeCredentials.1

---

### H103 — Employee availability capture carries material adoption risk

**Severity:** 🔴
**Status:** Open
**Area:** Employee portal / availability / adoption
**Concern:** `/employee/availability` accepts one row per submission. The current
flow requires repeated per-day entry of date, type, start and end values plus a
separate submission for each declaration, so completing a normal week requires
substantial repeated mobile input. Availability is Source 2 for rota
recommendations under D048, so low completion leaves the recommendation engine
without its primary declared input. Assessed as a material adoption risk on
inspection; no usability study has been run.
**Fix:** Availability.UX.1, frontend only and additive. Multi-day selection
within the visible week, one type and one time range applied across selected
days, times prefilled from the employee's last entry, one submit issuing the
existing per-row `POST /api/v1/employee/me/availability` once per selected day.
No new endpoint, no delete, no replace — every row remains an ordinary
employee-authored write and D048 is untouched.
**Explicitly out of scope:** an employee bulk-week write endpoint. Employee
replace-week would create an authority question against admin replace-week that
D048 does not answer, and inferring an answer from implementation would settle
precedence by accident. Recurring or standing availability is Availability.2 and
unadjudicated; "copy last week" is acceptable only as a client convenience
producing ordinary rows.
**Open ruling required before implementation:** partial-failure behaviour when
some days succeed and others return `409 AVAILABILITY_LOCKED_BY_PUBLISHED_ROTA`.
Recommended: retain successful rows, report failures by date, no rollback —
rollback would require deletes and introduce destructive semantics into a path
that currently has none.
**Suggested phase:** Availability.UX.1

---

### H104 — `source_conflict` presentation contradicts itself on the admin rota recommendation surface

**Severity:** 🟡
**Status:** Open
**Area:** Rota recommendations / feasibility presentation
**Concern:** `recommendationReasonLabels` in `admin-shell.tsx` predates
Availability.1a and omits `source_conflict`. It falls through
`humanizeRecommendationReason` to "Source conflict" in the generic blue chip —
identical styling to ranking notes such as "Below target hours" — while
`no_eligible_candidate` receives a distinct grey chip. Separately, a fixed
paragraph reading "No eligible candidate. Check staff availability, role
requirements, and hard hour limits" renders on every unfilled item, directly
contradicting a Source conflict chip above it. D056 rule 2 exists specifically to
keep those two causes distinct, so an operator is not told the employee is
unavailable when the true cause is conflicting declarations. This is a
correctness defect in operator-facing output, not a styling issue.
**Fix:** Add a distinct `source_conflict` label and chip treatment, and make the
explanatory paragraph conditional on the actual reason rather than fixed.
**Suggested phase:** Feasibility.1

---

### H105 — Admin replace-week destroys employee `preferred_off` rows

**Severity:** 🟡
**Status:** Open
**Area:** Availability / precedence
**Concern:** Admin replace-week is authoritative for the selected staff member
and week under D048 and replaces the week with full-day `available` rows,
deleting employee-authored `preferred_off` declarations. Additionally, a
`preferred_off`-only day displays the admin grid's "Set by employee" marker while
the binary toggle reads "Unavailable", because `availableDatesFromRows` filters
to `available | available_extra`. Both behaviours already applied to employee
`unavailable` rows; Availability.1b makes them more reachable but did not create
them.
**Fix:** Resolve under the deferred cross-source precedence phase. The future
precedence phase must not infer precedence from row order, timestamps,
declaration type, or writer role, per D056 rule 2.
**Suggested phase:** Precedence phase

---

### H106 — Composed availability declarations render as unrelated lines

**Severity:** 🟢
**Status:** Open
**Area:** Employee portal / availability presentation
**Concern:** D055 rule 4 permits an `available` row and a `preferred_off` row to
coexist coherently for the same date and window. The employee availability list
renders each row as a separate flat grey line with no grouping or compositional
signal, so an employee cannot tell whether their declarations combine coherently
or contradict each other. Observed in the browser on 2026-08-17, using
declarations dated 2026-08-19.
**Fix:** Group the read-back list by date and present a day's declarations
together rather than as independent rows.
**Suggested phase:** Availability.UX.1 or later

---

### H107 — Employee portal header exposes a raw site UUID

**Severity:** 🟢
**Status:** Open
**Area:** Employee portal / presentation
**Concern:** `/employee/availability` renders the site identifier as a raw UUID
in the header subtitle. It carries no meaning for an employee and looks
unfinished in any demonstration.
**Fix:** Display the site name, using the site data already available to the
employee portal.
**Suggested phase:** Availability.UX.1

---

### H108 — Employee `AVAILABILITY_DUPLICATE` constraint key

**Severity:** 🟢
**Status:** Done
**Area:** Availability / write-path validation
**Concern:** Raised during Availability.1b inspection: it was unverified whether
`409 AVAILABILITY_DUPLICATE` on the employee path keys on declaration type. If it
did not, the `available` + `preferred_off` composition permitted by D055 rule 4
would be unreachable in practice on that path.
**Fix:** Verified empirically in the browser on 2026-08-17. Two rows dated
2026-08-19, identical 09:00–17:00 window, types `available` and `preferred_off`,
both persisted and both rendered. The composition is reachable, consistent with
D023's Phase L employee duplicate rule of `tenant_id + site_id +
employee_account_id + date + start_time + end_time + type`. No change required.
**Suggested phase:** n/a — closed by observation

---

### H109 — Employee current-day views omit active overnight shifts

**Severity:** 🟡
**Status:** Open
**Area:** Employee portal / overnight boundary
**Concern:** All three shift collections in `EmployeeHomeRead` are
`start_at`-scoped. An employee working Sunday 22:00 → Monday 06:00 who opens the
portal at Monday 02:00 is absent from `today_operators`, from `my_rota`, and
from `weekly_rota` for the new week, because `_default_week_start` has already
advanced. They can find the shift only by navigating back a week. A colleague
checking who is on site sees nobody while someone is physically working.
This behaviour predates Coverage.1bA-1 and is consistent with D061 rule 2's
start-date ownership. What 1bA-1 changes is reachability: overnight shifts
become routine rather than API-only, so a latent boundary becomes operationally
live.
**Fix:** Adjudicate whether "today" on the employee surface means "starts today"
or "intersects the current instant." D061 rule 6 is scoped to the admin grid and
does not settle this. Requires a decision before implementation.
**Suggested phase:** Employee overnight visibility phase, post-Coverage.1bA-2

---

### H110 — `coverage_templates` model does not fully describe its schema

**Severity:** 🟢
**Status:** Open
**Area:** Schema parity / test fidelity
**Concern:** Migration `0014` created three CHECK constraints on
`coverage_templates`. Coverage.1bA-1 declared the time-window constraint on the
model deliberately, because it was the invariant that phase changed.
`ck_coverage_templates_day_of_week_range` and
`ck_coverage_templates_required_headcount_min` remain undeclared. Because the
test suite builds schema via `Base.metadata.create_all` and never runs Alembic,
those two predicates are absent from every test database and are exercised only
by router-level Python checks. A change to either would produce no test signal.
The same asymmetry may exist on other tables.
**Fix:** Audit all models against their migrations for undeclared constraints and
declare them. Expect this to surface existing test fixtures that create rows the
production database would reject. Separately, revisit `Base.metadata.create_all`
in `conftest.py`, which diverges from `CLAUDE.md`'s "Alembic migrations only. No
create_all."
**Suggested phase:** Schema parity phase

---

### H111 — Test invocation requires an undocumented `PYTHONPATH`

**Severity:** 🟢
**Status:** Done
**Area:** Developer workflow / documentation
**Concern:** `docker compose exec api pytest -q` fails collection with
`ModuleNotFoundError: No module named 'apps'` across all 58 test files.
`PYTHONPATH` is empty in the container and the working directory is `/app`. The
correct invocation requires `-e PYTHONPATH=/app`. This was documented nowhere,
and cost a full round trip during Coverage.1bA-1 when an implementation prompt
specified the wrong command.
**Fix:** Documented in `CLAUDE.md`. No code change.
**Suggested phase:** n/a — closed by documentation

---

### H112 — Published shifts open in the editor and fail with a generic message

**Severity:** 🟡
**Status:** Open
**Area:** Admin rota editor
**Concern:** The weekly grid puts no published-state guard on the shift edit
click. A published shift opens in the editor, and the failure surfaces only at
the API as a 409, which the catch block renders as "Could not update shift.
Please check the details and try again." The details are fine; the shift is
locked. The backend behaviour is correct and tested at
`test_phase_i4_shift_update_cancel.py`; the frontend is unguarded and the message
misleading. Predates Coverage.1bA-2 and was deliberately left out of scope.
**Fix:** Guard the edit click on publication state, or render the 409 distinctly.
**Suggested phase:** Rota editor hardening

---

### H113 — `notes` is collected in the shift draft and discarded on submit

**Severity:** 🟢
**Status:** Open
**Area:** Admin rota editor
**Concern:** `CreateShiftDraft` carries a `notes` field bound to a textarea in
the shift modal, but it does not appear in the submit payload. Anything typed is
silently lost. Predates Coverage.1bA-2.
**Fix:** Either send it, or remove the control. Sending it requires confirming
the API accepts a notes field on the site-scoped shift routes.
**Suggested phase:** Rota editor hardening

---

### H114 — A failed weekly rota load renders as both an error and an empty week

**Severity:** 🟢
**Status:** Open
**Area:** Admin rota display
**Concern:** When the weekly rota request fails, the grid shows a red error
banner and the footer simultaneously reads "No shifts created for this week."
Those are different states and the user sees both at once. Coverage.1bA-2
deliberately did not extend this pattern to carry-in, which distinguishes a
failed load from an empty one, but the original surface is unchanged.
**Fix:** Suppress the empty-state text while an error is displayed.
**Suggested phase:** Rota editor hardening

---

### H115 — D060 rules 13, 15 and 16 were never adjudicated

**Severity:** 🟡
**Status:** Open
**Area:** Decision records
**Concern:** D060 was committed at `c7fb7e9` as `Status: Proposed`. The committed
text is not the reviewed draft: it carries sixteen rules where the reviewed
version carried ten. All seven adjudicated corrections are present and correct
(seed times, mandatory setup over silent backfill, resolved-window
de-duplication, no Unavailable control, whole-phase gate after Coverage.1bB,
carry-forward with `source = admin`, "near tie" repudiated). But rules 13 (save
construction procedure), 15 (what D060 does not settle) and 16 (implementation
gate) originate from neither the v2 draft nor any ruling. They entered the
document because an AI wrote them, which is the failure mode DECISIONS.md exists
to prevent. Also unverified: rule 4 cites non-stitching as "D057 rule 3" where
the reviewed draft attributed containment to D055 rule 3. A miscitation in a
decision record propagates into every prompt that cites it.
**Status change in consequence, not in content (2026-09-02):** D060
implementation was gated on Coverage.1bB completing. That gate opened on
2026-09-02. H115 is now the only remaining blocker between the current state and
D060 implementation. Nothing may cite D060 as authority until those three rules
are adjudicated.
**Fix:** Read the committed entry against the seven rulings. Adopt rules 13, 15
and 16 by explicit adjudication or remove them. Verify the rule 4 citation
against D055 and D057. `Status: Proposed` means nothing downstream can cite it as
settled, so this is not blocking — but it must be closed before D060 is Accepted
or before any phase cites it.
**Suggested phase:** Before D060 adjudication

---

### H116 — Generic availability route records admin writes as employee-sourced

**Severity:** 🟡
**Status:** Open
**Area:** Availability / provenance
**Concern:** `POST /api/v1/availability` is guarded by `require_tenant_member`,
so an admin may call it, but it hardcodes `writer_identity="employee"` and
writes `source="employee"`. An admin-authored row is therefore recorded as
employee-authored. This is pre-existing and orthogonal to the overnight work,
but it undermines the provenance D048 records for future cross-source
precedence, and it means such rows take the employee advisory lock rather than
the admin one.
**Related, same route (added 2026-09-02):** `test_availability.py:290` now asserts
201 on a past-dated payload (`2026-04-06` / `2026-04-08`). That is correct
behaviour — the generic route has no past-date guard; only `employee.py` has
`_ensure_availability_is_future`. But the suite now locks that absence as though
deliberate, where previously it only exercised rejections. The generic route has
not been given the guards the employee path has.
**Fix:** Resolve writer identity and source from the acting principal, or decide
that admin writes must go through replace-week and close the generic route to
admins. Decide separately whether the generic route should carry the employee
path's past-date and published-week guards.
**Suggested phase:** Precedence phase, or alongside D060

---

### H117 — Employee availability UI has no cross-midnight affordance

**Severity:** 🟡 (reduced from 🟠 on 2026-09-02)
**Status:** Open
**Area:** Employee portal / availability entry
**Concern:** The gate is open as of Coverage.1bB-2b. Inverted times are now valid
data, and equal times are rejected with a legible error, so the original
silent-typo risk is closed. What remains is an affordance gap: the employee
availability form gives no indication that `22:00 → 06:00` is interpreted as
crossing midnight. An overnight row renders identically to a same-day pair. A
user cannot distinguish an intended overnight declaration from a mis-entered one
by looking at it.

Verified in-browser 2026-09-02: `21:00-06:00` saves and renders as
`21:00 - 06:00` with no midnight indicator.

The admin surface is unaffected: it remains binary and full-day under D048.
**Fix:** Belongs with D060's band UI, where Night is one of the four named bands
and the surface can show the resulting interval explicitly.
**Suggested phase:** D060 implementation

---

### H118 — API test container has no source bind mount; compose run can execute stale code

**Severity:** 🟠
**Status:** Open
**Area:** Developer workflow / test fidelity
**Concern:** The `api` service builds from `context: ..` with no `volumes:`
entry mapping the repository into `/app`, so
`docker compose run --rm api pytest` executes the last-baked image rather than
the working tree. Materialised during Coverage.1bB-2a: a deliberate
broken-clause causal proof passed against a stale image, appearing to show that
removing the clause changed nothing. The risk is highest in pre/post
experiments, where a change is temporarily removed precisely to prove causality
— the case where a false pass is most damaging.
**Fix:** Add `volumes: - ../:/app` to the `api` service, or document a
build-before-test rule in `docs/AI_WORKFLOW.md` together with required
container-side verification that the change under test is actually present. The
mount is the stronger fix; the documented rule depends on remembering it at the
moment it matters least.
**Suggested phase:** Developer workflow hardening

---

### H119 — Employee availability form shows `preferred_off` helper text for every type

**Severity:** 🟢
**Status:** Open
**Area:** Employee portal / availability UX
**Concern:** The employee availability form renders one helper line below the
Type select, unconditionally — `apps/web/app/employee/availability/page.tsx`
lines 302-304. Its text is the `preferred_off` explanation: "This records a
preference not to work. It does not by itself mark you as available." It
therefore misdescribes the other three types. Observed 2026-09-02 with Type set
to Available, where it tells the user their availability declaration does not
mark them available — the opposite of the truth.

Pre-existing. `IMPLEMENTATION_STATUS.md`'s Availability.1b entry records the
placement as "one line of **static** helper text below the select" and gives a
copy rationale written entirely in `preferred_off` terms; the consequence for
non-`preferred_off` types was not considered.
**Fix:** Make the helper text conditional on the selected type, or remove it and
put the `preferred_off` explanation on the option itself.
**Suggested phase:** D060 implementation, alongside H117

---

### H120 — README phase table is six phases out of date

**Severity:** 🟢
**Status:** Open
**Area:** Documentation / repository README
**Concern:** `README.md`'s phase table stops at Availability.1a and is missing
Availability.1b, Coverage.1bA-1, Coverage.1bA-2, Coverage.1bB-1, Coverage.1bB-2a
and Coverage.1bB-2b. Lines 161 and 247 still read "Availability.1a is complete.
Availability.1b is next."

Five phases of pre-existing drift, not created by Coverage.1bB-2b. Deliberately
not fixed in that phase's docs commit: adding one current row to a table missing
six entries would make the table more misleading, not less, because a reader
would take it as current and conclude the gap between 1a and 2b is real.
**Fix:** Bring the phase table and both prose lines current in one pass, as its
own piece of work.
**Suggested phase:** Documentation hardening

---

### H121 — Second publish path bypasses every readiness gate

**Severity:** 🔴
**Status:** Open
**Area:** Rota publishing / access control
**Concern:** `POST /api/v1/shifts/publish` (`shifts.py:460-492`) requires only
`require_tenant_role("admin")`, `_validate_range` and `_get_store_or_404`. It
sets `published_at` across a datetime range with no `_site_is_operationally_ready`
call, no no-shifts check and no already-published check.
`POST /api/v1/sites/{site_id}/rota/publish` (`sites.py:961-999`) enforces all
three. `POST /api/v1/shifts/unpublish` mirrors the unguarded path.

Two publish routes with two different contracts.
**Fix:** Establish which the frontend calls, then either align the gates or
remove the route.
**Suggested phase:** Publish path repair

---

### H122 — No lifecycle or revocation path for admin-side tenant users

**Severity:** 🔴
**Status:** Open
**Area:** Admin identity / tenant user lifecycle
**Concern:** Scope this precisely. Admin-side **self-service password reset
exists and is not the gap.** Q.4.2 shipped
`POST /api/v1/auth/password-reset/request` and
`POST /api/v1/auth/password-reset/confirm` with hashed single-use tokens,
1-hour expiry, session revocation and audit events. H058 is Done. Nothing here
implies otherwise.

What is missing is **owner-mediated lifecycle management of another tenant
user**. `apps/api/routers/admin_users.py` is 89 lines and contains exactly one
endpoint, `POST /users`. There is no endpoint to:

- list admin-side tenant users
- change an existing user's tenant role
- deactivate or revoke an existing user's admin access
- initiate a reset or re-invite on another user's behalf, if the product decides
  it needs one

Consequence: an admin created today cannot be removed except by direct database
access. Self-service password reset does not address revocation. Not shippable
to a paying customer.

Related: H102 records the equivalent gap on the employee side.
**Fix:** Add the listing and revocation surface first, then role change and
creation once store assignment exists under D063.
**Suggested phase:** Phase 1a (listing and revocation), completed in Phase 2

---

### H123 — Unreachable manager authorisation branch

**Severity:** 🟡
**Status:** Open
**Area:** Access control / dead code
**Concern:** `sites.py:63-78` contains a branch testing
`membership.role == "manager"` against `site.manager_user_id`. It cannot
execute: `"manager"` is not in `TENANT_ROLES`, not in `admin_users.py`'s
`_ALLOWED_ROLES`, and tenant registration assigns only `"owner"`. It is the only
occurrence of `"manager"` in the non-test API.

Dead authorisation code is worse than ordinary dead code. If `"manager"` ever
enters `TENANT_ROLES` the branch activates silently, with
single-manager-per-store semantics nobody adjudicated, on two endpoints out of
seven.
**Fix:** Delete the branch. D063 rule 5 requires this during the phase that
implements store assignment.
**Suggested phase:** Phase 2, store assignment

---

### H124 — `AdminUserCreate.full_name` is accepted and discarded

**Severity:** 🟢
**Status:** Open
**Area:** Admin identity / schema
**Concern:** The schema accepts `full_name` and the frontend sends it
(`staff-create-form.tsx:76`), but the `User` row is built from `email`,
`hashed_password`, `is_active` and `active_tenant_id` only
(`admin_users.py:58-63`). Admin-side users have no name stored.
**Fix:** Persist the value or remove the field from the schema.
**Suggested phase:** Phase 1a

---

### H125 — DECISIONS.md contains a duplicate D044 identifier

**Severity:** 🟡
**Status:** Open
**Area:** Documentation / decision integrity
**Concern:** Two distinct decisions share the identifier D044. A reference to
`D044` by identifier alone is therefore ambiguous, and an amendment aimed at one
decision may be applied to the other. Found 2026-09-02 while placing D062 and
D063.
**Fix:**

- inventory every D044 reference and determine which decision each intended;
- choose one historical decision to retain D044;
- reissue the other under the next unused decision number;
- leave an explicit historical note on the formerly duplicated entry and the
  reissued entry so the repair is traceable;
- update every reference whose intended target can be established.

Do not silently renumber either decision, and do not retire D044 while one valid
decision still retains that identifier.
**Suggested phase:** Documentation hardening / before the next amendment that
needs to cite either D044 decision.

---

### H126 — `AuthSession.is_revoked` model default disagrees with migrated PostgreSQL

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / session infrastructure / schema fidelity
**Concern:** `auth_session.py:53-58` declares `server_default=true()`, while
migration `0022:32` and live PostgreSQL use `false`. Live PostgreSQL is correct.
`create_all`-based schemas therefore disagree with migrated PostgreSQL about the
database default for this column. ORM inserts currently mask the discrepancy
because the model also declares `default=False` and every insert goes through
the ORM, but raw or default-dependent inserts and schema-fidelity tests can
observe different behaviour. No live path has been shown to observe it today;
the severity reflects the demonstrated impact, not the theoretical worst case.
Found 2026-09-03 during the Phase 1a inspection.
**Fix:** Align the model's `server_default` with the migrated and live `false`
default. No migration is expected, since live PostgreSQL is already correct.
**Suggested phase:** Authentication hardening

---

### H127 — `audit_logs` cannot record what changed

**Severity:** 🟡
**Status:** Open
**Area:** Audit / governance
**Concern:** `audit_logs` carries `id`, `tenant_id`, `user_id`, `action`,
`entity_type`, `entity_id`, `created_at`. There is no metadata, detail, or
before/after column, unlike `auth_security_events.metadata_json`. A governance
mutation can identify the actor, the action, and the affected entity, but cannot
record the prior state, the new state, the reason, or any other
mutation-specific detail. Found 2026-09-03 during the Phase 1a inspection.
**Fix:** Decide whether `audit_logs` gains a nullable JSON metadata column, or
whether governance actions that need detail write to `auth_security_events`
instead. The two mechanisms are currently split by subject rather than by detail
requirement.
**Suggested phase:** Audit hardening

---

### H128 — No zero-owner invariant exists outside migration `0027`

**Severity:** 🟡
**Status:** Open
**Area:** Tenant governance / data integrity
**Concern:** Migration `0027_phase_q4_4_owner_role`'s
`_backfill_one_owner_per_tenant` skips tenants with no `tenant_users` rows,
leaving them with no owner, and its `downgrade()` demotes every owner to
`admin`. The invariant exists only inside that one-time migration — it is not a
CHECK constraint, not a unique index, and not re-asserted by any service-layer
guard. Nothing detects or repairs a zero-owner tenant afterwards. Such a tenant
keeps functioning for everything except owner-only surfaces, which become
permanently unreachable, because `require_tenant_role("admin")` admits `admin`
as well as `owner`.

Not reachable through any current endpoint. D064 rule 5 keeps it unreachable
through Phase 1a by refusing owner memberships as revocation targets. Found
2026-09-03 during the Phase 1a inspection.
**Fix:** Decide whether the invariant belongs in a constraint, a service-layer
guard, or a detection task, and whether a zero-owner tenant should be repairable
without direct database access.
**Suggested phase:** Owner lifecycle

---

### H129 — DECISIONS.md `Date:` convention is unwritten

**Severity:** 🟢
**Status:** Open
**Area:** Documentation / decision integrity
**Concern:** Entries have used both date-decided and date-committed. D060 is
dated 2026-08-22 and committed 2026-08-23, its own header recording draft
lineage from 08-17. D062 and D063 are dated 2026-09-02 and committed
2026-09-03. D057, D058, D059 and D061 match their commit dates exactly. Nothing
records which the field means, so a reader cannot tell whether a mismatch is an
error or the convention working. Found 2026-09-03.
**Fix:** Record the convention in `CLAUDE.md` or in `DECISIONS.md`'s header. Do
not retrospectively alter existing dates; the ambiguity is in the rule, not in
the entries.
**Suggested phase:** Documentation hardening

---

### H130 — Admin account-security chain is unusable end to end

**Severity:** 🔴
**Status:** Open
**Area:** Authentication / admin portal frontend
**Concern:** The backend implements email verification (Q.4.3), TOTP enrolment,
login challenge verification, step-up, recovery-code use and disable
(Q.5.1/Q.5.2). None of that account-security chain is reachable from `apps/web`.
Password reset is Q.4.2 and is tracked separately under H058 and H132.

**Email verification:** no frontend surface calls
`POST /api/v1/auth/email-verification/request`; no api-client function exists;
`/admin/verify-email` does not exist as a route, so the URL the backend
constructs resolves to a 404; no banner or indicator exposes verification state,
and `UserOut` does not carry the field.

**2FA:** a case-insensitive search of `apps/web` for `2fa`, `totp`, `step_up`
and `recovery_code` returns zero hits across all seven endpoints.

**Login contract:** once 2FA is active, login returns `access_token=None`,
`token_type="2fa_pending"`, `requires_2fa=True` (`auth.py:1030-1032`). The
frontend type `AdminLoginResponse` (`api-client.ts:32-35`) declares
`access_token: string` with no challenge fields, and
`admin-login-form.tsx:143-150` calls `setAccessToken` unconditionally before
navigating. An owner who enrols 2FA out of band would therefore be unable to log
in through the portal. Read from source. Browser verification is required before
H130 is closed.

**Error handling:** `request()` (`api-client.ts:718-761`) special-cases 401
only. `error.code` IS read in sixteen places for domain-specific codes, so the
pattern exists — but no sensitive-action code is among them, and the dominant
convention is to match `error.status === 403` and render a fixed permission
string. A sensitive-action rejection would be indistinguishable from a genuine
permission failure.

**Impact:** the backend account-security capability is not product-usable, and
D040-governed sensitive actions cannot be wired. Blocks D064 rule 7 and
therefore Phase 1a's revoke mutation.
**Fix:** Q.5.3a-1 and Q.5.3a-2, then Q.5.3b and Q.5.3c. See `docs/HANDOVER.md`.
**Suggested phase:** Q.5.3a-1

---

### H131 — Store deactivation has no product surface

**Severity:** 🟡
**Status:** Open
**Area:** Feature reachability
**Concern:** `POST /api/v1/stores/{store_id}/deactivate` (`stores.py:386-392`)
is the only endpoint in the API guarded by `require_sensitive_admin_action`, and
it has no frontend caller. A grep for `/deactivate` in `apps/web` returns
`deactivateCoverageTemplate` and `deactivateWorkArea`, neither of which is
guarded by that dependency and both on different routers — a search for
"deactivate" in the frontend can therefore create a false impression that the
sensitive path is wired. It is not, and has never been exercised from the
product. Found 2026-09-03.
**Fix:** Decide whether store deactivation gains a surface, and if so whether it
waits for Q.5.3c like the Phase 1a revoke mutation.
**Suggested phase:** after Q.5.3c

---

### H132 — No human-reachable email delivery backend exists

**Severity:** 🔴
**Status:** Open
**Area:** Email delivery / account recovery
**Concern:** The only EmailService implementations at HEAD are `local_log` and
`test_capture` (`apps/api/services/email/__init__.py:9-13`). `EMAIL_BACKEND`
defaults to `local_log` (`settings.py:16`) and `infra/docker-compose.yml` does
not override it. `local_log` deliberately redacts `verification_url` and
`reset_url` via `FORBIDDEN_CONTEXT_KEYS` (`local.py:28-45`), rendering them as
`<REDACTED:length=N>`. Raw tokens exist only in request memory; `auth_tokens`
stores a SHA-256 hash with no raw column. No production provider exists.

This blocks two flows, not one:

```text
email verification   Q.4.3, gates require_sensitive_admin_action at
                     deps.py:262
password reset       Q.4.2, uses the same EmailService with a
                     password_reset template
```

A user who forgets their password today cannot recover it through the product,
for the same structural reason an owner cannot verify their email. See H058,
which carries a second independent blocker of its own.

The redaction is correct and test-locked and must not be weakened. The gap is
delivery, not logging.
**Fix:** A local SMTP EmailService delivering to a local mailbox for
development, and a real transactional provider for production, per the
2026-09-03 amendment to D038 Decision 7.
**Suggested phase:** Q.5.3a-1 for the development delivery backend. The
production provider is a separate launch-blocking phase.

---

### H133 — Sentry frame-local capture can transmit raw credentials

**Severity:** 🔴
**Status:** Done
**Area:** Observability / credential exposure

**Concern:** `sentry_sdk.init` is called with five arguments and does not set
`include_local_variables`, which defaults to `True`. Frame locals are therefore
serialised into every captured exception. The repository's `_before_send` hook
inspects only `event["request"]` — headers, cookies and data — and never touches
`exception.values[].stacktrace.frames[].vars`. The SDK's own default
`EventScrubber` does scrub frame vars, but by **exact lowercase key match** and
non-recursively.

The consequence is that in the auth request handlers, at the moment `send_email`
is called:

```text
token         denylisted, scrubbed
raw_token     NOT denylisted, captured verbatim
token_hash    NOT denylisted, captured
dummy_token   NOT denylisted, captured
context       NOT denylisted, non-recursive — captured with the complete
                reset_url / verification_url
normalized_email                captured
payload       captured as repr — on the reset confirmation path this is a
                Pydantic model holding the plaintext new password
```

`send_default_pii=False` adds only IP-address-related keys to the denylist and
does not help. `DEFAULT_MAX_VALUE_LENGTH` is `None`, so no truncation intervenes.

**This exists at HEAD and is independent of Q.5.3a.** An `IntegrityError` from
the existing `db.commit()` in the password-reset request handler is already
sufficient to trigger it. Q.5.3a makes it far more likely by introducing the
first component in that frame that can fail routinely.

**Currently transmitting?** No. `init_observability()` returns immediately unless
`SENTRY_DSN` is truthy; the default is `None`, and it is set in neither
`infra/docker-compose.yml` nor `.github/workflows/ci.yml`, and no `.env` exists.
Exposure is conditional on a DSN being injected into a deployed environment,
which is precisely what the variable exists for.

**Historical exposure: none established. Checked 2026-09-04.**

`read` — `git log -S "sentry.io"` returns no commits, so no DSN value ever
entered the repository history; the two hits for `SENTRY_DSN` are the Q.0 and
Q.1 commits that added the code reading it. No `.env` has ever been committed or
exists on disk. `SENTRY_DSN` appears in no shell profile, no shell history, no
exported environment, and no running container.

`owner-confirmed` 2026-09-04 — ForecourtOS has only ever run on Vachan's local
machine; no deployed or externally hosted instance has existed.

Those two together are what the classification rests on. Repository and local
inspection cannot by themselves prove that no external process ever received an
injected DSN; the owner confirmation closes that gap and is recorded as such
rather than folded into the inspection findings.

On that basis the defect is **latent**, not an incident. This matters because the
password-reset confirmation frame holds a user-chosen plaintext password inside
a Pydantic model whose `repr` prints field values — had a DSN ever been active,
this would have been an incident-response question about historical Sentry event
history rather than a hardening item.

**Fix (Q.5.3a-0), two independent controls:**

1. `include_local_variables=False` in `sentry_sdk.init`.
2. **Strip `exception.values[].stacktrace.frames[].vars` entirely in
   `_before_send`**, unconditionally, regardless of SDK configuration.
3. Retain `send_default_pii=False`.
4. Separately, extend `_before_send` with recursive scrubbing of structured
   request and context data by key: `token`, `raw_token`, `token_hash`,
   `access_token`, `refresh_token`, `password`, `new_password`,
   `confirm_password`, `authorization`, `cookie`, `reset_url`,
   `verification_url`, and secret/API-key-shaped keys.

**Why item 2 rather than key-based scrubbing of frame vars.** Key matching
cannot reach this failure mode. The dangerous local is `payload` — a Pydantic
model serialised as a `repr` string. Once `new_password='...'` is text inside
that string, under the innocuous key `payload`, there are no inner keys for any
scrubber to match. Item 4 alone would defend against a different attack than the
one this entry documents.

Items 1 and 2 are genuinely independent: item 1 prevents collection, item 2
removes the data at event level even if item 1 is later flipped back.

**Regression tests must inject a secret under an innocuous local variable name**
— `payload` or equivalent — not only under `raw_token`. A test using an obvious
name passes while the real hole stays open. Cover three placements: request
data, a nested dictionary, and an exception frame variable.

The only existing Sentry test asserts scrubbing of request headers, cookies and
body only. Frame-variable capture is untested and unhandled.

**Resolved in Q.5.3a-0**, with the two independent controls this entry called
for:

- `include_local_variables=False` in `sentry_sdk.init`, preventing collection.
- Unconditional removal of `vars` from every frame in `_before_send`, at event
  level and regardless of SDK configuration. All five stacktrace interfaces are
  covered: the top-level `stacktrace`, and `stacktrace` and `raw_stacktrace`
  under each of `exception.values[]` and `threads.values[]`.

Key-based scrubbing was extended as well, but as the separate defence this entry
described — recursive, with a depth bound and cycle detection, applied to
`request`, `contexts` and `extra`, over a widened key set that adds
`new_password`, `confirm_password`, `raw_token`, `token_hash`, `secret`,
`api_key`, `reset_url` and `verification_url`. A malformed event is dropped
rather than passed through.

The regression places a credential under an innocuous local name — `payload`,
holding the `repr` of a `PasswordResetConfirmRequest` — across all five
interfaces, which is the placement key matching cannot reach. `sentry-sdk` is
pinned at `2.68.1` under H140, so the version-dependent behaviour this entry
rests on no longer floats.

**Suggested phase:** Q.5.3a-0

---

### H134 — `ENV` is unvalidated, unset everywhere, and gates the refresh cookie's `Secure` flag

**Severity:** 🔴
**Status:** Done
**Area:** Configuration / session security

**Concern:** `ENV` is a plain `str` with default `"dev"`, no `Literal`, no
validator and no allowed-value list. It is not set in
`infra/docker-compose.yml`, not set in `.github/workflows/ci.yml`, and no `.env`
exists in the repository. Every repository-configured environment therefore runs
as `"dev"`.

The refresh cookie's `Secure` flag is computed as
`settings.ENV.lower() not in {"dev", "test", "local"}` in two places. A deployed
production process that simply omits the variable would issue a non-`Secure`
refresh cookie.

**Omission is the fail-open case, and it is the likeliest one**, because it
requires no action at all. An unrecognised *value* such as `ENV=prod` happens to
fail secure under the current expression — it is not in the permissive set — but
that is incidental rather than a designed property, and it does not make the
unvalidated vocabulary safe.

`ENV` is read in exactly four production places: the Sentry environment label,
the health-check body, and the two cookie flags.

**Fix:** D065 rule 2 proposes the repair — an explicit validated set with no
implicit default, enforced at startup. Logged separately because the cookie
posture is a launch blocker in its own right and must not be considered closed
merely because an email phase touched the same variable.

**Resolved in Q.5.3a-0.** The recorded defect was the implicit `ENV="dev"` path
yielding a non-`Secure` refresh cookie in production. It is closed:

- `ENV` has no default and is required. Missing or unrecognised values raise at
  settings construction, so the application cannot start on a coerced value.
- The canonical set is exact: `local`, `development`, `test`, `staging`,
  `production`.
- Both cookie paths use the new vocabulary — `_set_refresh_cookie` and
  `_clear_refresh_cookie` — so a cleared cookie carries the same flags as the
  one it clears.
- Tests prove `Secure=False` for `local`, `development` and `test`, and
  `Secure=True` for `staging` and `production`, on both paths.

A production smoke test of the cookie posture remains sensible as deployment
verification. It is not an open code defect.

**Suggested phase:** Q.5.3a-0 for the validation; verify the cookie posture at
the production security gate.

---

### H135 — D037's declared event vocabulary is substantially narrower than the live database constraint

**Severity:** 🟡
**Status:** Open
**Area:** Decision records / audit integrity

**Concern:** D037's "use these exact `event_type` values" section lists thirteen
values. The live database CHECK permits twenty-nine.

The gap is **unreconciled decision-record drift, not unauthorised code drift.**
D038 Decision 10 explicitly instructed future implementation to extend D037 with
eight password-reset and email-verification event types, and Q.4.2 and Q.4.3
implemented exactly that. Those values are authorised; D037's own vocabulary
section was simply never updated to record it.

Whether the remaining values — added by Q.5.1, Q.5.1b and Q.5.2a for 2FA and
step-up — carry equivalent authorisation from D039 or another accepted decision
**has not been verified**, and should be established as part of the
reconciliation rather than assumed in either direction.

The consequence either way: a decision record sixteen values out of step with
the schema it governs cannot be cited as authority for what the vocabulary is,
and any amendment to it would be amending a stale section.

**Fix:** Reconcile D037's vocabulary section against the live constraint by
explicit adjudication, recording for each value the decision that authorised it
— or, where none exists, adjudicating it. Do not retrofit this inside an
unrelated phase.

**Suggested phase:** Documentation / decision hardening

---

### H136 — D037's forbidden-metadata rules have no enforcement point

**Severity:** 🟡
**Status:** Open
**Area:** Audit integrity

**Concern:** D037 lists categories forbidden in event metadata "under all
circumstances" — raw tokens, token hashes, cookie values, passwords,
Authorization header contents, email addresses, secret material, and anything
uniquely identifying a person.

`_add_auth_security_event` performs a single `db.add` and passes the caller's
dict through unmodified. There is no allowlist, no denylist, no redaction and no
depth limit — nothing analogous to `FORBIDDEN_CONTEXT_KEYS` in the email logging
path. The `metadata_json` column has no CHECK, no key restriction and no size
limit.

Compliance is entirely call-site discipline plus per-phase tests. Those tests
are good — they assert whole-row absence of raw tokens, hashes, URLs, emails and
passwords — but each only covers the events its own phase produces. A new call
site can violate D037 with nothing failing.

**Fix:** Decide whether the prohibition belongs in a sanitising layer inside the
helper, in a shared test fixture applied to every event-producing test, or both.

**Suggested phase:** Audit hardening

---

### H137 — No security response headers exist in either tier

**Severity:** 🟡
**Status:** Open
**Area:** Web security baseline

**Concern:** Exhaustive search across `apps/`, `infra/` and `.github/` finds no
`Referrer-Policy`, `Content-Security-Policy`, `X-Robots-Tag`,
`Permissions-Policy`, `Strict-Transport-Security` or `X-Frame-Options` anywhere.
The only response header the backend sets is `X-Request-ID`. `next.config.ts` is
five lines and has no `headers()` function.

There is no route-specific or global mechanism a page can reuse; one must be
created.

D065 rule 9 scopes narrow controls to the two credential-bearing pages only,
deliberately. This entry covers the broader absence.

**Fix:** A global baseline — CSP, HSTS, frame policy, referrer policy — decided
and applied at the appropriate tier.

**Suggested phase:** Pre-customer security hardening

---

### H138 — Admin email identity is case-sensitive on login and case-insensitive on recovery

**Severity:** 🟡
**Status:** Open
**Area:** Identity / account recovery

**Concern:** Registration stores the address verbatim — no normalising
validator, and the column is a plain case-sensitive unique `String(255)`. Login
matches exactly. The password-reset request strips and lowercases before lookup.

An account registered as `Owner@Example.com` logs in normally, but its reset
lookup misses and returns the generic 202 — indistinguishable from a
nonexistent account, by design. The user cannot recover their password and
receives no signal that anything is wrong.

Invisible today because nothing delivers. It becomes a customer-visible recovery
failure the moment delivery works.

Not covered by any existing test: every Q.4.2 test registers a lowercase
address.

**Fix:** Settle admin login identity as case-insensitive. The repair spans
registration, login matching, uniqueness semantics and probably a functional
`lower()` unique index migration — and must begin with an inspection for
existing case-colliding rows, which cannot be resolved by silently choosing one
account.

**Deliberately not folded into Q.5.3a.** It is identity-normalisation work, not
email delivery. Use a lowercase throwaway address for the Q.5.3a browser gates.

**This is a named prerequisite for declaring H058 product-complete.** D065's
completion boundary scopes Q.5.3a to canonically-cased addresses. Q.5.3a-2 may
finish its own implementation and gates, but H058 must not be described as
universally complete while a valid class of admin account cannot recover.
Pre-customer blocker.

**Suggested phase:** Identity normalisation, before first customer

---

### H139 — Frontend role union still contains `manager` and rejects `member`

**Severity:** 🟡
**Status:** Open
**Area:** Frontend / role contract

**Concern:** The backend union is `owner | admin | member`. The frontend
`AuthMeResponse` declares `owner | admin | manager`, and the runtime type guard
in the admin shell accepts those three and rejects `member` — a rejected guard
throws, clears the access token and redirects to login.

D063 settled that no `manager` tenant role will ever be created. The frontend
type therefore names a role that will not exist and omits one that does.

Unreachable in practice today, because admin login requires an admin-portal
role, so a `member` never obtains an admin session. Two frontend declarations of
the same field also disagree with each other — `AdminRegisterResponse` uses the
correct three-value union.

H123 covers only the backend dead branch in `sites.py`. Nothing covers the
frontend occurrences.

**Fix:** Align the frontend union and guard with the backend. Do not piggyback
onto an unrelated diff unless that diff necessarily modifies the exact type and
the correction can be proven independently.

**Suggested phase:** With Phase 1a or Phase 2, where the role surface is
already being touched

---

### H140 — `sentry-sdk` is unpinned

**Severity:** 🟢
**Status:** Done
**Area:** Supply chain

**Concern:** `sentry-sdk` is declared without a version. The security-relevant
behaviour in H133 — the default value of `include_local_variables`, the
scrubber's exact-match denylist, and its non-recursive default — is
version-dependent, and the container resolves whatever is current at image
build. The repository's emergent convention pins security-relevant packages
exactly (`cryptography`, `pyotp`) and leaves older infrastructure bare.

**Fix:** Pin, per D035's "pinned or locked to current project standard". Worth
considering alongside a broader dependency-pinning pass rather than alone.

**Resolved in Q.5.3a-0.** `sentry-sdk==2.68.1`, pinned exactly in
`apps/api/requirements.txt`, alongside the H133 repair whose correctness depends
on that version's behaviour. Justified under D035 as a security-relevant pin, in
the same convention as `cryptography` and `pyotp`. `pip-audit` at `2fd3b99`
reports no vulnerability against 2.68.1; see H147 for the two packages it does
report.

**Suggested phase:** Supply chain hardening

---

### H141 — `AUTH_SECURITY_EVENT_TYPES` is dead advisory code

**Severity:** 🟢
**Status:** Open
**Area:** Audit integrity / maintainability

**Concern:** The event-type tuple in the model is imported by nothing and
checked by nothing. The routers use their own independent module-level
`AUTH_EVENT_*` string constants. Two lists must be kept in sync by hand, and no
test proves they are. The declarative SQLAlchemy CHECK is likewise inert,
because `create_all` is forbidden.

**Fix:** Either make the constant the single source the routers draw from, or
delete it. A constant that looks authoritative and enforces nothing is worse
than no constant.

**Suggested phase:** Audit hardening

---

### H142 — `metadata_json` type drift between model and migration

**Severity:** 🟢
**Status:** Open
**Area:** Schema parity

**Concern:** The migration creates the column as `postgresql.JSONB`; both the
`AuthSecurityEvent` and `AuthToken` models declare generic `JSON`. Harmless
while `create_all` is forbidden and no JSONB operator is used, but the
declarative model does not describe the live schema.

Related to H110's broader model-versus-migration parity concern.

**Fix:** Declare `JSONB` in the models, or record the divergence deliberately.

**Suggested phase:** Schema parity

---

### H143 — Documentation drift found during the Q.5.3a inspections

**Severity:** 🟢
**Status:** Partial
**Area:** Documentation accuracy

Grouped because each is a one-line correction and none affects behaviour:

- **D038 Decision 2 versus the live `auth_tokens` schema.** The decision proposes
  `expires_at ... not null`; the model is nullable. It fails closed — a NULL
  `expires_at` row can never be consumed — and nothing writes NULL today. The
  decision's expected index set also differs from the live one, and a third
  token type, `recovery_code`, exists in the live CHECK constraint and in the
  model but was never recorded in D038.
- **`README.md` describes `APP_BASE_URL` as password-reset-only.** It supplies
  the host for both the reset and verification URL builders. D038's amendment
  states this correctly; the README does not.
- **`README.md` describes `EMAIL_BACKEND`'s allowed values as "Q.4.1 values".**
  Those are the allowed values at HEAD, full stop. The phase qualifier implies a
  later phase widened them; none has.
- **H130 states login returns `access_token=None` under 2FA.** The route is
  declared `response_model_exclude_none=True`, so the key is absent from the
  JSON rather than null, and the frontend reads `undefined`. H130's conclusion is
  unaffected; the mechanism differs.
- **`docs/GPT_REVIEW_PREAMBLE.md`'s authority list omits `README.md`**, which
  `docs/HANDOVER.md` places above live code in its own ordering.

**Fix:** Correct in a documentation commit. Do not bundle into an
implementation diff.

**Closed by Q.5.3a-0 and this documentation pass:**

- The `EMAIL_BACKEND` "Q.4.1 values" row. Rewritten in `2fd3b99` to state the
  implemented values and their environment constraint.
- The `docs/GPT_REVIEW_PREAMBLE.md` authority list. `README.md` is now present,
  in the position `docs/HANDOVER.md` gives it.

**Still open:** the D038 Decision 2 schema drift, the `README.md` `APP_BASE_URL`
row, and H130's `access_token=None` wording.

**Suggested phase:** Documentation hardening

---

### H144 — The completed Q.2.2 supply-chain audit was never committed

**Severity:** 🟡
**Status:** Open
**Area:** Supply chain / record integrity

**Concern:** The repository copy of `SUPPLY_CHAIN_AUDIT_2026-05-11.md` at
`a4e7ccf` is an **unfilled template**. Verified 2026-09-04:

```text
line 28   Python registry existence check:  TODO
line 33   npm registry existence check:     TODO
line 45   Suspicious packages follow-up:    TODO
line 49   Final decision:                   TODO
```

Those TODOs sit above a completed sign-off block. A signed-off audit with
unfilled verification fields is worse than an unsigned one, because a future
D035 evaluation may cite it as completed.

**A completed version of this audit exists and was never committed.** The copy
in the AI project knowledge records every Python and npm package as `EXISTS`,
records the `pip-audit` and `npm audit` results, marks the final decision as
"No slopsquat-style anomalies were found", and carries the sign-off. It also
still contains the instruction that was meant to follow it —
`After saving, run: git status --short` — which is the tell that it was produced
and never written to disk.

So the finding is not that the checks were skipped. It is that **the work was
done and the record was lost**, leaving the repository asserting less than was
actually verified.

**Fix:** Reconcile the two copies. Establish whether the completed results are
still trustworthy at today's dependency set — the audit is dated 2026-05-11 and
`requirements.txt` has changed since — then either commit the completed audit or
re-run and commit fresh results. Do not simply paste the uncommitted copy
forward without re-checking.

**Suggested phase:** Supply chain hardening

---

### H145 — Project-knowledge documents diverge from, or have no counterpart in, the repository

**Severity:** 🟡
**Status:** Open
**Area:** Process / review integrity

**Concern:** `CLAUDE.md` requires governing documents uploaded to AI project
knowledge to be sourced only from the WSL repository path, because a stale copy
that wins a search produces false review findings.

On 2026-09-04 that failure occurred in the other direction. The project-knowledge
copy of `SUPPLY_CHAIN_AUDIT_2026-05-11.md` is **ahead of** the repository — a
completed audit that was never committed — while the repository holds the
unfilled template. An independent cold review, reading the project-knowledge
copy, concluded that H144 was a false finding and recommended deleting it. It was
not false. The repository copy carries the TODOs.

The rule as written guards against **stale** uploads. This case shows the risk is
divergence in either direction, and that an uncommitted document reaching project
knowledge is as dangerous as an outdated one — arguably more so, because it looks
more complete than reality rather than less.

The upload rule also names four governing documents explicitly. This file is not
among them, which is how it drifted without anyone noticing.

**Full comparison completed 2026-09-04.** All 28 project-knowledge documents
were compared against the repository at `a4e7ccf` by SHA-256 and line count:

```text
byte-identical            10   including all four governing documents,
                               README.md and CLAUDE.md
diverge                    2   SUPPLY_CHAIN_AUDIT_2026-05-11.md
                                 (325 lines vs 58 in the repository)
                               forecourt_os_permission_matrix_current_v1.md
                                 (167 lines vs 177)
no repository counterpart 16
```

The sixteen unanchored documents:

```text
__ANCI_OPS_SUITE                    STAFF_RULES_SOURCE_OF_TRUTH_v1
STAFF_SITE_CONSOLIDATION_v1         STAFF_SITE_CONSOLIDATION_v2
permission_matrix_v1                prd_v1
prd_v1_1                            api_contracts_v1
ai_architecture_prd_v1              frontend_pages_prd_v1
billing_architecture_prd_v1         deployment_runbook_v1
testing_strategy_v1                 data_retention_policy_v1
incident_response_policy_v1         security_review_checklist_v1
```

Two further observations:

**A Windows fingerprint on the diverging file.** Exactly two project-knowledge
documents use CRLF line endings — `SUPPLY_CHAIN_AUDIT_2026-05-11.md` and
`forecourt_os_prd_v1_1.md`. Every other file is LF, which is what the WSL
repository produces. The one file independently proved to diverge is one of the
two carrying the Windows fingerprint. Not proof of origin, but the strongest
available signal, and it points at the source the upload rule exists to exclude.

**A live consequence, already corrected.** `deployment_runbook_v1` is one of the
sixteen. An external review cited its environment vocabulary during the D065
drafting, and the draft carried "matches the deployment runbook" as
justification for rule 2's `ENV` tokens. D065 now states the vocabulary on its
own merits and records the runbook as unanchored. Had the comparison not been
run, a decision would have entered `DECISIONS.md` citing a document with no
committed source.

**Fix:** Three parts.

1. Extend the `CLAUDE.md` upload rule: every project-knowledge document must be
   an exact copy of a **committed** file at a stated commit. Nothing uncommitted
   is uploaded. State that the risk is divergence in either direction, not
   staleness.
2. Resolve the two diverging files. For the audit, see H144. For the permission
   matrix, establish which of the two is correct and commit it.
3. Decide what to do about the sixteen unanchored documents. Each is either
   worth committing — at which point it acquires a position in the authority
   hierarchy and can be verified — or worth removing from project knowledge.
   Leaving them in place means sixteen documents in every review context that no
   inspection can check and no reviewer should cite.

**Suggested phase:** Process hardening, before the next external review packet

---

### H146 — Email backend names can drift between registry and factory

**Severity:** 🟡
**Status:** Open
**Area:** Configuration / maintainability

**Concern:** Q.5.3a-0 introduced a second, independent list of valid email
backend names. Two now exist:

```text
Settings.EMAIL_BACKEND_ENVIRONMENTS   apps/api/core/settings.py
get_email_service                     apps/api/services/email/__init__.py
```

Nothing keeps them in sync, and no test asserts they agree. This is the H141
pattern in a second place.

The failure direction is the dangerous one. Adding a backend to `Settings`
without adding it to the factory means settings validation accepts the value at
startup and the factory raises on the first send, so the caller receives an
HTTP 500 — the exact defect Q.5.3a-0's startup validation was built to
eliminate. The opposite drift is benign: a factory branch unreachable because
settings rejects the name.

**Fix:** Make one list the source the other derives from, or add a test
asserting the two agree. The next phase adds a third backend, which is when the
drift becomes reachable.

**Suggested phase:** Q.5.3a-1

---

### H147 — Python dependency audit gate is red

**Severity:** 🔴
**Status:** Open — resolution adjudicated 2026-09-05; unimplemented
**Area:** Supply chain / CI integrity

**Concern:** `pip-audit` at `2fd3b99` reports 10 known vulnerabilities across
two packages:

```text
cryptography  42.0.8   pinned in Q.5.1; fixes available upstream
ecdsa         0.19.2   transitive; no upstream fix at time of writing
```

The findings are pre-existing. Q.5.3a-0 did not introduce them, and its CI run
did not surface them either — the Q.5.3a-0 review noticed the standing failure.
`sentry-sdk==2.68.1`, added by that phase, is not among the reported vulnerable
packages.

**The immediate consequence is that CI can no longer signal whether the next
phase broke something.** A gate that is red for inherited reasons makes the next
failure ambiguous — a reviewer cannot tell a new regression from the standing
noise without reading the full audit output every time. That is what makes this
urgent, independently of the vulnerabilities' own severity.

The 🔴 severity is assigned to the CI gate being red, not to the advisories. The
vulnerabilities' own severity follows from the triage rather than from a label
assigned in advance.

H064 tracks the existence of the audit machinery and remains Done. This is a
finding the machinery produced, not a failure of the machinery.

**Corrections and further findings, 2026-09-05.** C-1 to C-3 correct statements
this entry originally carried; C-4 to C-7 record findings it lacked.

**C-1 — The pin's origin is wrong**

```text
observed   git log -S "cryptography==42.0.8" → f85d9e0, 2026-05-22,
           "feat: add q5.1 totp 2fa backend"
```

It entered in **Q.5.1**, not Q.0. Q.0 swapped `passlib[bcrypt]` for `bcrypt` and
added `sentry-sdk`; it did not add `cryptography`. The
`python-jose[cryptography]` extra predates both.

**No reason for that specific version is recorded anywhere.** The Q.5.1 record
describes the pin without justifying the version, and D039 Decision 5 records a
supply-chain decision for `pyotp` only. The sole version constraint in the
installed set is `cryptography>=3.4.0`, from `python-jose`.

**C-2 — "Remove" is not an available course for `ecdsa`**

Removal is unavailable under the current install model.

```text
python_jose-3.5.0.dist-info/METADATA

  Requires-Dist: ecdsa!=0.15                                  unconditional
  Requires-Dist: cryptography>=3.4.0; extra == "cryptography"  the extra ADDS
```

The `[cryptography]` extra adds a package; it does not remove one.
`pip install -r requirements.txt` reinstalls `ecdsa` regardless of whether
anything imports it.

`ecdsa` is **not removable under the current resolver and install model.** Not
universally impossible: `python-jose` documents `ecdsa`, `rsa` and `pyasn1` as
unused when the `cryptography` backend wins, and a `--no-deps` install with
explicit dependency management would technically drop it. That route trades
reproducibility for one unused package and is not recommended — but an options
record should name it rather than foreclose it.

**Usage and removability come apart.**

**C-3 — The gate did not go red at Q.5.3a-0**

```text
observed   the audit step has failed on every push-triggered run since
           df38496, 2026-08-02 — 38 consecutive failures across five weeks,
           spanning Coverage.1bB-2b and all Q.5.3a documentation work
```

Q.5.3a-0 did not introduce the findings, which H147 states correctly. But its
run did not surface them either: **the Q.5.3a-0 review noticed the standing
failure.**

**C-4 — The npm gate has been silently disabled**

`Python dependency audit` precedes `npm dependency audit` in the same CI job, so
its failure leaves the npm step skipped.

**The CI npm audit has not run for five weeks.** One red step disabled a second
gate nobody was watching. Tracked as H149, which owns it; recorded here because
it is a consequence of this entry's condition.

**C-5 — The historical finding set is verified**

`externally verified` 2026-09-05 — GitHub Actions job `101363808505` for `2fd3b99`
installed `pip-audit 2.10.1` and printed exactly the ten rows the inspection
reproduced, including the duplicated `PYSEC-2026-35` and `PYSEC-2026-3553` rows.

The inspection could not retrieve this log — the endpoint requires admin rights
and `gh` was unavailable — and correctly recorded the set as unverified rather
than substituting a fresh run. It is now verified.

**C-6 — The transition date is unestablished, and why**

```text
2026-05-09  4f313c2  Q.1 CI hardening. Security job is secret-scan only;
                     no audit step exists. Run: success.
2026-05-11  4c7a8f2  Q.2.2 adds the pip-audit step.
2026-05-11           SUPPLY_CHAIN_AUDIT records a clean audit — of a
                     requirements file that did not yet contain the pin.
2026-05-22  f85d9e0  cryptography==42.0.8 enters requirements.txt.
      ————           no retained CI run in this window ————
2026-08-02  df38496  Earliest retained run containing the step. Failing.
```

Actions retention holds no run between 2026-05-09 and 2026-08-01 — the entire
window in which the transition occurred. The last retained passing security job
predates the gate's existence; the first retained run including it was already
failing.

Consistent with the gate going red through published advisories rather than a
repository change, but **consistency is not evidence of the date.** Recorded as
unestablished.

**C-7 — Context: how the pin entered unexamined**

D039 Decision 5 requires Q.5.1 to run dependency and audit checks after adding
`pyotp`. The Q.5.1 recorded checks list shows a build, an Alembic upgrade, and
one pytest file. No audit appears. CI would have run one on push, but no run is
retained for `f85d9e0`.

A historical process gap, not a live divergence. Recorded because it explains
how a pinned security dependency entered without its version being examined,
and because the same gap would let the next one in.

**Fix:** Adjudicated 2026-09-05, in three parts.

**R-1 — `cryptography`: upgrade to 49.0.0**

**Target: `cryptography==49.0.0`.** The lowest version clearing every reported
finding.

`externally verified` correction to the inspection: the inspection attributed
49.0.0's backwards-incompatible changes to 50.0.0. They landed in **49.0.0** —
SECT\* binary curve removal, OpenSSL 1.1.x support removal, key loading raising
`UnsupportedAlgorithm` instead of `ValueError`, `*_KEY_TYPES` alias removal, and
the ChaCha20 nonce change. 50.0.0 adds a PKCS7 behaviour change and FFDH
deprecation; 50.0.1 rebuilds wheels against OpenSSL 4.0.2.

**So the minimum upgrade already crosses the breaking boundary.** 49.0.0 is not
minimal because it is safe; it is minimal because nothing requires more.

Taking 50.x would add a PKCS7 change, an FFDH deprecation and a new OpenSSL
build to a security repair that does not need them, and the compatibility proof
would then cover variables the repair never introduced.

**This target is subject to compatibility proof, not asserted as safe.** The
application's own surfaces — `AESGCM.encrypt`, `AESGCM.decrypt`, `InvalidTag` —
are unchanged across the range.

The unproven surface is `python-jose 3.5.0` against `cryptography 49.0.0`, seven
major-version numbers above the repository's current pin — specifically its
`cryptography_backend` key loading, which 49.0.0 changed to raise
`UnsupportedAlgorithm` where it previously raised `ValueError`. The changelog
cannot answer whether that breaks anything here. Running the suite can.

The implementation must prove causally, not by import check:

```text
JWT encode and decode through the application's own code path
admin and employee auth/session regression
2FA enrolment, login challenge, step-up, recovery-code paths
AES-GCM TOTP encrypt and decrypt round trip
the full backend suite
pip-audit showing every cryptography finding cleared
CI proving the resolved dependency set, not a local import check
```

The Docker `api` service has no source bind mount. Any before/after comparison
requires an explicit `docker compose build api` and container-side verification.

**R-1 must also re-prove the evidence R-2 depends on.** `python-jose` selects
its backends by catching `ImportError` from `cryptography_backend`. Changing
`cryptography` is exactly the change that can flip a binding, and a partial
break is the dangerous case: if 49.0.0 breaks only the EC backend import, HS256
continues to work, the suite looks healthy, and `ECKey` silently falls back to
`ecdsa` — turning an accepted-as-unreachable package into a reachable one while
every visible signal stays green.

So R-1 carries this obligation, before any suppression lands:

```text
bump to 49.0.0
rebuild the image
re-run the backend key-binding probe: all four classes — HMAC, EC, RSA, AES
perform a real application JWT encode and decode
confirm ecdsa is absent from sys.modules, including after an ES256 lookup
```

If any binding has moved to a non-cryptography backend, **halt and report.**
R-2's acceptance does not hold and the phase stops there.

If `python-jose 3.5.0` proves incompatible with 49.0.0, **halt and report.**
Replacing the JWT library is a separate adjudication, not a fallback inside a
dependency bump.

**R-2 — `ecdsa`: conditional acceptance of `PYSEC-2026-1325`**

**Accepted conditionally under D066, subject to R-1's post-upgrade proof.**

The unreachability evidence below was gathered against `cryptography==42.0.8`.
R-1 replaces that version, and `python-jose` binds its backends by catching
`ImportError` from `cryptography_backend` — so the upgrade is precisely the
change capable of invalidating this record. **The acceptance is not final until
the bindings are re-proved against the rebuilt 49.0.0 image**, and the
suppression must not land before that proof.

The record D066 rule 2 requires:

```text
advisory        PYSEC-2026-1325

no fix          The Minerva timing attack against P-256. Affects ECDSA
                signing, key generation and ECDH. Signature verification
                is unaffected. Upstream states no fix is planned.

unreachable     Verified against installed code, not documentation.
                jose/backends/__init__.py binds four key classes
                independently by try/except ImportError; there is no
                globally selected backend. In this image all four resolve
                to cryptography_backend. A real JWT encode/decode round
                trip through the application's own code leaves ecdsa
                absent from sys.modules, and it remains absent after an
                ES256 key-class lookup. The single other reference, in
                jose/utils.py, sits in an except ImportError branch that
                is not taken.

                The advisory's affected operations — signing, keygen,
                ECDH — are not operations this application performs
                through this package at all.

not removable   ecdsa!=0.15 is an unconditional requirement of
                python-jose 3.5.0. See C-2.

re-review       (a) ANY cryptography version change — the bindings are
                    resolved by import success against that package, so
                    every version change can move them. R-1 triggers
                    this immediately.
                (b) JWT_ALGORITHM is set to any EC algorithm — see H148
                (c) cryptography ceases to be installed, which would
                    change every backend binding
                (d) python-jose is replaced or upgraded
                (e) an upstream fix is published
                (f) unconditionally before first customer use

accepted        Vachan, 2026-09-05 — CONDITIONALLY, per D066 rule 5.
                This acceptance becomes effective only if R-1's
                post-upgrade binding and reachability proof passes
                exactly as specified. If that proof fails or diverges in
                any respect, the acceptance is void, the suppression is
                not applied, and implementation halts.
```

The state machine this produces:

```text
D066 and this conditional acceptance are committed
        ↓
upgrade cryptography to 49.0.0
        ↓
rebuild the image, re-prove all four backend bindings,
real JWT round trip, ecdsa absent including after ES256
        ↓
fails or diverges  → HALT. R-2 never becomes effective.
passes             → the condition is satisfied
        ↓
add the recorded --ignore-vuln PYSEC-2026-1325
```

The adjudication happens once, before implementation. The implementer either
satisfies the stated condition or stops, and never acquires discretion to accept
the finding independently.

**Implementation of the suppression**, per D066 rule 3's requirement that the
mechanism be recorded with the acceptance rather than in the decision: a single
`--ignore-vuln PYSEC-2026-1325` flag on the `pip-audit` invocation in
`.github/workflows/ci.yml`, with an inline comment naming H147 R-2 and D066.
`pip-audit 2.10.1` exposes no configuration-file mechanism, so the command-line
flag is the only individual-suppression path available — which is convenient,
since it is also the one that appears in a diff.

**This flag lands last**, after R-1's bump, rebuild and binding re-proof have
all passed.

**Note on scope:** this justification is specific to `ecdsa`. It does **not**
extend to the `cryptography` findings. `GHSA-537c-gmf6-5ccf` concerns OpenSSL
bundled into the wheels and is indifferent to which API the application calls,
so "we only use AESGCM and HMAC" would not justify ignoring it. Those findings
have fixes; R-1 takes them.

**R-3 — Sequencing**

Ownership is kept separate so that H147's definition of Done does not depend on
a different defect:

```text
H147   owns the Python vulnerability resolution — R-1 and R-2
H149   owns the npm gate executing independently
```

The boundary before the next phase is the conjunction, not either alone:

```text
H147 resolved
H149 repaired, or npm audit otherwise actually executed
whole CI green
→ only then Q.5.3a-1
```

A gate that has been red for five weeks cannot tell you whether the next phase
broke something. That is the operative cost, independent of the advisories' own
severity — and it applies to the npm gate too, which nobody has read output from
since 2026-08-02.

**Suggested phase:** Before Q.5.3a-1

---

### H148 — `JWT_ALGORITHM` is an unconstrained string

**Severity:** 🟡
**Status:** Open
**Area:** Configuration boundary / authentication

**Concern:** `JWT_ALGORITHM: str = "HS256"` is a plain string with no validator.
Q.5.3a-0 constrained `ENV` and `EMAIL_BACKEND` to exact value sets that fail at
construction; this setting was not included.

An operator can move authentication onto a different algorithm family —
`ES256`, `RS256`, anything `python-jose` accepts — by setting one environment
variable. There is no startup validation, no allowed-value list, and no check
that the configured algorithm is compatible with the key material actually
supplied. A typo or an incompatible key format becomes a request-time
authentication failure rather than a startup rejection.

The same class of configuration drift D065 rule 2 closed for `ENV`.

**It also interacts with an acceptance.** R-2 accepts `PYSEC-2026-1325` because
the installed `python-jose` dispatch keeps the `ecdsa` backend unreachable — not
because EC algorithms are unused. The inspection established that even an
`ES256` lookup resolves to `CryptographyECKey`.

Changing `JWT_ALGORITHM` to another algorithm family nonetheless widens the
exercised cryptographic surface, which is why it is named as a conservative
re-review trigger — R-2 trigger (b) — rather than because it would reach `ecdsa`
today. An unvalidated setting is a weak foundation for any security position
that depends on which algorithms are in use.

**Fix:** Constrain `JWT_ALGORITHM` to an explicit allowed set validated at
`Settings` construction, following the pattern D065 rule 2 established. Decide
deliberately which algorithms are permitted rather than inheriting whatever the
library accepts.

**Suggested phase:** With or after H147. Does not block restoring the gate.

---

### H149 — A failing Python audit prevents the npm audit from running

**Severity:** 🟡
**Status:** Open
**Area:** CI topology

**Concern:** `Python dependency audit` and `npm dependency audit` are sequential
steps in the same CI job. A non-zero exit from the first leaves the second
skipped.

```text
observed   the npm step has been skipped on every run since df38496,
           2026-08-02 — the CI npm audit result has been unmeasured
           for five weeks
```

Scoped deliberately to the CI gate. Dependabot runs independently and is
configured for this repository, so the frontend's dependency posture is not
wholly unobserved — but the gate that is supposed to fail a build on a
high-severity finding has not run, and nobody has read its output in five weeks.

This is a gate design defect, not a consequence of the vulnerabilities. It
persists after H147 is resolved: any future Python audit failure will silently
disable the npm gate again, and the second failure will be invisible behind the
first.

**Fix:** Make the two audits independent, so each reports its own result and
neither can mask the other — separate jobs, or `continue-on-error` on the first
with an explicit aggregate gate, or `if: always()` on the second. The mechanism
is an implementation choice; the requirement is that one failing audit cannot
hide another.

Consider also that `pip-audit` is installed with `--upgrade` and is therefore
unpinned, so the gate's own tool and its advisory database both float. That is
arguably correct for a security gate — you want the current database — but it
means a run can go red without any repository change, which is what appears to
have happened here.

**Suggested phase:** With or alongside H147. Per R-3, H147 does not own this —
but the npm gate must actually execute before Q.5.3a-1 begins, since nobody
currently knows what it reports.

---

## Rejected alternative with a named reopening condition

Not a backlog entry. A backlog entry asserts that something is defective; no
inspection established that the current query-string contract is exploitable or
unacceptable. What was established is that future proxy, CDN and access-log
behaviour is unprovable from the repository.

**Fragment-based credential transport was considered and not selected for
Q.5.3a.** Moving the emailed link from `?token=` to `#token=` would keep the
credential out of the HTTP request line entirely. Not selected because the
threat it mitigates is unprovable from the repository; because fragment
preservation across the mail clients, security gateways and link-rewriting
infrastructure this product will encounter is unestablished; and because it
would dictate Q.5.3a-2's frontend architecture from a backend decision.

The state machine, recorded so nobody reads this as planned work:

```text
accepted now              query-string transport
mandatory future work     prove the web tier does not persist
                            credential-bearing query strings
conditional decision      reopen the transport choice only if that
                            proof cannot be obtained
```

The proof obligation is recorded in D038's 2026-09-05 amendment as a production
phase requirement. The transport decision is D065 rule 7.

---

## Note on the launch-gate register

The pre-customer security blockers named across D038's amendment and these
entries — production delivery, sending domain and DNS, identifier-scoped rate
limiting, the refresh cookie posture, query-string logging proof, global
security headers, email-case normalisation, production secret management — are
listed here in scattered form only.

**They should be consolidated into a single launch-gate register as its own
artifact, after Q.5.3a-1 ships.** Thirteen blockers spanning DNS, rate
limiting, session posture and secret management are not a subsection of an
email-delivery phase.
