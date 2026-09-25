# Project Handover

**Last implementation commit:** `0be2084` — feat: H154 fail-closed validation of security-critical settings
**Documentation checkpoint (not the project-knowledge export record — see
`docs/GPT_REVIEW_PREAMBLE.md`):** this commit
**Repository HEAD inspected before this update:** `0be2084`
**Branch:** `main`
**Date:** 2026-09-25
**Working tree:** clean before this documentation change
**Remote:** `main` and `origin/main` match at the inspected HEAD (0 ahead / 0 behind)

Always determine current HEAD from the repository using the pre-flight
commands below; do not infer it from this file.

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
c73e80b docs: record Q.5.3b completion; record the step-up direction
024d6c1 feat: Q.5.3b 2FA enrolment and login, H171 copy, H173 input checks
2ac1ad5 docs: correct H173 recovery-code format; log H174; add terminal-fact rule
870405a docs: log H171 and H173
068f7c2 docs: log H168-H170 and H172; add H169 evidence to H154
c536f60 fix(infra): pass TOTP_ENCRYPTION_KEY to the api service (H169-a)
4c0130b docs: record Q.5.3a-2b-2 completion; close Q.5.3a; log H165
9a1b9fe feat: Q.5.3a-2b-2 verify-email journey, H163 frontend repair, rule 10 indicator
e8de256 docs: record Q.5.3a-2b-1 completion; adjudicate H163's direction
1044b6a feat: Q.5.3a-2b-1 UserOut exposes email_verified_at
53a3b3d docs: record Q.5.3a-2a completion; log H162-H164
3d19e49 feat: Q.5.3a-2a admin password recovery journey
4507e7d docs: record D067 + H069 completion; close H069 and H153
7b7ab75 feat: D067 session revalidation and H069 cookie-only refresh
9f185e6 docs: add model routing policy to AI_WORKFLOW
eb2a52c docs: add model routing policy
e9716b1 docs: accept D067; rewrite H069 with closure criteria; amend D036
2fd3b99 docs: record Q.5.3a-0 completion
c7352b6 feat: Q.5.3a-0 account-security infrastructure hardening
894b148 docs: adjudicate D038 amendment and D065; add H133-H145
de5abc3 docs: record account-security chain gaps, amend D038 delivery direction
37a2797 docs: accept D064 admin membership lifecycle and revocation
fbe4faf docs: log H125 duplicate D044 decision identifier
c728790 docs: accept D063 admin identity and store assignment, retire D062
8dbaccb docs: record governing-document upload rule and external review preamble
9a11030 docs: record Coverage.1bB-2b completion, supersede D057 rule 6
a09da46 feat(availability): open overnight write gate and remove D057 rule 6 branch (Coverage.1bB-2b)
852cb90 docs: record Coverage.1bB-2a completion and log H116-H118
757c34e fix(availability): enforce cross-period write invariant
b844103 docs: log H115 — unadjudicated rules in committed D060
c7fb7e9 docs: record Coverage.1bB-1 completion, propose D060
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

The D067 + H069 record is split across two commits. `4507e7d` carries the phase
evidence under `docs/phases/d067-h069/` and the v7 implementation prompt. Its
message also described updates to the four governing documents, which were
modified but unstaged at that commit and land in the commit following it.
Determine current HEAD from the repository, not from this line.

## Just completed: WALK.1

**WALK.1 is a discovery session, not an implementation phase.** It walked the
product end to end in a browser against the local stack, on 2026-09-24, to
establish what is broken in the product before further work is done to make a
deployment safe. No feature code changed.

The full record is `docs/phases/walk1/observations.md`. **It records
observations and decides nothing.** No backlog entry has been created from it
and no D-number taken. Read it before drafting anything that touches the
surfaces it covers.

**The core journey works.** Register, 2FA enrolment and challenge, company
setup, site creation, staff creation, opening hours, shift creation,
recommendation generation, publish, employee login, employee rota visibility,
declared availability, cover request, and manager approval all completed.

**Three behaviours were browser-verified for the first time:**

