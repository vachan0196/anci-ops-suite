# ForecourtOS / Anci Ops Suite — Hardening Backlog

**Last updated:** 2026-05-11

This backlog tracks commercial SaaS hardening work. Items here are production-readiness work, not customer-facing feature scope.

---

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
**Fix:** Verified the existing SlowAPI limiter is configurable with `RATE_LIMIT_ENABLED`, uses deterministic `429 RATE_LIMIT_EXCEEDED` responses, and protects admin login, employee login, and public site lookup endpoints. Redis-backed distributed limiting remains a future production scaling item.
**Suggested phase:** Phase Q.0

---

### H050 — Secret scanning baseline

**Severity:** 🟡
**Status:** Done
**Area:** Secrets / developer workflow
**Concern:** Commercial development needs a documented way to scan for accidentally committed secrets before production-like deployment.
**Fix:** Added README hardening commands for local `gitleaks detect --source . --log-opts="--all"` usage and added a GitHub Actions gitleaks secret-scan job. No production secrets or `.env` files were added.
**Suggested phase:** Phase Q.0

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
**Fix:** Deferred to Q.2 because adding Next.js Sentry requires new frontend package/configuration and source-map choices. Backend Sentry remains enabled via H048; README documents the future `NEXT_PUBLIC_SENTRY_DSN` convention.
**Suggested phase:** Phase Q.1

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
**Status:** Partially Done
**Area:** Authentication / session management
**Concern:** Browser localStorage access tokens are exposed to XSS and are not production-safe for commercial SaaS authentication.
**Fix:** Phase Q.2 added a backend `auth_sessions` refresh/session foundation with hashed refresh tokens, portal-aware admin/employee sessions, refresh rotation, HTTP-only refresh cookie support, and disabled user/employee/staff-profile blocking. Existing bearer access-token support remains for compatibility. Frontend localStorage token storage remains temporary and must be migrated in the next auth phase.
**Suggested phase:** Phase Q.2

---

### H057 — Refresh token and logout revocation model

**Severity:** 🔴
**Status:** Done
**Area:** Authentication / session management
**Concern:** Login sessions need revocation and refresh-token reuse protection so logout can invalidate server-side session state.
**Fix:** Added `POST /api/v1/auth/refresh` with refresh-token rotation and `POST /api/v1/auth/logout` with refresh/session revocation. Refresh tokens are stored only as hashes, are portal-aware, and revoked refresh tokens cannot be reused.
**Suggested phase:** Phase Q.2

---

### H058 — Frontend auth cookie migration

**Severity:** 🔴
**Status:** Open
**Area:** Authentication / frontend
**Concern:** Admin and employee frontend flows still read/write access tokens from localStorage during the Q.2 compatibility window.
**Fix:** Implement D036 in Q.3.1. Migrate frontend auth calls to use the Q.2 refresh/session foundation and HTTP-only cookie flow. Frontend auth must no longer actively depend on localStorage access tokens; legacy localStorage keys `forecourt_access_token` and `forecourt_employee_access_token` must be cleared; stale key `employee_access_token` must not be used as an active key; refresh must use `credentials: "include"`; access tokens must be in-memory only; the required CSRF header must be included where required; logout must revoke the server-side session and clear the cookie; admin and employee flows must both work.
**Suggested phase:** Phase Q.3

---

### H064 — Supply chain hardening against slopsquat / hallucinated packages

**Severity:** 🟡
**Status:** Partially Done
**Area:** Supply chain security
**Concern:** AI-assisted development can introduce hallucinated package names that attackers register on PyPI/npm with malicious code. Dependabot and gitleaks do not fully protect against this attack vector.
**Fix:** Added a durable dependency verification policy, README supply-chain baseline checks, GitHub Dependency Review for pull requests, `pip-audit` for API requirements, and high-severity `npm audit` for frontend dependencies. Lockfile/hash-based Python installs and dependency approval automation remain future hardening work.
**Suggested phase:** Phase Q.2.2

---

### H061 — CSRF protection for cookie-based session model

**Severity:** 🔴
**Status:** Open
**Area:** Authentication / browser session security
**Concern:** Once the frontend uses the HTTP-only refresh cookie, CSRF becomes an active risk unless protected.
**Fix:** Implement the D036 strategy in Q.3.1: SameSite=Strict refresh cookie plus required custom request header `X-Requested-With: ForecourtOS` for cookie-backed browser auth requests, including refresh. Keep the strategy consistent for Admin Portal and Employee Portal.
**Suggested phase:** Q.3.0/Q.3.1
**Blocking:** Q.3 frontend cookie migration must not ship without CSRF protection.

---

### H067 — All-sessions logout / logout-all endpoint

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / session management
**Concern:** D036 chooses single-session logout for Q.3.1, but commercial account security will need a way to revoke all sessions for an admin or employee identity after suspected compromise or device loss.
**Fix:** Add an audited all-sessions logout capability in a later auth hardening phase. It should revoke all active refresh sessions for the authenticated identity and preserve portal-aware admin/employee boundaries.
**Suggested phase:** Q.4 or later dedicated auth hardening phase.

---

### H068 — Same-origin deployment/session routing validation

**Severity:** 🟡
**Status:** Open
**Area:** Deployment / session security
**Concern:** D036 chooses same-origin MVP production deployment with the API path-proxied under the app origin where practical. Deployment configuration must be validated so cookie Domain omission, SameSite=Strict, CSRF headers, and credentialed refresh work in production-like environments.
**Fix:** Validate staging/production routing for `https://app.forecourtos.com`, host-only refresh cookies, narrow local/staging CORS exceptions, and Admin Portal / Employee Portal session restoration before production launch.
**Suggested phase:** Q.3.1 or deployment hardening before production.

---

### H069 — Bearer-token deprecation/removal after migration

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / session migration
**Concern:** D036 keeps bearer-token compatibility temporarily after Q.3.1, but localStorage bearer-token browser usage must not become permanent.
**Fix:** After Q.3.1 ships, follow the D036 timeline: start deprecation warnings for legacy bearer-only browser usage at 30 days, stop issuing/using bearer tokens in normal frontend browser flows at 60 days, and remove or restrict legacy browser bearer compatibility at 90 days.
**Suggested phase:** Post-Q.3.1 auth hardening.

---

### H065 — Audit logging for auth/session events

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / auditability / incident response
**Concern:** Refresh issued, rotated, revoked, and rejected events are not clearly audit-logged. For a UK GDPR-aware commercial SaaS, incident investigation needs durable records of session lifecycle events.
**Fix:** Add audit log entries for refresh/session issue, rotation, logout revocation, invalid/revoked/expired/wrong-portal refresh attempts, and disabled-user/session blocking where practical. Include portal, user_id or employee_account_id, session identifier where safe, and rejection reason. Do not log raw tokens.
**Suggested phase:** Q.3 or Q.4 depending on scope.

---

### H066 — Refresh token reuse detection / session family pattern

**Severity:** 🟡
**Status:** Open
**Area:** Authentication / session compromise detection
**Concern:** Refresh rotation exists, but reuse detection is not yet implemented. If an already-rotated refresh token is reused, that can indicate token theft.
**Fix:** Add a session family model or equivalent tracking. On reuse of a rotated/revoked refresh token, revoke the related session family where safe and audit log the event.
**Suggested phase:** Q.3 or later dedicated auth hardening phase.
