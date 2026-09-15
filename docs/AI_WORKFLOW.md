# AI Workflow and Engineering Practice

Durable practices for working on this repository with AI assistance. Each rule here was
learned from a specific, costly failure in this project. The context matters as much as
the rule, so it is recorded alongside.

This document is permanent. Session-specific context belongs in `docs/HANDOVER.md`.

## Collaboration model

Four-party assistant workflow, with Vachan as the sole adjudicator:

| Participant | Role |
| --- | --- |
| Claude app | Advisory, governance and prompt drafting. Writes no repository facts. Every prompt carries PASTE INTO, MODEL, EFFORT, PURPOSE and WHY. |
| ChatGPT panel (VS Code) | Repository fact verifier and diff reviewer, with repo access. Answers factual questions before drafting begins. Clean tree, states HEAD, findings only, never redrafts, never adjudicates. |
| ChatGPT app | Blind adversarial reviewer. No repo access. Attacks the prompt as an artifact, not the facts. |
| Codex | Implementer and terminal executor. Halts on divergence rather than self-resolving. |
| Vachan | Sole adjudicator, committer and pusher. |

Sequence: Claude identifies what it does not know and issues a panel query in
the same turn → panel establishes facts → Claude drafts on facts → ChatGPT app
attacks the artifact → Claude responds independently → Codex implements → panel
reviews the diff → Vachan adjudicates and commits.

Record: v7 of the D067 + H069 prompt survived four blind review rounds and still
produced two Codex halts, both of which improved the phase. Execution found more
defects than argument did.

Never give Codex an intermediate or unreviewed prompt. One final agreed prompt only.

## Cardinal rule: inspect before asserting

Grep real schemas, routers and data before trusting documentation, memory, or an earlier
message in the same conversation.

This project has repeatedly had live schema diverge from what docs implied. Examples that
cost real time:

- A column named `day_of_week` was assumed on `availability_entries`. It does not exist.
- `staff_profiles` was assumed to have `site_id`. It has `store_id` only.
- Pay rates were proposed as tenant-level. `staff_profiles` already had `hourly_rate` and
  `pay_type` per employee.

## Run the aligned query before theorising

When debugging, check the data that would confirm or kill a theory **before** proposing
the theory.

During one session, several wrong diagnoses were proposed for an empty recommendation
draft: an empty candidate list, a non-existent `site_id` column, a timezone boundary bug.
Each was eliminated by data that could have been queried first. The actual cause was
mundane: a snapshot created before its inputs were ready.

Inspect first, then theorise. Not the reverse.

## Design-critical facts come from the terminal

A panel report is a model's summary of the repository, and it can be wrong in a
way that looks exactly like being right.

Record: on 2026-09-15 a panel report quoted verbatim, line-numbered code for
recovery-code generation, `RECOVERY_CODE_ALPHABET` and
`RECOVERY_CODE_LENGTH = 12`, that does not exist. The real generator is
`secrets.token_urlsafe(24)`: 32 case-sensitive characters. An approved UX
design, a committed backlog entry (H173 at `870405a`), a blind review and a
Codex implementation were all built on it. Codex halted on the divergence.
Shipped, the change would have blocked every valid recovery code.

Rule: any fact that a design, a user-facing string, a validation rule, or a
backlog entry's Fix depends on is confirmed by a command Vachan runs in his own
terminal, with the output pasted verbatim, before drafting on it. Claude names
those facts and supplies the command.

Panel reports remain the tool for locating code, enumerating callers, and diff
review. An implementer halt that contradicts a panel report is evidence, not
noise.

## Rebuild the container before browser verification

After any backend phase, rebuild and force-recreate before testing in a browser.

```bash
docker compose -f infra/docker-compose.yml up -d --build --force-recreate api
docker compose -f infra/docker-compose.yml run --rm api \
  sh -lc 'alembic -c apps/api/alembic.ini upgrade head'
```

A stale container caused a full round of false 422 and 404 diagnosis during CoverageUI.1.
The code was correct. The browser was talking to an older API than the repository.

If a request fails with a contract error, check the live OpenAPI and container freshness
before concluding the frontend contract is wrong.

## Use `git add -N` before approving a commit

`git diff` and `git diff --stat` do not show untracked files. On a phase that adds new
modules, the majority of the new code can go unreviewed.

