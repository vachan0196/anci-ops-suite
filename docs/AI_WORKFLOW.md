# AI Workflow and Engineering Practice

Durable practices for working on this repository with AI assistance. Each rule here was
learned from a specific, costly failure in this project. The context matters as much as
the rule, so it is recorded alongside.

This document is permanent. Session-specific context belongs in `docs/HANDOVER.md`.

## Collaboration model

Three assistants, deliberately kept independent:

- **GPT** drafts prompts and runs adversarial review.
- **Claude** cross-checks independently and gives a second opinion.
- **Codex** implements.

Claude's independence from GPT is intentional. The point is to surface blind spots, so
genuine disagreement should be stated rather than smoothed over. Two rounds of
adversarial review on Coverage.1a caught a double-staffing bug and a hard-delete crash
that would both have reached production.

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
