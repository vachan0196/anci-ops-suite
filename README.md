# Anci Ops Suite

Anci Ops Suite is being built as a commercial, multi-tenant SaaS operations product for forecourt and convenience retail teams. Documentation and implementation should be treated as production-oriented source of truth, not portfolio/prototype scaffolding.

## Project source-of-truth files

Before modifying this project, read:

1. `IMPLEMENTATION_STATUS.md` — current implementation reality and completed phases.
2. `DECISIONS.md` — deliberate product/technical decisions and PRD divergences.
3. `HARDENING_BACKLOG.md` — commercial SaaS hardening roadmap and open security follow-ups.
4. `README.md` — local run commands and current navigation.

PRD files describe the target product direction, but current implementation truth comes first.

## Resuming active work

After reading the authoritative source-of-truth documents, read:

- `docs/HANDOVER.md` — the latest working-session checkpoint, immediate next step, unresolved context, and relevant operational gotchas.
- `docs/AI_WORKFLOW.md` — durable AI collaboration and engineering practice.

The handover is non-authoritative and valid only at the commit recorded inside it. Always verify repository state and inspect the relevant code before making changes.

---
## Phase status

| Phase | Scope | Status |
|---|---|---|
| Phase K.2 | Employee login polish/site code lookup | Done |
| Phase L | Employee availability foundation | Done |
| Phase M | Employee request workflows foundation | Done |
| Phase N | Admin request approval queue | Done |
| Phase O | Approved leave request rota application | Done |
| Phase P.0 | Swap/cover workflow scoping + decisions | Done |
| Phase P.1 | Employee-safe same-site target list | Done |
| Phase P.2 | Target accept/decline workflow | Done |
| Phase P.3 | Cover approval rota application | Done |
| Phase P.4 | Swap target-shift modelling foundation | Done |
| Phase P.5 | Swap approval rota application | Done |
| Phase Q.0 | Commercial SaaS hardening baseline | Done |
| Phase Q.1 | CI/CD and observability hardening | ✅ Done |
| Phase Q.2 | Authentication/session hardening foundation | ✅ Done |
| Phase Q.2.1 | Auth session test + documentation hardening | ✅ Done |
| Phase Q.2.2 | Supply chain/slopsquat hardening | ✅ Done |
| Phase Q.3.0 | Frontend auth cookie/session + CSRF design/scoping | ✅ Done |
| Phase Q.3.1 | Implement frontend cookie/session migration + CSRF protection | ✅ Done |
| Phase Q.3.2 | Auth/security event audit storage design | ✅ Done |
| Phase Q.3.2.1 | Auth/session audit logging with dedicated auth security events storage | ✅ Done |
| Phase Q.3.3 | Refresh-token reuse detection / session family hardening | ✅ Done |
| Phase Q.4.0 | Email/auth token infrastructure design | ✅ Done |
| Phase Q.4.1 | Email service abstraction + local/test email backend | ✅ Done |
| Phase Q.4.2 | Admin password reset backend | ✅ Done |
| Phase Q.4.3 | Admin email verification backend | ✅ Done |
| Phase Q.4.4 | Owner/Admin role split | ✅ Done |
| Phase Q.5.0 | 2FA design decisions | ✅ Done |
| Phase Q.5.1 | TOTP enrolment + login verification + recovery codes backend | ✅ Done |
| Phase Q.5.1a | 2FA verify rate limiting | ✅ Done |
| Phase Q.5.1b | Disable 2FA + regenerate recovery codes backend | ✅ Done |
| Phase Q.5.1c | Auth test runtime profiling + full regression gate | ✅ Done |
| Phase Q.5.2a | Step-up auth mechanism + store deactivation gate | ✅ Done |
| Phase Q.5.2b | Docs-only sensitive-action rollout inspection close-out | ✅ Done |
| Phase R.0 | Frontend company profile real API migration | ✅ Done |
| Phase R.1 | Site setup localStorage cleanup / backend persistence alignment | ✅ Done |
| Phase R.2d | Block member admin portal access | ✅ Done |
| Phase T.0 | Tenant isolation + role boundary security gate | ✅ Done |
| Phase T.1 | Reconciled permission matrix current truth | ✅ Done |
| Phase T.2a | Store lifecycle PATCH bypass fix | ✅ Done |
| Phase T.2 | Matrix-backed role-boundary tests | ✅ Done |
| Phase UX.1 | Admin sites list and edit UI | ✅ Done |
| Phase UX.2 | Staff creation for existing sites | ✅ Done |
| Phase Staff.2 | Staff pay/RTW read-model hardening | ✅ Done |
| Phase Staff.2b | Staff pay/RTW write hardening | ✅ Done |
| Phase Staff.1 | Safe staff profile view/edit UI | ✅ Done |
| Phase Rota.1 | Multi-site admin rota selector/read-side stabilisation | ✅ Done |
| Phase RecommendationUI.1 | Admin recommendation draft display | ✅ Done |
| Phase RecommendationUI.2 | Apply recommendation draft to weekly rota grid | ✅ Done |
| Phase RecommendationUI.3 | In-app discard and regenerate for recommendation drafts | ✅ Done |
| Phase Coverage.1a | Work areas, generation provenance, and safe regeneration backend | ✅ Done |
| Phase CoverageUI.1 | Coverage rules and optional work-area configuration UI | ✅ Done |
| Phase CoverageUI.2 | Generate Week wired into the Weekly rota surface | ✅ Done |
| Phase Availability.1a | Timed declared availability semantics (backend) | ✅ Done |
| Docs.1 | Owner-only sensitive staff data decision recorded | ✅ Done |
| Docs.2 | Implementation status updated through staff hardening | ✅ Done |
| Docs.3 | Hardening backlog updated after staff sensitive data hardening | ✅ Done |
| Docs.4 | README updated through staff hardening | ✅ Done |