```bash
git add -N <new files>
git diff --stat
git diff -- <new files>
```

This was missed once on a phase where seven new files, including a migration, a router
and two test files, were nearly committed unread.

## Verify the staged set, not just the diff

`git add -N` surfaces untracked files. It does not confirm that tracked
modifications were staged. `git commit` without `-a` commits the index only, so a
file that was edited but not added is silently excluded, and the commit message
becomes the only record that it should have been there.

Before committing, confirm the file count:

```bash
git diff --cached --stat
git status --short
```

Every file named in the intended commit message must appear in `--cached --stat`,
and the count `git commit` reports must match the intended one.

On the D067 + H069 documentation commit, four governing documents were modified
but unstaged. The commit reported `9 files changed` where thirteen were intended,
and its message described content it did not contain. `git diff --cached --` was
run twice against one of the missing files and returned empty output both times;
the empty output was read as no news rather than as the answer.

## Prompt structure for Codex

Every implementation prompt should contain:

- A mandatory **Step 0 inspection** with explicit halt-and-report on divergence.
- **Locked decisions** stated so they cannot be reinterpreted.
- **Non-negotiables** including isolation, RBAC and audit requirements.
- **Files likely to change.**
- **Required tests**, naming the dangerous cases specifically.
- **Acceptance criteria.**
- **Validation commands.**
- An explicit **what not to do** list.
- **No auto-commit. No auto-push.**

Step 0 has repeatedly paid for itself. It has surfaced real error codes that differed
from assumptions, confirmed enum mappings, and located existing canonical sources that
would otherwise have been duplicated.

## Review gates after Codex reports

- Read the **migration before the logic**.
- Surface **untracked files** with `git add -N`.
- Grep the diff for the **specific risk** the phase introduced, for example `db.delete(`
  where soft-supersede was required.
- Verify the **one test that proves the dangerous case is dead**, rather than trusting a
  green summary.
- Confirm scope: no backend change in a frontend phase, no engine change in a UI phase.

## Documentation discipline

Keep documentation and implementation in separate commits.

Update durable documents first, then write the handover last. A handover must never
substitute for updating `IMPLEMENTATION_STATUS.md`, `DECISIONS.md` or
`HARDENING_BACKLOG.md`.

After committing documentation changes, re-upload the affected documents to any AI
project knowledge base. Committing them to the repository does not update an assistant's
uploaded copies, and stale project knowledge has caused avoidable rework.

## Testing depth

Light smoke test before committing a phase. One thorough end-to-end pass after a feature
is complete, not after each half.

CoverageUI.1 received a fourteen-phase isolated verification pass. It did earn its keep,
catching a stale container, a capability gap and a mobile layout problem. But a short
smoke test catches most of what a long pass catches, at a fraction of the cost. Depth
should scale with risk, not with habit.

## Vocabulary discipline

Product concepts must not blur in the UI.

Coverage rules are **staffing demand rules**, not shifts. Shifts are what Generate Week
produces from them. If the UI calls a rule a shift, managers will expect editing one to
change an existing rota.

This restriction governs system copy, component names and variable names. It does not
govern text a manager types into a free-form label field.

## Safety defaults

- No auto-commit. No auto-push.
- One explicit step at a time, with stop points before destructive or irreversible
  actions.
- Warnings are informational and non-blocking unless a decision says otherwise.
- Preserve tenant isolation, site isolation, RBAC and audit logging in every phase.
- Alembic migrations only. No `create_all`.
- Additive phases. No architecture redesign without explicit agreement.

## Time and date conventions

### Scheduling times are site-local wall-clock

All scheduling times — coverage template `TIME` values, `Shift.start_at` / `end_at`, and
availability `start_time` / `end_time` — are site-local wall-clock times. Timestamps stored
in `TIMESTAMP WITH TIME ZONE` columns carry a `+00:00` label that is storage notation, not
a conversion.

Do not introduce timezone conversion into any of these paths. Every writer currently
agrees, and the correctness of the whole scheduling chain depends on that agreement. A
single converting writer would silently shift every BST-period time by an hour.

See D054 for the full decision, its assumptions, and the exit condition that triggers real
timezone support.

### Test dates must be relative, never absolute