```text
overnight shifts          22:00-06:00 created, stored, and rendered as
                          "Overnight carry-over until 06:00" the next day
                          (Coverage.1bA). This contradicts H101's note that
                          the admin UI blocks overnight creation twice —
                          that note is out of date.
overnight availability    a 21:00-06:00 declared entry accepted and
                          persisted (Coverage.1bB)
cookie session refresh    after ~30 minutes idle, two 401s followed by
                          POST /auth/refresh 200 and successful replay.
                          D036's memory-only access token model recovering
                          live, which C2 was written to prove.
```

**Roughly 25 observations were recorded.** Three would cause real harm with a
customer and are the candidates for the next fix phase:

```text
A10-a   number inputs change value on page scroll — base hourly rate and
        both soft caps. Corrupts pay data silently, no error, no trace.
B1-c / B1-e / H102   no employee password reset anywhere: none on the
        employee portal, none admin-side, and temporary passwords are
        never forced to change. A forgotten password is a dead end.
C1-a    an approved cover request tells the admin "rota was not changed"
        and the employee only "Cover · approved", while the shift stays
        on their rota as scheduled. The employee's cover form has no
        target-employee selector, so every cover request they raise
        necessarily approves without reassigning.
```

**One item needs adjudication before any work touches it, and one is
resolved:**

```text
B3-b    availability type semantics. Code inspection confirmed the model
        already matches Vachan's intent — unavailable is a hard negative
        (declared_availability.py:23, 200-205). What is missing is a
        full-day vs specific-times choice on Unavailable. Sits under
        D057, D059, D060, D061 and Availability.1a.
A12-d   RESOLVED 2026-09-25, no defect. The two shifts in question were
        unassigned; the engine correctly excluded the user from exactly
        the dates he declared unavailable. The walkthrough misread the
        grid. Kept in the observations file with its evidence so the
        question is not re-raised. A 21:00-06:00 declared window
        correctly admitted a 23:00-06:00 shift, which is the best
        evidence the walk produced that Coverage.1bB holds at the
        matching layer and not only at storage.
```

**Environment facts the next session should not rediscover:**

```text
OpenAPI is served at /openapi.json, not /api/v1/openapi.json
Postgres: user anci, database anci_ops
TOTP_ENCRYPTION_KEY exists only as a shell export and does not survive a
  container recreate run from a shell without it. The loss is silent and
  surfaces only at enrolment (H169). Presence checks lie: ${VAR:+present}
  passes on a placeholder, and `test -n "VAR"` without $ has never
  checked anything. The decoder is the only reliable check.
APP_BASE_URL=http://localhost:3000, so every reset and verification link
  points at the laptop. This matters at the tunnel stage.
the local database carries rows from earlier development and is not a
  clean dataset — filter by store when reading it.
```

**Next gate: not chosen.** The sequence discussed, none of it released:

```text
triage the observations into blocking / wanted / later
adjudicate B3-b
a fix phase covering the blocking three
a seed script — hand entry of company, site, hours and six staff proved
  too slow to repeat, which answers the question WALK.1 step 3 asked
the Cloudflare tunnel and a second-laptop walk (H068 scoping)
```

Steps 3, 4 and 5 of the WALK.1 plan — seeding, the tunnel, and the
second-laptop walk — were not started.


## Just completed: H154

**H154 is complete at `0be2084`, under D069.** Staging and production now refuse
to start with unsafe security configuration. H148 and H169 close with it.
Suite: **1522 passed / 0 failed / 6 skipped**. See `IMPLEMENTATION_STATUS.md`
for the record, and D069 for the rules.

Proved from the terminal: under `ENV=production` with Compose's development
values, `import apps.api.main` exits 1, naming the four unsafe settings.

**Next gate: not chosen.** No decision releases a specific next phase. Open on
the path to staging and production:

- **H184** — transport-library logging. Blocks staging.
- **H068** — deployment. Not released; inspect its entry before drafting.
- **H180** — credential injection. Blocks production.
- **H181** — Resend key startup validation, the same fail-closed pattern D069
  uses. Blocks production and first customer.
- **H183** — awaits Vachan's adjudication of the intended sentence.
- **H178, H179** — customer two stays blocked until both ship.
- **H185, H186** — 🟢 observations from this phase. Not decided.

Also outstanding before the first customer, unchanged: H138, H102,
SiteHours.24h and H174. The sensitive-action step-up draft must take a D-number
above D069, confirmed from `DECISIONS.md` before use.