---
## 🧠 Current Focus

Current completed product/security work:

```text
Staff.2  — Staff pay/RTW read-model hardening
Staff.2b — Staff pay/RTW write hardening
Staff.1  — Safe staff profile view/edit UI
Rota.1   — Multi-site admin rota selector/read-side stabilisation
RecommendationUI.1 — Admin recommendation draft display
RecommendationUI.2 — Apply recommendation draft to weekly rota grid
RecommendationUI.3 — In-app discard and regenerate for recommendation drafts
Docs.1   — Owner-only sensitive staff data decision recorded
Docs.2   — Implementation status updated through staff hardening
Docs.3   — Hardening backlog updated after staff sensitive data hardening
Docs.4   — README updated through staff hardening
```

Current rota UI truth:

```text
/admin/rota uses the existing /api/v1/sites/{site_id} rota route family.
The site selector is sourced from GET /api/v1/stores via listStores.
The initial selection is the first active site, preserving previous behaviour.
Changing site refetches that site's weekly rota, readiness, and safe staff directory.
Selection is component state only; no localStorage is used.
Recommendation drafts are self-service in the admin rota UI:
generate -> discard/regenerate -> apply -> publish.
Apply and publish remain separate explicit steps.
Regenerate currently uses discard -> create -> load because the public create schema does not expose atomic replacement.
Rota.2 remains a future editor-focused phase.
```

Current coverage-generation truth:

```text
Work areas are site-scoped operational tags, separate from required_role and recommendation matching.
Coverage templates and work areas soft-deactivate so generated-shift lineage remains intact.
Generate Week is safely repeatable: untouched generated shifts are soft-superseded and recreated,
while assigned, published, overridden, manual, and legacy_untracked shifts are preserved.
Preserved manual and legacy_untracked shifts do not satisfy template headcount.
Each generated shift records its generation run, source template, and work area.
Regeneration atomically discards the active recommendation snapshot for the same site/week,
but does not recreate it; H091 remains open.
PostgreSQL generation concurrency is protected by a deterministic transaction advisory lock plus row locks.
SQLite tests do not prove that PostgreSQL concurrency boundary.
```

Current CoverageUI status:



```text

CoverageUI.1 is complete, verified, and committed as 2cd98c4.

Coverage rules share the Weekly rota selected-store state and support multi-day creation, lifecycle actions,

optional work areas, partial retry, historical label resolution, and a responsive mobile coverage layout.

Inactive work areas are read-only historical records because the public API does not support reactivation.

CoverageUI.2 is complete, verified, and committed as 421fc82.

Generate Week is wired into the Weekly rota surface and calls POST /api/v1/rota/generate-week with store_id and week_start.

The UI reports backend reconciliation counts verbatim and applies no derived classification of kept shifts.

Confirmation, result, and error state are scoped to the store and week that produced them.

Generation and rota refresh are separate outcomes; a failed refresh never reports generation as failed.

Availability.1a is complete. Availability.1b is next.

H096 (work-area reactivation lifecycle) and H097 (Weekly rota mobile layout) are deferred follow-ups.

```
Current staff sensitive-data rule:

```
Owner can read/write staff pay and RTW fields.
Admin/non-owner staff read responses omit pay/RTW fields.
Admin/non-owner writes of non-null pay/RTW fields are rejected.
Explicit non-owner null pay/RTW fields are stripped and cannot clear Owner-set values.
```

Sensitive staff fields currently protected in admin staff APIs:

```
hourly_rate
pay_type
rtw_status
```

Normal staff edit UI must use safe-fields-only payloads.

Staff.1 safe staff profile editing is complete at:

```
/admin/staff/[staffId]
```

Staff.1 uses `GET /api/v1/staff/{staff_id}` for edit pre-fill and `PATCH /api/v1/staff/{staff_id}` for saving. It does not use `/api/v1/staff/directory` for edit pre-fill.

Staff.1 safe editable fields:

```
job_title
phone
emergency_contact_name
emergency_contact_phone
contract_type
notes
```

The notes field warns users:

```
Do not store NI numbers, right-to-work document details, passport/BRP/share-code details, medical information, payroll-sensitive data, or other sensitive personal data in notes.
```

Do not add these into normal safe staff edit UI:

```
is_active
deactivate
reactivate
archive
delete
hourly_rate
pay_type
rtw_status
NI number
passport number
BRP/share-code documents
document upload
base hours threshold
overtime rate
weekly hour cap
payroll rules
display_name
```

`display_name` editing remains deliberately deferred because of linked user/staff identity name-authority questions. Staff lifecycle remains separate. Pay/RTW remains a future Owner-only UI with step-up/audit where applicable.

Scheduling times are site-local wall-clock. Timestamps in `TIMESTAMP WITH TIME ZONE`
columns carry a `+00:00` label that is storage notation, not a conversion. Do not introduce
timezone conversion into coverage templates, shifts, or availability. See D054.

Current source-of-truth files:

```
IMPLEMENTATION_STATUS.md
DECISIONS.md
HARDENING_BACKLOG.md
apps/api/docs/forecourt_os_permission_matrix_current_v1.md
```
Next recommended phases:
- Availability.1b — Employee-facing `preferred_off` surface. Availability.1 is not complete until it lands.
- Staff.1L — Staff deactivate/reactivate lifecycle design.
- H083 — Owner-only staff pay/RTW UI with step-up and audit, when prioritised.

---
## Commercial SaaS Standard

- Backend is the source of truth for tenant/site isolation, RBAC, workflow state, and rota mutation.
- Employee/admin token separation, deterministic errors, audit logging, and safe response shapes are production requirements.
- Browser-only/localStorage behavior is not acceptable as production persistence for commercial workflows.
- Prototype or temporary PRD drift must be documented in `DECISIONS.md` and resolved before commercial rollout.

---
## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `JWT_SECRET_KEY` | Yes in production | Signs API access tokens; local default is development-only. |
| `JWT_ALGORITHM` | No | JWT signing algorithm; defaults to `HS256`. |
| `BCRYPT_TEST_FAST` | No | Test-only bcrypt speed flag; defaults to `false`, preserving production bcrypt cost. Pytest sets this explicitly to `true`; do not enable in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token lifetime; defaults to `15`. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh/session token lifetime; defaults to `14`. |
| `AUTH_REFRESH_COOKIE_NAME` | No | HTTP-only refresh cookie name; defaults to `forecourt_refresh_token`. |
| `APP_BASE_URL` | No | Frontend/app base URL used for generated password reset links; defaults to `http://localhost:3000`. |
| `EMAIL_BACKEND` | No | Internal email backend selector; allowed Q.4.1 values are `local_log` and `test_capture`, defaults to `local_log`. |
| `RATE_LIMIT_ENABLED` | No | Production defaults to `true`; the test bootstrap sets it to `false` before importing the application, and the Compose `api` service does not inject a value. |
| `RATE_LIMIT_PASSWORD_RESET_REQUEST` | No | SlowAPI route/IP-level password reset request limit; defaults to `10/hour`. The D038 3-per-email target is deferred to H071. |
| `RATE_LIMIT_PASSWORD_RESET_CONFIRM` | No | SlowAPI route/IP-level password reset confirmation limit; defaults to `10/hour`. |
| `RATE_LIMIT_EMAIL_VERIFICATION_REQUEST` | No | SlowAPI route/IP-level email verification request limit; defaults to `10/hour`. The D038 3-per-user target is deferred to H074. |
| `RATE_LIMIT_EMAIL_VERIFICATION_CONFIRM` | No | SlowAPI route/IP-level email verification confirmation limit; defaults to `10/hour`. |
| `RATE_LIMIT_2FA_VERIFY` | No | SlowAPI route/IP-level 2FA challenge verification limit; defaults to `5/minute`. |
| `RATE_LIMIT_2FA_STEP_UP` | No | SlowAPI route/IP-level 2FA step-up verification limit; defaults to `5/minute`. |
| `RATE_LIMIT_2FA_DISABLE` | No | SlowAPI route/IP-level 2FA disable limit; defaults to `5/minute`. |
| `RATE_LIMIT_2FA_RECOVERY_REGEN` | No | SlowAPI route/IP-level recovery-code regeneration limit; defaults to `5/minute`. |
| `TWO_FACTOR_STEP_UP_TTL_MINUTES` | No | Server-side step-up freshness TTL for sensitive actions; defaults to `5`. |
| `TOTP_ENCRYPTION_KEY` | Yes for TOTP enrolment/verification | Base64-encoded 32-byte AES-GCM key for encrypted TOTP secret storage. Never commit real TOTP encryption keys, never reuse `JWT_SECRET_KEY`, and use only placeholders in docs, for example `TOTP_ENCRYPTION_KEY=replace-with-generated-production-secret`. |
| `SENTRY_DSN` | No | Enables backend Sentry error tracking when configured. |
| `SENTRY_ENVIRONMENT` | No | Overrides the Sentry environment label; falls back to `ENV`. |
| `SENTRY_TRACES_SAMPLE_RATE` | No | Optional Sentry trace sample rate; defaults to `0.0`. |
| `NEXT_PUBLIC_SENTRY_DSN` | No | Reserved for optional frontend Sentry setup; frontend Sentry is deferred after Q.1. |

