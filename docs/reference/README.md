# Reference Documents — NOT Source of Truth

The files in this folder are reference material only. None of them is authoritative.
Where anything here disagrees with the repository, the repository is correct.

## Authority order

From `docs/HANDOVER.md`, lowest item added by this folder:

```text
IMPLEMENTATION_STATUS.md
DECISIONS.md
HARDENING_BACKLOG.md
README.md
current code, schemas, routes, tests, OpenAPI
task-specific contracts and older PRDs
docs/reference/  (this folder — lowest)
```

## What these are

- `forecourt_os_database_schema_prd_v1.md`
- `forecourt_os_technical_architecture_prd_v1.md`
- `phase17_employee_api_contract.md`

All three were written in April/May 2026. They describe intended design at the time
of writing, not current implementation. The codebase has moved on from them in
places that matter.

## Known stale, not in this folder

Two related documents are **not copied here** because they are confirmed stale, but
the divergence is worth flagging so it isn't rediscovered at cost:

- `forecourt_os_api_contracts_v1.md` documents a site-scoped
  `/api/v1/sites/{site_id}/rota/generate-week`. The live route is flat:
  `POST /api/v1/rota/generate-week`.
- `forecourt_os_frontend_pages_prd_v1.md` claims readiness blocks rota generation.
  `generate_week_shifts` has no readiness check.

Both were confirmed stale during CoverageUI.2. Neither has been copied into this
repository.

## Rule for AI agents

Never cite anything in this folder as justification for an implementation choice
without verifying against current code first. If this folder and the code
disagree, the code wins, always.