## Just completed: D068.1

**D068.1 is complete at `7a2fdc1`.** Staging and production are constructible
for the first time: the `resend` backend is registered and permitted in those
two environments only. Suite: **1120 passed / 0 failed / 6 skipped**. See
`IMPLEMENTATION_STATUS.md` for the record.

**Delivery is not proved.** No real-provider send has occurred; every test uses
an in-memory transport. The first real send happens in staging, which does not
yet exist (H068).

**Next gate: H154.** D068 rule 1 released it. Inspect its current entry before
drafting. D068 rule 5 fences `RESEND_API_KEY` out of H154's scope — its startup
validation is H181's.

Open on the email and deployment path:

- **H184** — transport-library logging can expose the key and provider bytes.
  Blocks staging.
- **H180** — production credential injection. Blocks production.
- **H181** — key startup validation. Now also records the `Bearer None` and
  trailing-newline behaviour. Blocks production and first customer.
- **H183** — the D068 section 3 splice. Awaits Vachan's adjudication of the
  intended sentence.
- **H178, H179** — durable dispatch and timing isolation. Customer two stays
  blocked until both ship and D068's exception is retired.

Also outstanding before the first customer, unchanged from Login.1: H138, H102,
SiteHours.24h, and H174. The sensitive-action step-up draft must take the next
free D-number, confirmed from `DECISIONS.md` before use.

## Just completed: Login.1

Login.1 is complete, with H174 deferred to its own phase and gate. H172's QR
and manual fallback and H171's expired-challenge recovery were browser-gated
by Vachan on 2026-09-17. H175 items 2–4 are done; item 1 and H170 remain open.
Final backend suite reported by Vachan: **1075 passed / 0 failed / 6 skipped**.
Implementation and documentation are committed; HEAD is `5ea5565` with a clean tree. See `IMPLEMENTATION_STATUS.md`,
`docs/phases/login1/README.md` and `docs/phases/login1/browser-gate-evidence.md`.

**Next gate: D068's implementation phase.** H154 and the deployment are blocked
behind D068. D068 makes staging and production constructible by adding the first
permitted production email backend; H154's settings-validation work and H068's
deployment work follow that gate. Login.1's gates are complete.

**The provider side is already done.** Resend is live on the dedicated sending
subdomain `mail.siteoverview.uk`, verified 2026-09-20, with SPF, DKIM and DMARC
records in place. The operational record is
`docs/operations/email-delivery-setup.md`. What remains under D068 is the code
path — the adapter, its registry entry, and the staging/production environment
mapping — plus H180 (credential injection) and H181 (fail-closed startup
validation). No live credential exists on a development machine, per D068
rule 5, and the first real-provider send happens in staging.

Also outstanding before the first customer:

- Production email delivery under D038's amendment. The sending identity is
  satisfied — see D068 section 7 and `docs/operations/email-delivery-setup.md`.
  The code path is D068's implementation phase. H180 and H181 remain open, and
  every D038 item D068 does not waive still blocks customer one.
- H138 admin email identity normalization.
- H102 employee credential lifecycle / admin management surface.
- SiteHours.24h. Vachan's current customer context is one 24-hour site and one
  non-24-hour site. Continuous opening is still forbidden by
  `ck_store_opening_hours_open_times` (`apps/api/models/store_opening_hours.py:31`).
- H174 recovery-code usability remains deferred and unimplemented.

The sensitive-action step-up decision is drafted but not accepted or assigned
an issued D-number; it must take a later number. D068 is now the accepted
production-email decision. D066 has two headings (the decision and its
amendment); H125 records the separate duplicate D044 defect. Do not infer the
next free number from a heading count.

## Just completed: Q.5.3b

**Q.5.3b is complete at `024d6c1`.** 2FA enrolment and 2FA login are usable
through the product, with H171's copy and H173's input checks. H130's
login-lockout half is proved fixed; H130 stays open until step-up ships. See
`IMPLEMENTATION_STATUS.md` for the completion record and
`docs/phases/q5-3b/browser-gate-evidence.md` for the gate.

**Read "Design-critical facts come from the terminal" in `docs/AI_WORKFLOW.md`
before drafting anything.** This phase lost a day to a panel report that quoted
recovery-code constants that do not exist.

