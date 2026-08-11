# Project Handover

**Valid at implementation commit:** `421fc82`
**Branch:** `main`
**Date:** 2026-08-10
**Working tree:** clean
**Remote:** synced with `origin/main`

## Purpose and authority

This is a continuation checkpoint, not a source of truth. It records where active work
stopped, what happens next, and what the next session should inspect first.

It is **non-authoritative**. If repository HEAD differs from the commit above, verify the
repository before relying on anything here.

Authority order:

```text
IMPLEMENTATION_STATUS.md
DECISIONS.md
HARDENING_BACKLOG.md
README.md
current code, schemas, routes, tests, OpenAPI
task-specific contracts and older PRDs
```

This document references those. It does not restate them. Durable engineering practice
lives in `docs/AI_WORKFLOW.md`.

## Repository checkpoint

```text
e344ecf fix(tests): make employee portal test dates relative to today
6ebf321 docs: add latest commit to handover log block
678204c docs: correct handover self-reference to its own commit
f45b49a docs: refresh handover for CoverageUI.2 completion and Availability.1
888e867 docs: record CoverageUI.2 completion in README and correct dates
d820c24 docs: record CoverageUI.2 and close CoverageUI.1 retest
421fc82 feat: wire Generate Week into the rota workflow
df38496 docs: add shared project handover and AI workflow practice
```

No uncommitted work. Nothing pending review.

## What just completed: CoverageUI.2

Generate Week is wired into the Weekly rota surface. The control calls
`POST /api/v1/rota/generate-week` with exactly `store_id` and `week_start`, reports the
backend reconciliation counts verbatim, and applies no derived classification.

Full detail is in `IMPLEMENTATION_STATUS.md`. Not restated here.

CoverageUI.1's outstanding post-correction browser retest is also closed. Inactive work
areas were confirmed as read-only historical records with no rename, deactivate, or
reactivate action, and not selectable for new rules.

The end-to-end customer workflow was verified in the same session: coverage rules,
Generate Week, generate recommendations against real availability, apply, publish. Site
isolation held across separate per-site rule sets.

## Corrections learned during CoverageUI.2

These cost real time. Do not repeat them.

- **The previous handover pointed at the wrong component.** It described the Generate
  Week button as being in the Coverage rules workflow. The button was in
  `admin-shell.tsx`. `coverage-rules.tsx` line 667 mentions "Generate Week" only as
  descriptive prose inside a paragraph. A grep for the control, not the phrase, would
  have caught this immediately.
- **Two PRDs are stale and are not in the repository checkout.**
  `forecourt_os_api_contracts_v1.md` documents a site-scoped
  `/api/v1/sites/{site_id}/rota/generate-week`; the live route is flat.
  `forecourt_os_frontend_pages_prd_v1.md` states readiness blocks generation; the backend
  has no readiness dependency or check. Both files exist only in AI project knowledge, not
  in the repo, so Codex cannot read them. Do not instruct Codex to consult them.
- **Stale AI project knowledge produced two false findings.** Uploaded copies of
  `HARDENING_BACKLOG.md` and `README.md` were sourced from a duplicate Windows-side
  folder rather than the WSL repository. Upload from
  `\\wsl.localhost\Ubuntu\home\vachan\code\anci-ops-suite` only. Replace existing project
  knowledge entries rather than adding alongside them.

## Immediate next phase: H088a

Availability date/timezone convention documentation and full-day boundary tests. A
prerequisite for Availability.1: H088's own fix text names "before introducing timed
windows".

## Then: Availability.1

Timed employee availability.

### Verified by inspection on 2026-08-10

- `availability_entries` already has nullable `start_time`/`end_time` and NULL-safe partial
  unique indexes for both full-day and timed rows. **No migration is required.**
- `_availability_covers_shift` is duplicated **byte-identically** in
  `apps/api/routers/shifts.py:175` and `apps/api/routers/rota_recommendations.py:216`,
  along with `_AVAILABLE_TYPES`. Consolidation into one shared helper is safe and is
  recommended inside Availability.1, so timed windows are not judged by two unreconciled
  copies.
- The site-local-as-UTC convention is uniform across all three writers: the generator
  (`datetime.combine(..., tzinfo=timezone.utc)` on a local template `TIME`), the frontend
  (`Date.UTC(...)` / `getUTCHours()`), and availability `Time` values. No BST defect. The
  convention is correct but undocumented — that is what H088a records.

### Undecided rules the helper already encodes

