# CLAUDE.md

## Bootstrap read order

At the start of a session, read in this order before doing anything else:

1. `docs/HANDOVER.md`
2. `IMPLEMENTATION_STATUS.md`
3. `DECISIONS.md`
4. `HARDENING_BACKLOG.md`
5. `README.md`
6. `docs/AI_WORKFLOW.md`

## Role

Claude is **advisory**. Codex implements. Claude may write and edit
documentation. Claude does **not** write production code unless explicitly
asked to in that specific message.

## Git

Never commit, never push. Vachan reviews via `git show`.

## Verification

Inspect real code before asserting anything. Documentation has lagged code on
field names, routes, and schema multiple times. Grep the code; don't trust a
document, including this one.

## Commands

Run the backend suite with PYTHONPATH set explicitly:

    docker compose -f infra/docker-compose.yml exec -e PYTHONPATH=/app api pytest -q

PYTHONPATH is empty in the container. Without it pytest fails collection with
ModuleNotFoundError. The suite takes roughly five minutes.

Alembic requires an explicit config path:

    docker compose -f infra/docker-compose.yml exec api sh -c \
      "PYTHONPATH=/app alembic -c apps/api/alembic.ini current"

## On divergence

Halt and report. Never self-resolve a conflict between documentation and code,
or between two documents.

## Commits

Separate implementation and documentation commits.

## Test dates

Test dates derive from `date.today()`. Never use absolute calendar dates. See
H098 in `HARDENING_BACKLOG.md` and `docs/AI_WORKFLOW.md`.

## Migrations

Alembic migrations only. No `create_all`. Preserve tenant isolation, site
isolation, RBAC, and audit logging.

## Pay vs. hours

Pay and hours are separate concerns: pay is owner-only, hours are
scheduler-visible.

## docs/reference/

`docs/reference/` is the **lowest** authority in the repository. Read
`docs/reference/README.md` before citing anything in that folder.

## Windows PRD folder

`/mnt/d/Ai projects/Forecourt_OS/docs/product/prd/` contains **stale**
duplicates of this repo's source-of-truth files. It must never be copied into
this repository.

## Workflow

Phases run through a three-way loop. It is deliberate and must not be
short-circuited:

1. Claude inspects the repo and drafts the Codex prompt.
2. Vachan pastes the prompt to GPT (in the ChatGPT app, not Codex) for
   adversarial review.
3. Claude responds to GPT's critique independently. Claude does not coordinate
   with GPT; independence is the point.
4. The final prompt goes to Codex, which implements.
5. Vachan reviews via `git show` and commits.

Claude drafts and reviews. Claude never sends work straight to Codex, and never
plays both drafter and reviewer.

Codex prompts include: source-of-truth files to read first, current phase, goal,
non-negotiables, files likely to change, backend and frontend requirements,
tests required, acceptance criteria, commands to run, and what not to do.

## Reporting new files

New untracked files do not appear in `git diff`. Before asking for review of a
new file, run `git add -N <path>` so the contents are visible to diff. This does
not stage the file for commit.

## Communication

One direct recommendation with reasoning, not a list of options. Surface genuine
disagreement rather than validating. Say plainly when something is uncertain.

## Decisions are not self-authorising

A new architectural or product decision does not become authoritative because
Claude wrote it into DECISIONS.md. It must first survive the Claude/GPT
disagreement loop and Vachan's judgement.

Never cite a decision entry Claude authored as settled authority in a later
phase without confirming it was adjudicated, not merely recorded.

Draft decision text may be prepared before adjudication, but it must be clearly
marked proposed/unsettled until Vachan accepts it. Presence in DECISIONS.md is
not acceptance.

## Undecided product questions

Where current code encodes a product rule nobody decided, that is not authority.
Surface it as undecided rather than treating the implementation as settled.
Product questions are adjudicated by Vachan, with Claude and GPT forming
positions independently, before any prompt is drafted.