### Direction agreed 2026-09-16 — not yet a decision

Vachan set a sensitive-action policy that replaces Q.5.3c's original
single-endpoint scope. It needs a D-number in `DECISIONS.md` before any
implementation.

```text
step-up    re-verify with 2FA before a sensitive action, even after a 2FA login
window     one verification covers further sensitive actions for a short time
who        owner-only at MVP
where      enforced by the API, never by the UI alone

gated
  store opening hours changes
  adding an employee
  deactivating an employee      "delete" means deactivate; record-keeping
                                duties make erasure a separate process
  changing pay
  viewing NI number, passport and right-to-work documents
                                the API withholds them until verified
  closing a store               deactivate, shipped together with reopen (H082)

not gated
  rota shift edits
```

Carry into the D-number:

- Every owner must enrol 2FA before adding a first employee, so H172, H170 and
  H174 become pre-customer blockers.
- H165 is superseded once the D-number is accepted.
- Q.5.3c's gate no longer needs a destructive control. Build the reusable
  step-up prompt, prove it on one existing, reversible action that already has
  a screen, then widen action by action, including Phase 1a's revoke mutation.
- The window length, which gated actions exist today, their endpoints, and
  which already call `require_sensitive_admin_action` are inspection questions,
  answered from the terminal before drafting.

## Just completed: Q.5.3a-2b-2

**Q.5.3a is complete at `9a1b9fe`.** H163's frontend half is closed; its
backend half remains open. See `IMPLEMENTATION_STATUS.md` for the completion
record, the correction to the commit message's login-loop claim, and Vachan's
2026-09-13 browser gate. **Q.5.3b, 2FA enrolment and login, is the next gate.**

## Just completed: Q.5.3a-2b-1

Q.5.3a-2b-1 is complete at `1044b6a`. The suite is **1075 / 0 / 6**
(passed / failed / skipped). The mutation demonstration is recorded under
`docs/phases/q5-3a-2b-1/`. See `IMPLEMENTATION_STATUS.md` for the completion
record. **Q.5.3a-2b-2 is the next gate and must repair H163's frontend half
before its indicator work.**

## Just completed: Q.5.3a-2a

Q.5.3a-2a is complete at `3d19e49`. **Q.5.3a-2b is the next gate.**
Rule 9 is partially satisfied: the visible URL is scrubbed, but the token remains
in the serialised React payload and Next router history state. This finding is
logged as H162. **Q.5.3a is not complete until 2b ships.** See
`IMPLEMENTATION_STATUS.md` for the scope split and evidence, including Vachan's
2026-09-13 browser gate. H163 records the role/nullability disagreement, and
H164 records the pre-existing registration/live-session behaviour.

## Just completed: D067 + H069

D067 + H069 is complete at `7b7ab75`, with documentation in the commit that
follows. **Q.5.3a-2 is unblocked; the next gate is Q.5.3a-2.** H069 and H153
are closed. See `IMPLEMENTATION_STATUS.md` for the full phase record and
`docs/phases/d067-h069/` for the evidence.

Carry forward the coverage statement: revocation is swept across all 100 secured
operations. Absent session, malformed sid, nonexistent session, expired session,
portal mismatch and subject mismatch are tested per authentication path across
eight paths, not per operation. The sweep and per-path matrix compose; D067's
literal "on every authenticated operation" form was not achieved, and this is
the stated alternative. The explicit membership and role preservation matrix
was not built; existing passing RBAC tests are the current evidence, and the
matrix remains unmechanised verification debt. The per-path single-primary-key
session SELECT assertion covers D067 §5 query shape.

Carry forward two Open findings in `HARDENING_BACKLOG.md`:

- **H160:** ordinary 422 validation messages disclose the endpoint's server file
  path and line number through `str(exc)`; unrelated to H069 and not fixed.
- **H161 (Low):** separate dependency and auth-router clocks can make fixtures
  validate sessions against a different clock from issuance. Both use the real
  clock in production; this is test-infrastructure fragility, not a production
  defect. Anchoring the TOTP test to `date.today()` repaired that fixture, not
  the underlying clock split.

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