Not defects; product rules nobody has ruled on. Decide and write into D048 during
Availability.1:

- **Full containment required.** Available 09:00-17:00 does not cover an 08:00-16:00
  shift. Partial overlap is not availability.
- **Overnight shifts match full-day rows only.** Timed entries are skipped when a shift
  crosses midnight. This collides directly with Coverage.1b.
- **Contradictory rows are inert, not decisive.** Both query paths filter
  `type.in_(_AVAILABLE_TYPES)`, so an `unavailable` row is never fetched. "No row" and
  "explicit unavailable" are identical to the engine. Replace-week masks this today; a grid
  UI would expose it.

### Locked decisions that govern this phase

Read `DECISIONS.md` before drafting. D048 in particular: availability is person-scoped on
`user_id`, and admin replace-week is authoritative and overwrites employee-set rows.

## After Availability.1

Not yet scheduled, in no fixed order:

- **Coverage.1b** — overnight coverage. Template validation rejects
  `end_time <= start_time`, so 24-hour sites cannot express their pattern.
- **H097** — Weekly rota mobile layout. The rota surface still overflows horizontally.
- **Sales data integration** — blocked on a real export from the customer.

## Locked corrections

Settled after real cost. Do not reopen.

- **Store model.** The first customer runs three separate stores under one tenant, not
  three work areas inside one store. `work_area_id` is nullable and tag-only, and this
  customer does not use it.
- **Work-area lifecycle.** `WorkAreaPatch` accepts `label` only. Generic PATCH does not
  accept `is_active`, deliberately, so deactivation cannot bypass the `WORK_AREA_IN_USE`
  guard. Inactive work areas are read-only historical records. See H096.
- **Generate Week endpoint is flat.** `POST /api/v1/rota/generate-week`, body exactly
  `store_id` and `week_start`, schema is `extra="forbid"`. Rota reads remain site-scoped
  via `getSiteWeeklyRota`. This asymmetry is intentional.
- **Empty recommendation drafts were never an engine bug.** Every occurrence traced to a
  snapshot created before shifts or availability were ready.
- **Employment and pay model.** D053 is locked. Read `DECISIONS.md` before any
  multi-store, hours, earnings or pay work.

## Unresolved matters

- **Testing depth.** Light smoke test before committing a phase, one thorough end-to-end
  pass after a feature is complete. Do not repeat a large isolated CRUD pass unless a new
  defect justifies it.
- **CI is green.** The full backend suite is 455 passed, 0 failed, 6 skipped. H090 was
  resolved on 2026-08-10 as test-data expiry, not a production defect and unrelated to the
  H085 identity seam.
- **H091 remains open.** Recommendation-draft creation does not acquire the Generate Week
  advisory lock, so invalidation against a concurrently created draft is best-effort.
- **Sales data for franchise counters.** Sales-driven staffing is blocked on a real export
  from the customer. This is a phone call, not a build task. It has been outstanding across
  multiple sessions. Ask whether it has arrived.

## Runtime gotchas relevant right now

**Stale API container.** After any backend phase, rebuild before browser testing or the
browser talks to an older API than the repository.

```bash
docker compose -f infra/docker-compose.yml up -d --build --force-recreate api
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc 'alembic -c apps/api/alembic.ini upgrade head'
```

**Test suite.**

```bash
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc "PYTHONPATH=/app pytest apps/api/tests/ -q"
```

Expected: 455 passed, 0 failed, 6 skipped.

**GitHub authentication.** HTTPS with a fine-grained Personal Access Token, cached via
`credential.helper store`. Account passwords are rejected. If a push fails with "Password
authentication is not supported", the token has expired and needs regenerating at
https://github.com/settings/tokens with Contents: Read and write on this repository.

**Frontend dev server.**

```bash
cd apps/web && npm run dev
```

Note the port it prints; Next.js moves off 3000 when it is taken.

## First inspection steps in a new session

Do not assume this document is current.

```bash
cd ~/code/anci-ops-suite
git status --short --branch
git log --oneline --decorate -8
git fetch origin
git rev-list --left-right --count origin/main...HEAD
```

Expected: branch `main`, clean tree, synced with origin. HEAD will be ahead of the
implementation commit above; docs commit separately by convention.

Then inspect the real `availability_entries` schema, the availability routers, and
`_availability_covers_shift` before drafting anything for H088a or Availability.1. Grep the code.
Do not trust this document, older PRDs, or an assistant's uploaded copies.