# Anci Ops Suite

Anci Ops Suite is being built as a commercial, multi-tenant SaaS operations product for forecourt and convenience retail teams. Documentation and implementation should be treated as production-oriented source of truth, not portfolio/prototype scaffolding.

## Project source-of-truth files

Before modifying this project, read:

1. `IMPLEMENTATION_STATUS.md` — current implementation reality and completed phases.
2. `DECISIONS.md` — deliberate product/technical decisions and PRD divergences.
3. `README.md` — local run commands.

PRD files describe the target product direction, but current implementation truth comes first.

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
| Phase Q.3.1 | Implement frontend cookie/session migration + CSRF protection | 🔜 Next |

---
## Current Focus

We are currently working on:

👉 Phase Q.3.0 complete: frontend cookie/session and CSRF decisions are captured in D036  
👉 D036 locks the CSRF strategy, cookie attributes, in-memory access-token storage, bearer-token deprecation timeline, localStorage migration, refresh-on-401 behaviour, logout scope, and same-origin deployment target  
👉 Next: Phase Q.3.1 — implement frontend cookie/session migration and CSRF protection

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
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token lifetime; defaults to `15`. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh/session token lifetime; defaults to `14`. |
| `AUTH_REFRESH_COOKIE_NAME` | No | HTTP-only refresh cookie name; defaults to `forecourt_refresh_token`. |
| `RATE_LIMIT_ENABLED` | No | Enables API rate limiting when `true`; tests normally set this to `false`. |
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
docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc "PYTHONPATH=/app pytest -q"

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

Run tests in Docker with rate limiting disabled:

```bash
docker compose -f infra/docker-compose.yml run --rm -e RATE_LIMIT_ENABLED=false api sh -lc 'PYTHONPATH=/app pytest -q'
```

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