**One deliberate behaviour change.** Cross-midnight shifts failed closed in automatic
matching from this phase, per D057 rule 6. A full-day row on the start date no longer
established eligibility for a shift crossing midnight, and manual assignment was
unaffected. **D057 rule 6 was superseded by D061 in Coverage.1bB-2b on 2026-09-02**; a
full-day start-date row still does not establish that eligibility, but the reason is now
structural containment rather than an early return.

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
rules, generation, manual entry, and display were complete at this commit. What
remained — overnight declared availability and automatic matching — landed in
Coverage.1bB and completed on 2026-09-02.

Three implementation defects were caught in review before commit, with three
different causes: representation scope, D054 handling, and async state
ownership. Separately, D054 caused repeated reasoning and specification traps
during the phase, which is why its frontend arithmetic convention is now
documented explicitly in `CLAUDE.md`.

## Just completed: Coverage.1bB-1

Cross-date interval arithmetic and loader repair, committed as `77709ba`. Backend
only. Detail is in `IMPLEMENTATION_STATUS.md`.

**The gate was still closed at this commit.** 1bB-1 made the arithmetic correct; it did
not make overnight availability writable or matchable. D057 rule 6 still returned
`CROSS_MIDNIGHT_UNSUPPORTED` before any positive was considered, and the write
validator still rejected an earlier end time. Nothing an operator could do reached
the new code paths yet — they were exercised only by the twelve regressions.
Coverage.1bB-2b opened the gate on 2026-09-02.

## Just completed: Coverage.1bB-2a

Transactional invariant repair, committed as `757c34e`. Backend only. Detail is
in `IMPLEMENTATION_STATUS.md` and not restated here.

The availability advisory lock is now subject-global, and admin replace-week
validates against retained same-source rows in adjacent weeks while keeping its
week-owned deletion set.

**The gate was still closed at this commit.** 1bB-2a made the invariant hold across
periods; it did not make overnight availability writable or matchable. D057 rule 6
remained controlling and `_validate_availability_payload` still rejected an earlier
end time. Coverage.1bB-2b opened the gate on 2026-09-02.

## Just completed: Coverage.1bB-2b

Overnight availability write gate and D057 rule 6 removal. Backend and tests only.
Detail is in `IMPLEMENTATION_STATUS.md` and not restated here.

**The gate is open, and Coverage.1bB is complete.** `_validate_availability_payload`
now rejects equal times only, and the evaluator's cross-midnight early return is gone
along with `start_date_entries` and the `CROSS_MIDNIGHT_UNSUPPORTED` enum member. An
employee declaring `22:00-06:00` is eligible for a 22:00 to 06:00 shift. **D061
supersedes D057 rule 6 as of this phase.**

D057 rule 3 survives the change: two full-day rows on consecutive dates still do not
stitch to cover an overnight shift.

**Read the `W + 7` bound note in `IMPLEMENTATION_STATUS.md` before narrowing
`staff.py:650`.** The bound's guarantee rests on a mutation demonstrated on
2026-09-02 that is not in the suite, and the accompanying non-overlap control does not
discriminate the bound.

Verified in-browser on 2026-09-02: overnight declarations save and render, and equal
times are rejected with a legible error. No frontend change was required or made.

## Immediate next phases

**Q.5.3 — Admin account security, frontend and delivery.**

Three dependency-ordered subphases. Each subphase carries the browser verification
required for its own behaviour. Q.5.3c additionally carries the complete end-to-end
chain that proves D040's prerequisite.

### Q.5.3a — Admin email verification, password recovery, and delivery

**D065 is the authority for this phase.** It splits Q.5.3a into three ordered
subphases — Q.5.3a-0, Q.5.3a-1 and Q.5.3a-2 — superseding the single-phase scope
and browser gate previously recorded here. D038's amendment moves production
delivery to a separate launch-blocking phase.

Read both entries in `DECISIONS.md` before drafting. Their rules are deliberately
not restated here: a restatement in a non-authoritative document is how a wrong
reading enters.

**Phase state:**

```text
Q.5.3a-0   complete
Q.5.3a-1   complete at 9ac5945 — local email delivery, H132 and H146 closed
D067 + H069 implementation   complete at 7b7ab75; documentation in the following commit
Q.5.3a-2a   complete at 3d19e49 - recovery journey, H058 frontend blocker closed
Q.5.3a-2b-1 complete at 1044b6a - UserOut exposes email_verified_at
Q.5.3a-2b-2 complete at 9a1b9fe - verify-email, H163 frontend half, rule 10
Q.5.3a     complete at 9a1b9fe
H147       Done at 978c66f
H149       Done at 978c66f
H150       open, and does not block — see H147 R-3 as amended
H151       open — the Compose/CI email-selection invariants are unasserted
```

