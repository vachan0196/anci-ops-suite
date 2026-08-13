# AGENTS.md

Rules for Codex when implementing in this repository.

## Role

Codex implements. Codex does not review its own instructions and does not decide
product or architectural questions. Those arrive already settled in the phase
prompt.

## Never

- Never commit. Never push. Vachan reviews via `git show` and commits.
- Never self-resolve a divergence between documentation and code. Halt and
  report.
- Never change production behaviour merely to silence an unexpected failing
  test. If a test exposes behaviour conflicting with the settled phase contract,
  implement the authorised change. If the phase did not authorise it, halt and
  report.
- Never weaken or bypass a validation guard to make a phase succeed, unless the
  phase prompt explicitly carries an adjudicated decision changing that rule.
- Never use `create_all`. Alembic migrations only.

## Always

- Preserve tenant isolation, site isolation, RBAC, and audit logging.
- Derive test dates from `date.today()`. Absolute calendar dates are prohibited
  in new or modified tests. See H098.
- Run `git add -N <path>` for new untracked files before reporting, so their
  contents are visible to `git diff`.
- After backend changes, rebuild the API before browser verification.
- Before capturing a backend baseline that depends on the current API image,
  rebuild first, so the baseline cannot come from a stale image:
  `docker compose -f infra/docker-compose.yml up -d --build --force-recreate api`

## Authority

Documentary authority:
IMPLEMENTATION_STATUS.md > DECISIONS.md > HARDENING_BACKLOG.md > README.md >
docs/reference/ (lowest).

Current code, schemas, routes, tests, and OpenAPI are implementation evidence
and must always be inspected for the phase.

If current implementation conflicts with an authoritative document, do not
choose one based on this ordering. Halt and report the divergence.

Do not consult forecourt_os_api_contracts_v1.md or
forecourt_os_frontend_pages_prd_v1.md. Both are stale and not in this checkout.

## Domain boundaries

Do not infer or reinvent pay, hours, identity, RBAC, or sensitive-data
boundaries. Read the current relevant entries in DECISIONS.md and the current
permission source of truth before changing those areas.
