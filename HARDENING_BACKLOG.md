# HARDENING_BACKLOG.md — ForecourtOS / Anci Ops Suite

**Last updated:** 2026-05-18

## Purpose

This file tracks commercial SaaS hardening work required before and after first paying customer onboarding.

ForecourtOS is a real multi-tenant commercial SaaS product. It handles employee data, rota decisions, future billing, and future AI-assisted workflows. Hardening work must be treated as product-critical, not optional cleanup.

## Severity Legend

- 🔴 Critical / launch-blocking
- 🟡 Important / near-term hardening
- 🟢 Later / scale or maturity improvement

## Current Focus

Phase Q.5 — Owner and sensitive-action 2FA

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
**Status:** Open
**Area:** Authentication / sensitive action protection
**Concern:** Owner-only areas such as payroll, billing, compliance documents, destructive actions, and tenant-level settings require stronger protection before commercial launch.
**Fix:** Add 2FA baseline for Owner login and/or sensitive action re-authentication, with audit logging and recovery rules. Phase Q.4.4 resolved the prerequisite Owner/Admin role split. D039 records the Q.5 design. Q.5.1 implemented the backend TOTP enrolment, login challenge verification, encrypted TOTP secret storage, and recovery-code use loop. Q.5.1b added rate-limited disable 2FA and recovery-code regeneration endpoints with recovery-code consumption, old-code invalidation, and safe auth security events. Q.5.2a added the server-side step-up mechanism and wired it to store deactivation. H060 remains open/partial until the sensitive-action gate is rolled across the remaining existing sensitive endpoints.
**Suggested phase:** Phase Q.5.2b
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
**Status:** Open
**Area:** Authentication / email verification / sensitive action protection
**Concern:** D038 allows unverified admin users to log in for now, but future sensitive actions should require verified admin email before commercial launch. Without this, an unverified email account may access sensitive Owner/Admin actions.
**Fix:** Add backend enforcement so unverified admin users are blocked from sensitive actions such as billing, payroll, compliance documents, staff profile changes, tenant/site settings, exports, destructive actions, role/permission changes, and other Owner-only governance actions. Per D039, combine this with the Q.5.2 sensitive-action gate so email verification, enrolled 2FA where required, and recent step-up state are enforced through one path. Q.5.2a applied the gate to store deactivation only, so H073 remains open/partial until Q.5.2b applies the reusable dependency to the remaining existing sensitive endpoints.
**Suggested phase:** Phase Q.5.2b

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