**D067's implementation gate for Q.5.3a-2 is satisfied at `7b7ab75`.** D067
carries the reasoning and the rule for immediate session revalidation, and H069
was bundled with its implementation. Carry forward the coverage limitations
recorded above when relying on this phase.

Q.5.3a-0's completion record is in `IMPLEMENTATION_STATUS.md`. **D066 and H147
are the authority for the gate work** — D066 governs when a dependency advisory
may be suppressed, and H147 carries the resolution as R-1 to R-3 and the
sequencing as R-3. Read both before drafting; their rules are not restated
here.

### Q.5.3b — 2FA enrolment and login

```text
enrolment: status, begin, authenticator setup, confirm
recovery codes presented safely at enrolment
the 2fa_pending login contract: AdminLoginResponse typing, challenge token
  preservation, TOTP or recovery-code entry, /2fa/verify
```

Recovery-code **use** during login is in scope. Disable-2FA and recovery-code
regeneration UI are not, unless the implementing phase establishes they are needed
for a safe journey.

Browser gate for Q.5.3b:

```text
verified throwaway owner
→ enrol TOTP
→ recovery codes are presented safely
→ logout
→ login returns the 2FA challenge rather than establishing a normal
  session
→ submit TOTP
→ normal admin session established successfully
```

Also exercise recovery-code login once, since recovery-code use during login is in
scope, and confirm the used code cannot be reused.

**Do not enrol 2FA on the standing development owner account.** This gate is where
H130's login-lockout defect is proved fixed.

### Q.5.3c — Sensitive-action step-up

**Superseded in direction, 2026-09-16.** The scope and gate below predate the
sensitive-action policy recorded under "Just completed: Q.5.3b". They stand
until that policy's D-number is accepted.

```text
recognise AUTH_2FA_STEP_UP_REQUIRED and AUTH_2FA_ENROLMENT_REQUIRED rather
  than rendering a generic permission failure
prompt for a factor, call /2fa/step-up, retry the original mutation
AUTH_EMAIL_VERIFICATION_REQUIRED routes the owner to verification
```

Closes H130.

**Acceptance gate after Q.5.3c — one browser run, end to end:**

```text
verified email
→ enrol TOTP
→ capture recovery codes
→ logout
→ login and complete the 2FA challenge
→ invoke a sensitive action
→ step-up prompt
→ verify the factor
→ the original action is retried successfully
```

That run is the proof D040's prerequisite is satisfied, and the precondition for
wiring Phase 1a's revoke mutation.

**Note for the browser work:** verification state is not cached. Every request
reloads the user by primary key (`deps.py:188`) and the access token encodes only
`sub`, `exp` and `sid`, so a session observes verification immediately with no
re-login. Enrolling 2FA on an account, however, may lock it out of the portal until
Q.5.3b lands — use a throwaway account and establish a recovery path before
enrolling.

**Phase 1a — Admin membership lifecycle, access-reducing operations only.**

Governed by D064. Closes the listing and revocation portion of H122, and H124.

```text
Migration
  tenant_users.is_active
  users.full_name, nullable, no backfill

Backend
  list admin-side tenant users
  deactivate an admin membership
  revoke that tenant and user's active admin sessions, atomically with the
    membership change
  enforce inactive membership across all seven admin auth paths
  persist full_name
  audit the deactivation

Frontend
  owner-only user-management list
  deactivate action; no create, promote, or role-change surface
  build on staff-directory.tsx's div-grid pattern — apps/web has no table
    component and no <table> element anywhere

NOT Phase 1a
  reactivation
  owner deactivation, promotion, demotion, or transfer
  role change
  new-admin creation UI
  store assignments
  any writer for users.is_active
```

**The revoke mutation is gated on Q.5.3c.** D064 rule 7's inspection was completed
on 2026-09-03 with the result "UX insufficient": `require_sensitive_admin_action`
fails closed at `deps.py:279`, and neither the email-verification gate nor the 2FA
gate is passable through the product. The rule stands unamended; wiring waits. The
rest of Phase 1a — migration, listing, `full_name`, audit — is unaffected.