Do not write absolute calendar dates into test fixtures. Derive dates from `date.today()`.

Absolute dates are future-proof only until real time crosses them. H090 was caused by two
such dates sitting inert for months, then failing simultaneously once they fell into the
past — and the cause was initially misattributed to an unrelated identity seam, costing an
investigation branch.

Where a test needs a lead time against a configured threshold, compute it from the setting
rather than assuming a value. See H098 for the remaining exposure.

---

## Model Routing Policy

**Status:** Active
**Date:** 2026-09-11
**Scope:** Every prompt Claude chat hands to Vachan for execution elsewhere.

This is a workflow convention, not a product decision. It does not take a
D-number. It lives here because a convention that survives only in a chat
session does not survive the session.

---

## 1. Routing header

Every prompt Claude produces carries this header. No prompt ships without it.

```
### PASTE INTO: [exact surface]
### MODEL: [exact picker string]
### EFFORT: [exact slider string]
### PURPOSE: [task class from the table below]
### WHY: [one line]
```

`MODEL` and `EFFORT` use the literal strings shown in the interface. They are
never paraphrased, abbreviated, or replaced with API-level names. If Claude is
unsure of the exact string for a surface, it asks rather than guesses.

---

## 2. Confirmed literal strings

### Codex / ChatGPT panel in VS Code

Model picker (`Select model`):

```
GPT-6 Astra
GPT-5.6 Sol
GPT-5.6 Terra
GPT-5.6 Luna
GPT-5.5
```

Effort slider (`Select effort`), ascending:

```
Light
Medium
High
Extra High
Ultra
```

The API names these levels `low`, `medium`, `high`, `xhigh`, `max`. **Those are
not the strings in this interface and must never appear in a routing header.**
`Low` and `xhigh` in particular have already been introduced once by a review
pass and corrected.

### ChatGPT app (chat surface, Plus plan)

`GPT-5.6 Sol` only, at `Medium` or `High`.

Plus has no Pro option in the chat picker, so GPT-6 Pro — the chat-surface
packaging of Astra — is unavailable there. This is a plan gate, not a rollout
queue. Astra is available on Plus **in Codex and Work**, which is the surface
the table below routes to.

Codex allowance is separate from chat allowance. Heavy work belongs in Codex
for that reason as well as the capability one.

---

## 3. Governing rule

> Always select the lowest effort expected to complete the task reliably.
>
> Escalate for reasoning complexity, ambiguity, interacting invariants, or the
> failure of a cheaper pass. **Never escalate because the subject matter is
> important.**

Reading `DECISIONS.md`, locating a route, checking a schema, or confirming a
test exists does not become high-effort work because the feature it eventually
serves touches auth, tenancy, or migrations. The task class is what is being
asked, not what it is for.

---

## 4. Routing table

| Task class | Surface | MODEL | EFFORT |
|---|---|---|---|
| Mechanical retrieval — read a file, grep a symbol, confirm a `path:line` anchor, list callers | Codex panel | `GPT-5.6 Luna` | `Light` |
| Local implementation — intended behaviour and affected seam already established | Codex | `GPT-6 Astra` | `Light` |
| Multi-file implementation — reasoning across files, invariants, tests, or interacting behaviour | Codex | `GPT-6 Astra` | `Medium` |
| Diff review, engineering-level adversarial pass | Codex panel | `GPT-6 Astra` | `Medium` |
| Architecture, tenancy, auth and security, destructive migrations | Codex panel | `GPT-6 Astra` | `High` |
| Unresolved contradiction, or exceptionally difficult investigation after a cheaper pass failed | Codex panel | `GPT-6 Astra` | `Extra High` |
| Independent reasoning-soundness review, without repo access | ChatGPT app | `GPT-5.6 Sol` | `High` |
| Open-ended discussion, planning, drafting | ChatGPT app | `GPT-5.6 Sol` | `Medium` |

`Ultra` is never routed to directly. It is reachable only as a second
escalation, after an `Extra High` pass has run and failed to resolve the
question, and it requires Vachan's explicit instruction in the specific case
with the reason recorded in the session. Ultra reached by any other path
recreates the problem this policy exists to solve, one row further down.

`GPT-5.6 Terra` and `GPT-5.5` are deliberately unrouted. Terra was removed
because "retrieval requiring judgement" is not a mechanical predicate and put an
ambiguous call back into every routing decision.