---
## Commercial Hardening Checks

Run before production-like deployment:

```bash
# Secret scan, if gitleaks is installed
gitleaks detect --source . --log-opts="--all"

# Backend migration check
docker compose -f infra/docker-compose.yml run --rm api sh -lc "alembic -c apps/api/alembic.ini upgrade head"

# Backend tests
docker compose -f infra/docker-compose.yml run --rm api sh -lc "PYTHONPATH=/app pytest apps/api/tests/ -q"

# Python known-vulnerability audit
pip-audit -r apps/api/requirements.txt

# Frontend checks
cd apps/web
npm run build
npx tsc --noEmit

# npm known-vulnerability audit
npm audit --audit-level=high
cd ../..

# Review dependency and workflow changes before commit
git diff -- apps/api/requirements.txt apps/web/package.json apps/web/package-lock.json .github/workflows
```

These are baseline controls for known vulnerabilities and dependency review. They do not fully prevent typosquatting or slopsquatting; new dependencies still require manual verification against official registries and project documentation before merge.

---
## CI/CD Baseline

GitHub Actions runs:

- Backend Docker build
- Alembic migration check
- Backend pytest suite
- Frontend build
- TypeScript check
- Secret scanning
- Dependency Review on pull requests
- Python dependency audit with `pip-audit`
- npm high-severity dependency audit

Production deployment is not automated yet.

---
## Observability

Backend Sentry is optional and enabled with:

```text
SENTRY_DSN
```

Frontend Sentry, when configured in a future phase, should use:

```text
NEXT_PUBLIC_SENTRY_DSN
```

Sensitive values such as auth headers, cookies, passwords, tokens, and secret-like fields must be redacted.

API responses include `X-Request-ID` for request correlation, and incoming `X-Request-ID` values are propagated when provided.

---
## How to run locally

1. Start the stack (API + Postgres):

```bash
docker compose -f infra/docker-compose.yml up --build
```

2. Run migrations (in another terminal, from repo root):

```bash
docker compose -f infra/docker-compose.yml run --rm api alembic -c apps/api/alembic.ini upgrade head
```

The API is available at `http://localhost:8000`.

Run the full backend test directory in Docker:

```bash
docker compose -f infra/docker-compose.yml run --rm api sh -lc 'PYTHONPATH=/app pytest apps/api/tests/ -q'
```

The test bootstrap defaults `RATE_LIMIT_ENABLED` to `false` before importing the
application. The normal Compose `api` service does not inject this setting, so
production-like application processes retain the backend default of `true`.
Pass `-e RATE_LIMIT_ENABLED=true` explicitly when exercising rate-limit
behaviour.

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Hot food forecast (stub):

```bash
curl "http://localhost:8000/api/v1/hot-food/forecast?store_id=store-001&horizon_days=7"
```

## Migrations

Run latest migrations locally (without Docker, defaults to sqlite if `DATABASE_URL` is unset):

```bash
alembic -c apps/api/alembic.ini upgrade head
```

Create a new migration:

```bash
alembic -c apps/api/alembic.ini revision -m "your migration message"
```

## Reset dev database

Reset Postgres dev data:

```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up --build -d
docker compose -f infra/docker-compose.yml run --rm api alembic -c apps/api/alembic.ini upgrade head
```

Reset local sqlite fallback:

```bash
rm -f dev.db
alembic -c apps/api/alembic.ini upgrade head
```