### The ship boundary, and why it exists

D063 rule 3 states that an admin with zero assignments has zero operational store
access. **That rule is not enforced until Phase 2.** Live code today gives every admin
tenant-wide operational access.

Therefore any admin created or promoted between Phase 1a and Phase 2 receives
tenant-wide access, directly contrary to a rule this project has already Accepted.
Scoping the two phases together does not close that interval; only sequencing does.

The rule that decides what ships in 1a:

```text
operations that REDUCE access  → safe before scoping exists
operations that GRANT access   → wait for Phase 2
```

List, deactivate, revoke and the `full_name` fix all reduce or are neutral. Role
promotion and new-admin creation grant, and are deliberately excluded from Phase 1a's
new management surface.

This does not remove the existing capability. `POST /api/v1/admin/users` still accepts
`role="admin"` today via direct API call. Phase 1a declines to add a new surface to an
unscoped grant; it does not claim to have closed the existing one.

Phase 2 then delivers, in a safe migration sequence: the assignment relation,
existing-admin backfill, assignment enforcement at every store-scoped operation,
deletion of the H123 branch, and creation/promotion with store assignment required at
the point of grant. That completes H122.

### Two transitional states that must not exist

Creation/promotion and its required store assignment must succeed **atomically**, or
the access grant must fail closed. No newly granted admin may exist in an
operationally unscoped state. A sequence where the role grant commits and the
assignment write then fails leaves exactly the tenant-wide access D063 rule 3
prohibits.

Existing-admin backfill must complete successfully **before** assignment-based
enforcement is enabled. Enforcement must not be enabled first and repaired by backfill
afterwards.

The same invariant, both directions:

```text
existing admins      backfill → enforcement
new or promoted      role grant + assignment, atomic
```

The failure each prevents:

```text
enforcement before backfill    every existing non-owner admin
                               locked out on deploy
role before assignment         a new admin silently receives
                               tenant-wide operational access
```

### Current phase sequence

This sequence is planning, not adjudicated authority. Where it conflicts with
`DECISIONS.md`, the decision record governs.

D064 hard-gates only the revoke mutation on Q.5.3c. Migration, listing, `full_name`
and audit could technically land earlier.

The project nevertheless schedules the whole Q.5.3 arc first and keeps Phase 1a
coherent rather than splitting it into two partial passes. Phase 2 is already
hard-dependent on the account-security arc, because admin creation and promotion is
the privilege-grant case identified by D040. With Q.5.3 required before Phase 2
regardless, there is little value in creating a partial Phase 1a checkpoint and
returning to it afterwards.

This is sequencing plan, not an additional D064 security requirement.

The Q.5.3a, Q.5.3b and Q.5.3c subphase scopes and browser gate scripts are likewise
planning, derived from the 2026-09-03 inspections rather than adjudicated. An
implementing phase may revise them against live code without changing the governing
decisions, provided D040 and D064's security requirements remain satisfied.

```text
Q.5.3a-0  Account-security infrastructure hardening
Q.5.3a-1  Local email delivery foundation
Q.5.3a-2a   complete at 3d19e49 - recovery journey, H058 frontend blocker closed
Q.5.3a-2b-1 complete at 1044b6a - UserOut exposes email_verified_at
Q.5.3a-2b-2 complete at 9a1b9fe - verify-email, H163 frontend half, rule 10
Q.5.3a     complete at 9a1b9fe
Q.5.3b    complete at 024d6c1 - 2FA enrolment and login, H171, H173
Q.5.3c    Sensitive-action step-up
Phase 1a  Admin membership lifecycle, access-reducing only
Phase 2   Store assignment, enforcement, backfill
Phase 3   H115 adjudication
Phase 4   D060 admin availability bands
Phase 5   Publish path repair (H121)
── MVP line ──
Phase 6   Reports and sales export
Phase 7   SiteHours.24h
Phase 8   H085 + H102 employee identity
Phase 9   Employee portal
```

**H115 remains open and is now the only blocker between the current state and D060
implementation**, since D060's Coverage.1bB gate opened on 2026-09-02. Rules 13, 15 and
16 of the committed entry were never adjudicated, and the rule 4 citation is unverified.
`Status: Proposed` keeps this non-blocking, but it must close before D060 is Accepted or
cited.

