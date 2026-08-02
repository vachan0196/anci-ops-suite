# Project Handover

**Valid at commit:** `2cd98c4`
**Branch:** `main`
**Date:** 2026-07-31
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
2cd98c4  feat: add weekly coverage rule management UI       (CoverageUI.1)
a4a27c5  docs: lock multi-store employment and pay semantics
e5faff1  fix: restore reliable backend test rate-limit setup (H089 resolved)
7132530  feat: add safe coverage generation provenance       (Coverage.1a)
```

No uncommitted work. Nothing pending review.

## Immediate next phase: CoverageUI.2

Wire the existing Generate Week endpoint into the Coverage rules workflow. The backend
exists and works. The button is currently disabled and labelled "Coming later". That is
the whole gap.

### Scope

- Enable the existing action and call the real endpoint.
- On success: refresh the weekly rota, reset recommendation-draft state, keep the
  selected site and week, report whether a draft was discarded.
- Report the reconciliation result using only fields the backend returns:
  `created_count`, `replaced_count`, `kept_matching_count`, `kept_conflict_count`,
  `generation_run_id`, `draft_discarded`.
- Show a warning before regenerating **only** when an active recommendation draft is
  loaded.
- On failure, leave rota and recommendation UI state intact. The backend operation is
  transactional.

### Acceptance criteria

- Generate Week runs from the UI and produces open shifts for the selected store and week.
- Counts displayed match the API response exactly.
- No invented classification. Do not write "kept 3 assigned shifts". The response carries
  matching and conflict counts, not an assigned/published/manual breakdown.
- After a successful generate, the recommendation panel visibly resets rather than
  showing a stale discarded draft.
- A failed generate changes no visible state.
- Existing rota, recommendation, apply and publish flows are unaffected.

### Non-goals for this phase

Do not expand into: work-area reactivation (H096), Weekly rota mobile redesign (H097),
multi-store assignments (H094), pay calculation, Availability.1, recommendation-engine
changes, RBAC changes, or backend work-area lifecycle changes.

## After CoverageUI.2

1. **One end-to-end customer workflow test**, not another exhaustive isolated pass:
   define coverage rules, Generate Week, generate recommendations, apply, publish.
2. **Availability.1**: timed employee availability.

Availability.1 is the user's original goal. It was deferred behind coverage work because
coverage rules define the real shift windows that availability presets should map to.
Building it first would have meant inventing generic period labels that might not match
how any given store runs.

Useful when it starts: `availability_entries` already has `start_time` and `end_time`
columns, currently unused (NULL means full day), and `_availability_covers_shift` already
handles windowed availability. Largely wiring, not new architecture.

## Locked corrections

These were settled after real cost. Do not reopen them during CoverageUI.2.

- **Store model.** The first customer runs three separate stores under one tenant, not
  three work areas inside one store. An earlier misunderstanding drove part of the
  Coverage.1a design. `work_area_id` is nullable and tag-only, and this customer does not
  use it.
- **Work-area lifecycle.** `WorkAreaPatch` accepts `label` only. Generic PATCH does not
  accept `is_active`, deliberately, so deactivation cannot bypass the `WORK_AREA_IN_USE`
  guard. Inactive work areas are read-only historical records. See H096.
- **Empty recommendation drafts were never an engine bug.** Every occurrence traced to a
  snapshot created before shifts or availability were ready. RecommendationUI.3 fixed the
  recovery gap.
- **Employment and pay model.** D053 is locked. Read `DECISIONS.md` before any
  multi-store, hours, earnings or pay work.

## Unresolved matters

- **Testing depth.** Agreed after CoverageUI.1 took a very long verification pass: light
  smoke test before committing a phase, one thorough end-to-end pass after a feature is
  complete. Do not repeat a large isolated CRUD test pass unless a new defect justifies it.
- **CI is red.** Caused by the two known H090 employee-portal failures, not by recent
  work. CI stays red until H090 is fixed.
- **Sales data for franchise counters.** Sales-driven staffing is blocked on a real export
  from the customer. Ask whether it has arrived.

Deferred items most likely to become relevant next: **H090**, **H097**, **H094**,
**H096**, **Coverage.1b**. Definitions are in `HARDENING_BACKLOG.md`.

## Runtime gotchas relevant right now

**Stale API container.** After any backend phase, rebuild before browser testing or the
browser talks to an older API than the repository. This produced a full round of false
422 and 404 diagnosis during CoverageUI.1.

```bash
docker compose -f infra/docker-compose.yml up -d --build --force-recreate api
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc 'alembic -c apps/api/alembic.ini upgrade head'
```

**Test suite.** H089 is fixed. The suite runs green by default with no `-e` flag.

```bash
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc "PYTHONPATH=/app pytest apps/api/tests/ -q"
```

Expected: 453 passed, 2 failed, 6 skipped. The two failures are H090.

**Overnight shifts are impossible.** Coverage template validation rejects
`end_time <= start_time`, so 24-hour sites cannot express their pattern until
Coverage.1b.

## First inspection steps in a new session

Do not assume this document is current.

```bash
cd ~/code/anci-ops-suite
git status --short --branch
git log --oneline --decorate -8
git fetch origin
git rev-list --left-right --count origin/main...HEAD
```

Expected: HEAD `2cd98c4`, branch `main`, clean tree, synced.

Then inspect the Coverage rules component and the Generate Week code path before drafting
anything for CoverageUI.2.
