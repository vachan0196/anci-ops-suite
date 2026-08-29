# Project Handover

**Valid at implementation commit:** `77709ba`
**Branch:** `main`
**Date:** 2026-08-23
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
77709ba feat(availability): cross-date interval arithmetic and loader repair (Coverage.1bB-1)
3555dc5 docs: record Coverage.1bA-2 completion and three backlog findings
5180c21 feat(rota): manual overnight shift entry and carry-over display
78a6a3e docs: record Coverage.1bA-1 completion and three backlog findings
a809a9c feat(coverage): overnight coverage templates and generation
29db901 docs: accept D061 cross-midnight interval representation
fc0fcc6 docs: record Availability.1b completion and seven backlog findings
7408893 feat(availability): expose preferred_off on employee availability page
526c699 docs: record Availability.1a completion and the D059 remediation
70b467e feat(availability): timed declared availability semantics
e0fcbbe docs: record D059 resolving the preferred_off eligibility contradiction
674b3e3 docs: record D058 scoping contradictions and reason composition
326bca4 docs: record D057 implementation-forced availability rules
87976d8 docs: record D056 amending D055 after second-pass inspection
1f321f0 docs: record D055 availability semantics and add design directory
eb6840c test: lock availability date and row-shape validation boundaries
0b884e2 docs: record D054 site-local-as-UTC convention and test date rule
9144c89 docs: correct H090 root cause, add H098, refresh handover
e344ecf fix(tests): make employee portal test dates relative to today
6ebf321 docs: add latest commit to handover log block
678204c docs: correct handover self-reference to its own commit
f45b49a docs: refresh handover for CoverageUI.2 completion and Availability.1
888e867 docs: record CoverageUI.2 completion in README and correct dates
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

## Just completed: H088a

Availability date convention and row-shape boundary tests, committed as `eb6840c`.
Fourteen boundary cases lock the Monday week_start rule, the half-open date window, the
employee past-date guard, and submitted row shape, at both unit and HTTP level, across the
employee create path and admin replace-week. D054's wall-clock convention is now stated in
the availability router docstring. No production behaviour changed.

Verified during the phase: half-open availability rows — exactly one of `start_time` or
`end_time` set — fall outside BOTH partial unique indexes and have no check constraint.
`_validate_availability_payload` is the only guard against them. This is now tested but
remains a single point of failure worth noting if a third writer is ever added.

Known limitation: `test_employee_past_date_guard_rejects_yesterday_accepts_today_and_future`
binds `date.today()` before issuing its HTTP calls. A run crossing midnight between those
two points would fail spuriously. Accepted rather than fixed; the test must use real today
because it exercises a guard against `datetime.now()`, and freezing time was out of scope.

## Just completed: Availability.1a

Timed declared availability semantics, committed as `70b467e`. Backend only.

One shared declared-availability evaluator now serves both the recommendation engine and
the shift-side check, replacing two byte-identical copies of the old boolean matcher. All
four declaration types are evaluated; previously `unavailable` and `preferred_off` were
never loaded. The evaluator result is orthogonal — eligibility, `preferred_off` standing,
and exclusion cause are separate fields — because a flat enum would discard `preferred_off`
on excluded candidates, which D055 rule 4 requires to remain explanatory.

Full detail is in `IMPLEMENTATION_STATUS.md`. Not restated here.

**One deliberate behaviour change.** Cross-midnight shifts now fail closed in automatic
matching, per D057 rule 6. A full-day row on the start date no longer establishes
eligibility for a shift crossing midnight. Manual assignment is unaffected.

**Two defect sites were corrected before commit, under D059.** An incorrect reading of
`preferred_off` let a lone preference establish eligibility, and separately let a
preference-only candidate satisfy D057 rule 8's counterfactual. The second site sits behind
an early return, so fixing the first would not have fixed it.

### The correction worth remembering

The wrong reading entered through the **v3.1 Codex prompt**, which specified
`preferred_off → available`. Codex implemented what it was told. The prompt survived **two
adversarial review passes** with that line intact, and the defect surfaced only in
post-implementation diff review.