**SiteHours.24h now requires a migration.** Per the 2026-09-02 correction to D061 rule
1a, the continuous-open state is forbidden by `ck_store_opening_hours_open_times`, not
merely unused. Rule 1a's three-state shape must land on **both** request and response
paths together per engineering constraint 2, both duplicated readiness predicates must
be updated per engineering constraint 7, and existing `00:00-23:59` site data is
ambiguous and must not be repaired by inference — confirm per site with the operator.

**H116, H117, H118 and H119 are logged and not folded in.** None was a Coverage.1bB
dependency. H117 was reframed in this phase — the silent-typo risk it described is
closed, and what remains is an affordance gap. H116 was extended, and H119 records a
helper-text defect on the employee availability form.

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

### Locked decisions that govern this phase

Read `DECISIONS.md` before drafting. D048 in particular: availability is person-scoped on
`user_id`, and admin replace-week is authoritative and overwrites employee-set rows.

## After Availability.1

- **Coverage.1b** — overnight and 24-hour operation. ✅ **Complete 2026-09-02**
  (1bA, 1bB-1, 1bB-2a, 1bB-2b). The first customer runs a mix of 24-hour and
  non-24-hour sites under one tenant. 24-hour operation was unrepresentable at three
  layers — store opening hours, coverage templates, and availability — all blocked by the
  same `close_time > open_time` constraint, recorded as H101. Coverage templates and
  availability are now unblocked; **store opening hours remain, and are SiteHours.24h.**
  D057 rule 6 had to be adjudicated as an unconditional cross-midnight fail-closed
  because the intended site-dependent rule needed a 24-hour indicator that did not
  exist; D061 superseded it once the representation existed.

Not yet scheduled, in no fixed order:

- **H097** — Weekly rota mobile layout. The rota surface still overflows horizontally.
- **Sales data integration** — blocked on a real export from the customer.

## Locked corrections

Settled after real cost. Do not reopen.

- **Store model.** Separate sites are stores under one tenant, not work areas
  inside one store. Vachan's updated customer context (2026-09-17) is one 24-hour
  site and one non-24-hour site. `work_area_id` remains nullable and tag-only.
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
- **CI is green except the npm audit.** At `978c66f`, backend checks, frontend
  checks, the secret scan and the Python dependency audit all pass; `pip-audit`
  reports no known vulnerabilities and one ignored, the `PYSEC-2026-1325`
  acceptance recorded in H147 R-2. The npm dependency audit now **executes** —
  that is H149's repair, and its proof — and **fails**, on 6 vulnerable
  packages. That is H150, open and not restated here. Under H147 R-3 as amended
  it does not block Q.5.3a-1. The full backend
  suite at the Login.1 checkpoint is 1075 passed, 0 failed, 6 skipped. H090 was
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
export TOTP_ENCRYPTION_KEY=$(openssl rand -base64 32)
docker compose -f infra/docker-compose.yml build api
LOCAL_EMAIL_BACKEND=local_smtp docker compose -f infra/docker-compose.yml --profile mailbox up -d --force-recreate api mailpit
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc 'alembic -c apps/api/alembic.ini upgrade head'
```

**Test suite.**

```bash
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc "PYTHONPATH=/app pytest apps/api/tests/ -q"
```

Expected: 1120 passed, 0 failed, 6 skipped. The command now requires `ENV`; the
Compose `api` service supplies `development` and the test bootstrap overrides it
to `test` before the application is imported.

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

At this checkpoint: branch `main`, HEAD `0be2084` before this documentation
commit, working tree clean. Re-inspect rather than assuming; docs commit
separately by convention.

H154 is complete under D069. The next gate is not chosen; the open items are
listed under "Just completed: H154" above. H068's deployment work is not
released; inspect its entry before drafting. The step-up draft remains
unaccepted and must take a D-number above D069.
Before eventually implementing it, confirm the free identifier, current gated
actions, endpoints and existing `require_sensitive_admin_action` callers from
the terminal. Q.5.3c follows an accepted decision.

Grep the code. Do not trust this document, older PRDs, or an assistant's uploaded
copies.
