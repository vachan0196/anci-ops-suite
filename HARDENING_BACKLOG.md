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
**Fix:** Added README hardening commands for local `gitleaks detect --source . --log-opts="--all"` usage. No production secrets or `.env` files were added.
**Suggested phase:** Phase Q.0

---

### H051 — Minimal CI hardening gate

**Severity:** 🟡
**Status:** Deferred
**Area:** CI/CD / release safety
**Concern:** A commercial SaaS should run backend tests, migrations, frontend checks, and secret scanning automatically before merge/deployment.
**Fix:** Deferred because this repo currently has no `.github` workflow baseline, and adding a credible full gate should be done with branch/runner expectations confirmed. README now documents equivalent local hardening commands.
**Suggested phase:** Phase Q.0

---

### H052 — Phase 17 P.5 contract cleanup

**Severity:** 🟡
**Status:** Done
**Area:** API contract / documentation truth
**Concern:** Phase 17 API contract summaries must reflect that target-accepted swap approval now exchanges both shift assignments.
**Fix:** Verified and kept the Phase 17 summary at Implemented Through Phase P.5, Planned After Phase P.5, and removed completed swap rota update omission.
**Suggested phase:** Phase Q.0