This is what D057 exists to prevent — a product rule entering through a prompt rather than
through adjudication. It got through because it did not look like a new rule; it looked like
a restatement of D055 rule 1. Three existing tests had already locked it green. They were
corrected rather than deleted, because their subjects were valid and only their fixtures
were wrong; deleting them would have removed the D056 rule 1 and D058 rule 2 guarantees
while the suite still looked green.

Check prompts for rules that read as restatements. Those are the ones review misses.

## Just completed: Availability.1b

Employee-facing `preferred_off` surface, committed as `7408893`. Frontend only,
four edits across two files. **Availability.1 is complete per D057 rule 9.**

Detail is in `IMPLEMENTATION_STATUS.md`. Not restated here.

The process lesson from 1a held. The Codex prompt for 1b contained no sentence
describing what `preferred_off` means — it specified literal string values, file
anchors, and placement only. There was no restatement surface because there was
nothing to restate.

## Just completed: Coverage.1bA-2

Manual overnight shift entry and carry-over display, committed as `5180c21`.
Detail is in `IMPLEMENTATION_STATUS.md`.

A manager can now create and edit shifts spanning midnight, and the grid shows
which day a night shift carries into. Within Coverage.1b, overnight coverage
rules, generation, manual entry, and display are complete. What remains is
overnight declared availability and automatic matching.

Three implementation defects were caught in review before commit, with three
different causes: representation scope, D054 handling, and async state
ownership. Separately, D054 caused repeated reasoning and specification traps
during the phase, which is why its frontend arithmetic convention is now
documented explicitly in `CLAUDE.md`.

## Just completed: Coverage.1bB-1

Cross-date interval arithmetic and loader repair, committed as `77709ba`. Backend
only. Detail is in `IMPLEMENTATION_STATUS.md`.

**The gate is still closed.** 1bB-1 made the arithmetic correct; it did not make
overnight availability writable or matchable. D057 rule 6 still returns
`CROSS_MIDNIGHT_UNSUPPORTED` before any positive is considered, and the write
validator still rejects an earlier end time. Nothing an operator can do reaches
the new code paths yet — they are exercised only by the twelve regressions.

## Just completed: Coverage.1bB-2a

Transactional invariant repair, committed as `757c34e`. Backend only. Detail is
in `IMPLEMENTATION_STATUS.md` and not restated here.

The availability advisory lock is now subject-global, and admin replace-week
validates against retained same-source rows in adjacent weeks while keeping its
week-owned deletion set.

**The gate is still closed.** 1bB-2a made the invariant hold across periods; it
did not make overnight availability writable or matchable. D057 rule 6 remains
controlling and `_validate_availability_payload` still rejects an earlier end
time.

## Immediate next phases

**Coverage.1bB-2b** — open the gate. Two items, in this order.

1. **The write gate.** Relax `_validate_availability_payload` to reject equality
   only; equality stays rejected under D061 rule 1. **There is exactly one
   enforcement point in the repository** — no Pydantic validator on request or
   response, no model `CheckConstraint`, no migration `CHECK`, and no frontend
   guard — so **no migration is needed**. The half-open XOR guard sits
   immediately above the clause being changed and must not move: per H088a it is
   the only defence against exactly-one-time-set rows, with no database
   constraint behind it. This item ships a user-visible capability with no
   frontend change, because the employee availability page already has time
   inputs and no client-side ordering guard (H117).

2. **D057 rule 6 replacement.** Remove the evaluator's cross-midnight early
   return and the then-dead `start_date_entries`, whose only reference is inside
   that branch. `CROSS_MIDNIGHT_UNSUPPORTED` appears in no response schema, no
   API contract and no frontend string, so there is no contract blast radius.
   **T7 and T7b are rewrites, not deletions.** T7b's expected value inverts: it
   currently asserts that a next-day preference is *not* seen, and once
   `relevant_entries` governs, it will be. That inversion is the marker that the
   removal actually took effect.

