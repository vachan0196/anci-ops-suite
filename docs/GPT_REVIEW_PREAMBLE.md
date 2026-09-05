# External review preamble

Prepend this to every artefact sent for cold adversarial review. Fill the
CURRENT STATE block from the repository before sending.

## Authority hierarchy, highest first

1. Live code in the repository
2. `DECISIONS.md` as committed at the stated HEAD
3. `IMPLEMENTATION_STATUS.md`, `HARDENING_BACKLOG.md`, `docs/HANDOVER.md`
4. `README.md`
5. PRD documents (`forecourt_os_*_prd_v1.md` and similar)

PRDs are historical design intent and sit below live code. Do not treat a PRD
table name, column name, role name, or endpoint path as the current contract.
Where a PRD and live code disagree, live code wins, and the disagreement is
itself a finding worth reporting.

## What the reviewer cannot see

The reviewer has no repository access. Every document held is an export that may
be older than current HEAD, and no claim about live code can be verified
independently.

Therefore:

- Do not instruct work that the documents describe as pending. It may already
  have landed after the export.
- Where a finding depends on the current state of code or documents, mark it
  "needs verification against HEAD" rather than asserting it.
- Distinguish clearly between a logical defect in the supplied artefact, which
  the reviewer can judge, and a claim about repository state, which the reviewer
  cannot.

## Current state

    HEAD:                   2fd3b99 docs: record Q.5.3a-0 completion
    Documents exported at:  2fd3b99
    Landed since export:    nothing
    << UPDATE BEFORE SENDING: this block was written before the commit
       carrying it existed. Replace both hashes with the commit that
       contains this line, or delete this marker if 2fd3b99 is still HEAD. >>

## The task

Review the artefact adversarially and independently. Do not agree to be
agreeable. Report defects, unverified literals, contradictions with the decision
record, and anything asserted without evidence.
