# HARDENING_BACKLOG.md — ForecourtOS / Anci Ops Suite

**Last updated:** 2026-07-20

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
**Status:** Done
**Area:** Authentication / account recovery
**Concern:** Admin users need a secure password reset flow before production onboarding.
**Fix:** Phase Q.4.2 added the admin-side password reset backend with generic request responses, hashed single-use `password_reset` tokens, 1-hour expiry, atomic token consumption, safe rejection classification, Q.4.1 email service usage, and active admin session revocation after successful reset.
**Suggested phase:** Phase Q.4

---

### H059 — Email verification for admin-side accounts

**Severity:** 🟡
**Status:** Done
**Area:** Authentication / onboarding security
**Concern:** Owner/Admin accounts should verify email ownership before production use, especially before billing and sensitive access.
**Fix:** Phase Q.4.3 added the admin-side email verification backend foundation with `users.email_verified_at`, authenticated request/resend, public confirm, hashed single-use `email_verification` tokens, 24-hour expiry, atomic token consumption, safe rejection classification, already-verified handling, Q.4.1 email service usage, and safe auth security events. Per D038, unverified admin users can still log in; sensitive-action enforcement remains deferred to H073.
**Suggested phase:** Phase Q.4

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