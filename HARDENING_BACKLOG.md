# ForecourtOS / Anci Ops Suite — Hardening Backlog

**Last updated:** 2026-05-07

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
**Fix:** Migrate frontend auth calls to use the Q.2 refresh/session foundation and HTTP-only cookie flow, then remove `forecourt_access_token` and `forecourt_employee_access_token` localStorage dependencies.
**Suggested phase:** Phase Q.3
