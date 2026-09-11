# Model Routing Policy

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