### The Luna / Astra boundary

> Use `GPT-5.6 Luna` at `Light` only when the requested output can be produced
> by locating, extracting, enumerating, or reporting repository facts **without
> deciding what those facts mean**. The moment interpretation, reconciliation,
> design judgement, or implementation reasoning is required, use `GPT-6 Astra`.

Luna:

```text
show lines 210-240 of apps/api/routers/staff.py
find every caller of this helper
which migration contains this constraint?
list the tests mentioning preferred_off
what is HEAD?
```

Astra:

```text
does this implementation violate D067?
are these two callers semantically equivalent?
what needs changing here?
is this migration safe?
does this test actually prove the invariant it claims to?
```

The dividing line is the verb. Locate, extract, enumerate, report — Luna.
Judge, reconcile, decide, verify — Astra.

### Why the repo side keeps two models

Effort is one axis; model is the other, and the model axis is the larger lever.
Mechanical retrieval is the highest-frequency query class in this workflow.
Routing all of it to the frontier model returns most of the cost this policy
exists to control, however low the effort setting.

The competing view — one model, no picker-switching, a high quality floor — was
considered and rejected on frequency grounds. Revisit if Luna produces an anchor
that does not match the file, which is the failure that would invalidate the row.

---

## 5. Why the ladder sits where it does

Effort is a cost curve with diminishing returns, not a quality dial. Published
per-task figures across Astra's five levels show quality index rising 49 → 52 →
53 → 54 → 55 while cost rises roughly fourfold. The first step up buys three
points. Every step after buys one.

OpenAI's own documentation states that lower effort does not mean lower
capability across models — Astra at its lowest effort can outperform Sol at
High — and that higher effort consumes more allowance without reliably
producing a better result.

### What the lower setting costs

A deep review at low effort may return fewer findings, or rank them worse. In
one documented read-only code review, the lowest setting found five real issues
in sixty seconds; the highest found seven in seven and a half minutes and
re-ordered them. The two extra findings were real.

### Why that is acceptable here

This repository's loop already has a second net. Every diff is reviewed by
Vachan before commit. Adversarial passes are separate steps, not a single shot.
A finding missed at `Medium` has another chance at human review — which is how
D059 was caught.

Reliability first, efficiency second. This ladder does not trade the first for
the second; it stops paying for headroom that measurement says is not being
used.

---

## 6. Standing rules

1. **The slider is sticky.** It holds its last position across messages and
   sessions. A header specifying `Light` does nothing unless the slider is
   actually moved. Check it before sending, every time.

2. **Independence is preserved by construction.** Prompts sent to GPT carry the
   diff, the file anchors, and the question. They never carry Claude's
   rationale, Claude's expected answer, or any framing that indicates a
   preferred conclusion. The ChatGPT app row exists specifically so that
   reasoning-soundness review happens in an environment that cannot see the
   repo and did not produce the reasoning under review.

3. **Escalate only on unresolved conflict.** A pass that returns a clean result,
   or a result Vachan disagrees with, is not grounds for escalation. A pass that
   returns two mutually incompatible findings, or cannot resolve a contradiction
   in the evidence, is. The escalation prompt restates the conflict neutrally.

   Escalation is graduated: `High` → `Extra High` → `Ultra`. No step is skipped.
   Each step requires the previous one to have run and failed.

4. **Claude routes; Vachan overrides.** Claude selects the model and effort for
   every prompt it produces. Vachan may override any selection without
   justification. An override that recurs is a signal the table is wrong and
   should be amended here.

---

## 7. What not to do

```text
do not run Ultra as a default operating position
do not reach Ultra without a failed Extra High pass first
do not raise effort in place of narrowing the prompt
do not send mechanical retrieval to Astra
do not write API effort names (low, xhigh, max) into a header
do not paraphrase MODEL or EFFORT strings
do not escalate because the first answer was unwelcome
do not include Claude's reasoning in a prompt destined for GPT
```

---

## 8. Amendment

Amendments are recorded at the end of this section, dated, rather than rewritten
in place — matching the convention used in `DECISIONS.md`. The interface strings
in §2 are the most likely thing to go stale; re-verify them against the live
picker whenever a routing header produces a setting that does not exist.