Also carried into 2b:

- **The deferred `W + 7` boundary regression.** The bound is implemented; the
  semantic test needs a Sunday `W+6` payload row crossing midnight, which item 1
  makes writable. 2b is not complete until it is exercised.
- **`all_positives` draws from `relevant_entries`.** A prior-day hard positive
  is therefore already live in contradiction detection and **becomes observable
  the moment item 1 opens, not item 2.**
- **On completion of 1bB-2b, D061 supersedes D057 rule 6**, and `DECISIONS.md`
  must be updated in that phase's documentation commit. It is deliberately
  untouched until then.

**H115 still needs a ruling before anything cites D060.** Rules 13, 15 and 16 of
the committed entry were never adjudicated, and the rule 4 citation is
unverified. `Status: Proposed` keeps this non-blocking, but it must close before
D060 is Accepted or cited.

**H116, H117 and H118 are logged and not folded in.** None is a Coverage.1bB
dependency.

**SiteHours.24h** — continuous-opening representation per D061 rule 1a.
Independent; opening hours have no scheduling consumer.

**Not on the critical path:** H102 and H103 remain deprioritised under
admin-first MVP scope. H112, H113 and H114 are rota-editor hardening, all
pre-existing.

### Governing decisions for the availability area

Read all of these before any further availability work. They interlock and several amend or
qualify each other:

```text
D048  person-scoped availability, admin replace-week authority
D054  site-local wall-clock convention
D055  declared-availability semantics
D056  amends D055 — ranking, cross-source fail-closed, override deferral
D057  nine implementation-forced rules D055/D056 did not settle
D058  contradiction scope and reason composition
D059  amends D055 rule 1 — preferred_off is a soft modifier only
```

`docs/design/availability_product_area.md` is **proposed only** and the lowest authority in
the repository. Per `docs/design/README.md`, only `DECISIONS.md` entries marked Accepted are
binding, and where the two disagree `DECISIONS.md` wins.

**D058's stopping rule remains in force for the availability area.** A new decision during a
phase is permitted only where inspection proves an accepted rule impossible against live
code, or two accepted rules mutually contradictory. D059 was already an exception-B
invocation. A second one is a signal to reassess phase scope, not licence to write D060.

### Revised phase sequence

Not yet scheduled beyond Availability.1b, in this order:

1. Availability.1a — timed declared availability, backend only. ✅ Done, `70b467e`
2. Availability.1b — employee-facing `preferred_off` surface. ✅ Done, `7408893`.
   Availability.1 is complete, per D057 rule 9
3. Availability.Override.1 — converge manual assignment paths on override-aware logic,
   per D056 rule 3 and H099
4. Feasibility.1
5. H094 groundwork
6. Availability.2 — standing baseline
7. Availability.3 — change lifecycle
8. Precedence phase
9. Cross-site phase

Submission windows, availability deadlines, publication timing, and standing scheduling
baselines are **proposed only**, recorded in `docs/design/availability_product_area.md`, and
are **not adjudicated**. They are not required for Availability.1 and must be independently
decided when Availability.2 begins. See also H100 (availability editability after publication
is asymmetric, no submission-window concept exists in the codebase today).

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

- **Coverage.1b** — overnight and 24-hour operation. **Priority elevated; no longer
  "unscheduled, no fixed order."** The first customer runs a mix of 24-hour and
  non-24-hour sites under one tenant, and 24-hour operation is currently unrepresentable
  at three layers — store opening hours, coverage templates, and availability — all
  blocked by the same `close_time > open_time` constraint. Recorded as H101. D057 rule 6
  had to be adjudicated as an unconditional cross-midnight fail-closed because the
  intended site-dependent rule needed a 24-hour indicator that does not exist.

Not yet scheduled, in no fixed order:

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
- **CI is green.** The full backend suite is 494 passed, 0 failed, 6 skipped. H090 was
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

Expected: 494 passed, 0 failed, 6 skipped.

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