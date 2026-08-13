# Availability — product area design (v3)

**Status: PROPOSED. Not adjudicated. Not authoritative.**

**v3** — incorporates GPT's narrow second pass. All four fencing points passed; three wording and
semantic corrections applied. One item remains for Vachan's adjudication: whether
`available_extra` receives a ranking bonus (section 4).

Per the project's standing rule, a design does not become authoritative because an AI wrote
it down. It must survive independent review and Vachan's judgement.

This revision incorporates GPT's cold review of v1 and the subsequent exchange. Sections
marked **CORRECTED FROM v1** record where v1 was wrong, so the error is visible rather than
quietly removed.

**This version is for a narrow second pass only**, on four points listed in section 11 — not
another broad architecture review.

---

## 1. The problem

Rota generation needs to know when each person can work. The system has one concept for this:
a weekly availability row marking a date (optionally with a time window) as `available`,
`available_extra`, `preferred_off`, or `unavailable`.

That single concept does two jobs and cannot do both:

- **What someone agreed to work when hired.** Durable, negotiated, changes rarely.
- **What someone can do this particular week.** Volatile, declared, changes constantly.

The system cannot distinguish "I can only ever work mornings" from "I'd prefer mornings this
week."

### The scenario that exposed it

If every employee declares morning-only availability, evening shifts have no eligible
candidates. The engine silently returns fewer assignments than there are shifts. The manager
sees empty cells and no explanation.

The only remedy today is admin replace-week, which per D048 **wipes the week and overwrites
employee-set rows**. The employee's declaration is not overruled — it is deleted.

### How the operator solves it today

From Vachan's direct operational experience at a multi-site forecourt operator:

> Two staff can only work mornings. Two others are flexible and can work mornings or nights.
> The manager assigns shifts on the basis of that understanding.

That understanding is real and already exists. It was established at hiring: *"these are the
timings we have available, what are you available for?"* It is simply not written down. It
lives in the manager's head.

**The proposal is not adding a new concept to the product. It is recording something that
already exists in the business but not in the software.**

---

## 2. Verified current state

Established by direct code inspection on 2026-08-11. Facts, not claims.

### Schema

`availability_entries` already has nullable `start_time` / `end_time` and two partial unique
indexes: one for full-day rows (both NULL), one for timed rows (both NOT NULL). **No migration
is required for timed availability.**

A half-open row (exactly one set) matches neither index and has no check constraint.
`_validate_availability_payload` is the only guard. Covered by tests as of H088a (`eb6840c`).

Validation also rejects `end_time <= start_time`. **Consequence: overnight availability
(22:00–06:00) is currently inexpressible.** This was not identified in v1 and is material to
Q2.

### Matching logic

`_availability_covers_shift` is duplicated **byte-identically** in
`apps/api/routers/shifts.py:175` (manual assignment validation) and
`apps/api/routers/rota_recommendations.py:216` (recommendation engine):

```python
for entry in entries:
    if entry.date != shift_date:
        continue
    if entry.start_time is None and entry.end_time is None:
        return True
    if not shift_starts_and_ends_same_day:
        continue
    if entry.start_time is not None and entry.end_time is not None:
        if entry.start_time <= shift_start_time and entry.end_time >= shift_end_time:
            return True
return False
```

Both callers pre-filter with `type.in_({"available", "available_extra"})`.

### What that code implies, none of which was ever decided

1. **Full containment required.** Available 09:00–17:00 does not cover an 08:00–16:00 shift.
2. **Overnight shifts match full-day rows only.** Timed entries are skipped for any shift
   crossing midnight. Entries are matched on the shift's *start* date, so the second calendar
   day is never consulted.
3. **`unavailable` rows are never loaded.** Inert, not decisive. A date with both `available`
   and `unavailable` resolves as eligible.
4. **`preferred_off` has no effect on recommendations.** Never loaded.

These are encoded rules nobody chose. They are artefacts of implementation.

### Other relevant facts

- The employee portal **already exists** (Phase 17). Both writers already write to the same
  table. This is a live divergence, not a future design problem.
- D048: availability is person-scoped on `user_id`. Admin replace-week is authoritative and
  destructive.
- D054: all scheduling times are site-local wall-clock; the `+00:00` on timestamp columns is
  a storage label, not a conversion.
- First customer: three separate stores under one tenant, single timezone, shared staff.
- Coverage.1b (overnight coverage) is on the roadmap. Coverage template validation rejects
  `end_time <= start_time`.
- H094 (multi-store assignment and cross-store hour aggregation) is documented, not built.
  The current data model cannot correctly represent "works Store A and Store B but not
  Store C."
- **Soft caps deprioritise; they do not exclude.** HourTarget is the hard limit. Warnings are
  non-blocking and informational; no create, update, or publish operation may be gated on
  them. Locked.
- Site isolation is a locked architectural property.
- **The `manager` tenant role does not exist.** The implemented set is `owner | admin |
  member`. "Site manager" is an operational term only; no implementation may assume a
  `manager` RBAC role.

---

## 3. Proposed model — two layers plus an output

**CORRECTED FROM v1.** v1 called this a three-tier model with the rota as tier 3. The rota is
not a tier of availability; it is an output produced from demand plus constraints. The
distinction matters because feasibility reporting must work before the standing layer exists.

```text
Standing scheduling agreement          (does not exist yet)
              +
Weekly declaration / exceptions        (exists today)
              +
Coverage demand and other constraints
              ↓
        Rota / feasibility
```

### Layer 1: standing scheduling agreement

Set during hiring, admin-side, changes rarely.

- A recurring pattern of weekday plus time intervals.
- With day-level rules: "Wednesdays, mornings only" — a permanent recurring rule, not a
  one-off.
- Scoped to **(user, site)** — see section 6.
- **Visible to both parties.** The employee sees their own agreed pattern in the portal; the
  admin sees the same record.

**CORRECTED FROM v1.** v1 described this as an *envelope* that weekly declarations operate
*within*. That is wrong in both directions:

- Standing "mornings or evenings" plus weekly "mornings only" is **inside** the pattern but
  narrower — not outside it, as v1 claimed.
- Standing "Monday mornings only" plus weekly "also free Monday evening" is an employee
  volunteering extra flexibility. That is precisely what `available_extra` is for, and v1's
  envelope model would have rejected it.

Layer 1 is therefore a **normal agreed baseline**, not an absolute envelope. Weekly
declarations may narrow it temporarily, confirm it, express preference within it, or expand
it temporarily. **The composition rule is undefined and is now Q8.** Without Q8 the two-layer
model is not actually specified.

### Layer 2: weekly declaration

What exists today. Employee-declared, week-scoped, volatile.

### Why mutual visibility matters

From Vachan's description:

> The employees are also aware of what availability they told the admin, and the admin also
> knows what availability the employees told.

Both sides seeing the same record is what makes the rest work. The employee declares against
a known baseline rather than guessing; disputes have a written reference.

### What the standing layer does and does not solve

**CORRECTED FROM v1.** v1 implied the standing layer resolves the unrunnable-business
scenario. It does not.

If all ten employees genuinely have standing agreements saying mornings only, and the business
needs five evening staff, the standing layer explains **why** the business cannot be staffed.
It does not make it staffable.

What it adds is the ability to distinguish:

- **Temporary weekly shortage** — standing pattern covers evenings, this week's declarations
  don't.
- **Structural recruitment gap** — no standing pattern covers evenings at all. The owner needs
  to hire, and the software should say so.

The actual fix for silent failure is **feasibility reporting**, which is orthogonal and does
not depend on the standing layer. See section 5.

---

## 4. Declaration semantics — the two-axis matrix

The central correction from review. v1 asked "is declared availability a constraint or a
signal?" as if all declarations had one strength. They do not: four types already exist and
their names imply different semantics.

Two independent questions must be answered separately, or they get settled in the same
paragraph again:

1. **What does this declaration type mean?**
2. **When two authorities provide competing declarations, whose effective state wins?**

### Axis 1 — type strength

| Type | Strength | Automatic assignment | Meaning |
|---|---|---|---|
| `available` | hard positive | Eligible | Employee can work |
| `available_extra` | hard positive, exceptional | Eligible. **No ranking bonus proposed** — see below | Flexibility beyond normal pattern |
| `preferred_off` | soft negative | Eligible, deprioritised | Prefers not to; not a prohibition |
| `unavailable` | hard negative | Not eligible | Explicitly cannot work |
| no applicable row | — | Not eligible **in this layer** | No declaration at all — a different business fact from `unavailable` |

### Does `available_extra` rank ahead of `available`?

D048 explicitly deferred whether `available_extra` and `preferred_off` affect scoring, so this
is genuinely open. **Proposed: no ranking bonus in Availability.1.** Retain `available_extra`
as a distinct hard-positive type carrying its "extra" provenance, but do not preferentially
schedule someone merely because they volunteered beyond their normal pattern. The standing
layer can give "extra" richer meaning later.

Two arguments beyond simplicity. First, a ranking bonus creates a perverse incentive: the
people who volunteer flexibility get scheduled most, so in a site with two flexible and two
morning-only staff, the flexible pair absorb the load. Second, under ERA 2025 the hours
actually worked over a reference period drive guaranteed-hours entitlement — so systematically
favouring the flexible employee has a downstream contractual consequence nobody chose.

**This is the one item flagged for adjudication rather than proposed as settled.**

`preferred_off` reduces desirability without removing eligibility. If Alice is `available` and
Bob is `preferred_off` and both are otherwise suitable, recommend Alice. If only Bob can cover,
recommend Bob with the preference shown.

**Consequence:** if Availability.1 surfaces `preferred_off` in the UI while the engine ignores
it, the UI makes a promise the engine does not honour. Either implement its meaning or do not
expand that UX.

### Axis 1 — same-source overlap combinations

Genuine contradiction is narrower than v1 and GPT's first review both assumed. Only
hard-positive against hard-negative is incoherent.

Coherence alone is not enough — each combination must also state its **effective outcome**, or
the matcher can return on the first positive row it happens to read and silently ignore
`preferred_off`. Compatible signals compose by effective strength, not by row order.

| Overlapping pair, same source | Verdict | Effective outcome |
|---|---|---|
| `available` + `preferred_off` | Coherent — "I can work, but prefer not to in the afternoon" | Eligible, deprioritised |
| `available_extra` + `preferred_off` | Coherent | Eligible, deprioritised |
| `preferred_off` + `unavailable` | Coherent — a preference and a hard exclusion can coexist | Not eligible for automatic assignment; `preferred_off` remains explanatory metadata |
| `available` + `unavailable` | **Contradiction** | Reject the declaration at write time |
| `available_extra` + `unavailable` | **Contradiction** | Reject the declaration at write time |
| Multiple non-conflicting windows on one date | Allowed | Compose normally. Multiple windows and contradiction are different problems |

Proposed write-time rule:

> A single writer may not create overlapping hard-positive and hard-negative declarations for
> the same availability subject and applicable scheduling scope.

Deliberately not phrased as "person, site, and time interval." D048's canonical availability
identity is person-scoped on `tenant_id + user_id + date + type`; `site_id` is not part of that
identity. Availability.1 should implement the exact scope its live endpoints confirm, rather
than hardcoding a site grain into a generic product rule that later availability sources may
not share.

### Axis 2 — cross-source precedence

**This is where D048 enters, and it must not be settled on axis 1.**

Employee declares `available` 09:00–17:00; admin later writes `unavailable` 13:00–17:00. That
is not corrupted data. It is one authority overruling another, and there may be a legitimate
operational reason.

**This is a future precedence scenario, not a current one.** Under D048 as implemented, those
two records cannot coexist after an admin save, because admin replace-week deletes the employee
rows first. D048 stores `source="admin"` and `source="employee"` precisely so that future
precedence work is possible, while deferring the precedence rules themselves.

**CURRENT (D048, unchanged by this document):** admin replace-week is authoritative and
destructive. The employee's rows for that week are deleted before the admin's are written.
Because of this, cross-source contradiction cannot currently persist in the table.

**PROPOSED TARGET DIRECTION — not adjudicated; implementation timing not approved:**
authority and data deletion are separate concepts. An admin may determine effective scheduling
state without erasing the employee-origin declaration.

Destructive overwrite loses facts the rest of this design depends on: what the employee
declared, when, what the admin changed, why the system treated them as unavailable, and
whether staff and management disagreed. That directly damages the explainability that
feasibility reporting is built on.

**Fencing, which matters more than the target itself:**

- Availability.1 does **not** redesign D048. Retaining both sources with dynamic precedence
  and provenance is its own data-model and lifecycle problem — uniqueness constraints,
  effective-state evaluation, historical retention, API changes, admin UI semantics, and
  probably a migration.
- Availability.1 tests may preserve the current API contract where needed but **must not
  assert that destructive replacement is desirable product behaviour.** Current behaviour is
  not to be canonised as the future semantic rule.
- A dedicated precedence phase is required. It is not scheduled here.

### No-row wording

Scoped deliberately to the weekly declaration layer:

**CORRECTED FROM v2.** The v2 wording said "absence of an *affirmative* applicable declaration
does not establish eligibility." That contradicted the type matrix: `preferred_off` is not
affirmative, yet it does establish eligibility, deprioritised.

> **In the weekly declared-availability layer, no applicable declaration does not establish
> eligibility. An applicable declaration establishes eligibility according to its type
> semantics.**

Weekly layer, explicitly:

```text
available          → eligible
available_extra    → eligible
preferred_off      → eligible, deprioritised
unavailable        → not eligible
no applicable row  → not eligible
```

`no applicable row` and explicit `unavailable` currently produce the same automatic-assignment
outcome, but they remain **different business facts** and must stay distinguishable — for
explanation ("James declared unavailable" versus "James has not submitted availability", which
lead to different managerial actions) and for future composition.

Not "no row always means unavailable." Later, the standing layer may evaluate: weekly
declaration exists → apply weekly semantics; no weekly declaration → consult standing baseline.
That adds a source before the final eligibility decision rather than contradicting
Availability.1.

---

## 5. Feasibility reporting

Raised independently by GPT and **moved earlier in the sequence** than v1 proposed, because it
directly fixes the originating scenario and needs none of the standing layer.

The current failure mode is silence: no eligible candidate means the shift is left unfilled
with no explanation. To a manager that is indistinguishable from broken software.

Proposed behaviour:

- Availability validation answers *"is this a valid declaration?"* — never *"does the business
  still work if we accept it?"* Different layers; merging them turns an HR policy question
  into a validation rule.
- A truthful declaration is never rejected, altered, or silently overridden to make the
  business runnable.
- The engine **leaves the shift unfilled** rather than degrading from "available employee" to
  "some employee." If availability can be silently ignored under pressure, it stops being data
  and employees stop maintaining it.
- The system reports *why* nobody is eligible, per shift and per person.
- Assigning outside declared availability is an explicit, reasoned, auditable override — not
  an automatic fallback.
- Insufficient coverage warns strongly but **does not block publication.** Real operations are
  messy: agency staff, someone calling back, a shift deliberately left open. A hard block would
  make ForecourtOS the reason the week's rota did not go out. Consistent with the locked
  non-blocking-warnings principle.

### Exclusion categories — CORRECTED FROM v1

v1 listed "hours cap reached" as an eligibility reason. That is wrong: the project's locked
rule is that soft caps deprioritise rather than exclude, with HourTarget as the hard limit.
v1 would have turned a non-blocking product rule into a hard scheduling constraint.

Feasibility must therefore use four distinct categories:

| Category | Example |
|---|---|
| Hard exclusion | `unavailable`; no applicable declaration; HourTarget exceeded |
| Soft warning | Over weekly or monthly soft cap |
| Preference | `preferred_off` |
| Eligible | — |

---

## 6. Multi-site

From Vachan's description:

> Every site is independent. Site A's manager communicates with the employee, and Site B's
> manager communicates with the employee as well. They agree what days you work at this site
> and what days at that site.

So the standing agreement is scoped to **(user, site)**. Two independent negotiations. This
matches the locked store model: three separate stores under one tenant, not three work areas
in one store.

### The tension

- **Negotiation is per-site.** Two independent conversations.
- **Obligation is per-person.** Working time limits, rest periods, and guaranteed-hours
  obligations attach to the human.

Concrete failure: Site A agrees Mon–Wed mornings; Site B agrees Tue–Thu evenings. Neither
knows about the other. Tuesday the person is agreed to both, and their total agreed week is far
larger than either site believes. Both sites acted correctly. The system permitted it.

Not hypothetical for the first customer — one tenant, three sites, shared staff is exactly the
configuration where this occurs.

### Is this a site-isolation violation? — CORRECTED FROM v1

v1 asserted that any answer other than "do nothing" is an exception to site isolation. GPT
disputed this and is right.

Site isolation means a site-scoped user cannot access data they are not authorised to see. It
does not mean scheduling logic may never evaluate tenant-wide constraints. A Site A admin
receiving *"this employee has a scheduling conflict elsewhere"* — without site name, times, or
counterparty — is a privacy-preserving derived signal, not cross-site data exposure. An
owner-level aggregate is plainly compatible with an owner who already holds multi-site
authority.

### The real blocker is H094

The project already records that the current data model cannot correctly represent "works
Store A and Store B but not Store C," and that cross-store person-level aggregation is open.

> **Per-site standing agreements for shared staff must not be implemented ahead of the
> multi-store identity and assignment model they depend on.**

Otherwise Availability.2 builds permanent data on an identity grain already known to be
insufficient.

---

## 7. Change lifecycle

Agreements are renegotiated. From Vachan's description:

> I moved to Coalville. I tell my manager my hours are more flexible now, I can work nights.
> They keep it in mind and make the next rota accordingly.

That conversation happens verbally and lives in the manager's memory.

### Both entry routes must exist

- **Employee portal request** — reason, proposed new pattern, effective-from date.
- **Admin direct record** — for the conversation that happens at the counter.

If the only route is a formal portal request, most changes will not be recorded — which is the
current failure.

### Two properties the record needs

- **Effective-from date.** "I can work nights now" — from when? Without it the approver does
  not know which rota it applies to.
- **Supersede, do not overwrite.** The previous agreement is retained, producing a history:
  *hired mornings-only; moved; agreed nights from 1 September.*

### `shift_requests` reuse — CORRECTED FROM v1

v1 stated that pattern changes are structurally the same as leave, swap, and cover requests,
and that `shift_requests` therefore already provides the lifecycle. **That was an assumption
inferred from workflow shape, not from schema inspection.**

Leave, swap, and cover are about specific rota or shift events. Changing a standing work
pattern is closer to changing a workforce agreement, and needs `effective_from`, previous
pattern, proposed pattern, accepted pattern, superseded version, possibly employee
acknowledgement, and history.

Shared pending/approved/rejected states are not sufficient grounds for table reuse. Reuse the
workflow concepts if helpful; **do not assume table reuse until schema inspection proves the
model fits.**

### Provenance — CORRECTED FROM v1

v1 described the standing pattern as a "mutually agreed" record while also allowing the admin
to edit it unilaterally. If an admin edits and the system immediately labels the result
"agreed," nothing proves the employee agreed.

Either capture provenance — initiated by, source (verbal or portal), recorded at, effective
from, employee notified, employee acknowledged — or name it honestly as a
**manager-recorded agreed pattern** rather than claiming the system evidences mutual
agreement. Digital acknowledgement is not required for MVP; the honest naming is.

---

## 8. Compliance framing — CORRECTED FROM v1

v1 referred to "2027 Employment Rights Act guaranteed-hours obligations." That is wrong on
both the name and the certainty.

Verified 2026-08-13:

- The legislation is the **Employment Rights Act 2025**, which received Royal Assent on
  18 December 2025. Implementation is staged across 2026 and 2027.
- The consultation *"Make Work Pay: Ending one-sided flexibility: reforms of zero hours and
  similar contracts"* was published 2 June 2026 and closes **25 August 2026**.
- Guaranteed-hours offers, reasonable notice of shifts, and compensation for shifts cancelled,
  moved, or curtailed at short notice all require secondary legislation. Implementation is
  expected in 2027; **no date is confirmed.**
- The Government is consulting on the low-hours threshold, with options from 8 to 48 hours per
  week and a stated preference of 8–20, and on the reference period, with a stated preference
  of 12 weeks.
- Sources conflict on whether shift-notice and cancellation-payment rights land in October 2026
  or 2027. Do not assert either without checking closer to the date.

**Defensible framing:**

> A durable history of agreed scheduling patterns and shift-notice timestamps may prove useful
> for future compliance and evidence, including forthcoming guaranteed-hours and shift-notice
> requirements. The final regulations and the records they will require are not settled. Legal
> review is required before treating any part of this model as a compliance artefact.

Do not claim this model *is* the artefact the rules will require.

Commercial note, not a claim: a 12-week reference period against an 8–20 hour threshold is the
kind of calculation a rota system can perform and a spreadsheet cannot. That is a sharper story
than "compliance" in the abstract — but it needs a solicitor, not an AI.

---

## 9. Open questions

**Q1 — Containment or overlap.** Current code requires full containment. Proposed position:
keep containment for eligibility, because an employee available 09:00–17:00 genuinely cannot
work all of an 08:00–16:00 shift. Partial overlap remains useful *information* for feasibility
display and for possible future split-shift coverage. Eligibility and useful overlap are
different concepts. Manual assignment validation should use the same rule with an explicit
override path, so the two matchers never disagree.

**Q2 — Overnight.** Proposed: an overnight shift is eligible only when availability
continuously covers the complete shift interval across the relevant calendar dates. Current
behaviour (skip timed entries, match only the start date) should not become the product rule.

**Availability.1 consequence:** because validation rejects `end_time <= start_time`, overnight
availability is inexpressible today. **Do not relax that validation in Availability.1.** Lifting
it would create an intermediate state where the API accepts 22:00–06:00 but the matcher cannot
interpret it. Decide the semantic direction now; implement representation and matching together
with Coverage.1b or a dedicated overnight phase. Do not hack around SQL `TIME` by splitting
rows at midnight.

**Q3 — Contradiction.** See section 4, axis 1. Narrowed to overlapping hard-positive against
hard-negative from the same source.

**Q4 — Declaration strength.** See section 4, axis 1. Type-specific rather than one answer.

**Q5 — Standing pattern shape and validity.** *Two questions, not one.* (a) Pattern shape:
proposed as weekday plus time intervals as stored truth; "mornings"/"evenings"/"nights" may be
UI shortcuts derived from a site's common shift patterns but must not be the canonical database
meaning. (b) Version validity: `effective_from`, `effective_to` or until-superseded, with
historical versions retained rather than overwritten.

**Q6 — Cross-site conflict visibility.** See section 6. Not necessarily an isolation violation.
Blocked on H094 regardless.

**Q7 — Who initiates a change.** Proposed: both. Employee via portal request, admin via direct
record. The distinction between requested, recorded, acknowledged, and approved/effective needs
thought.

**Q8 — How do standing and weekly availability compose?** *The largest open question.* Without
it the two-layer model is undefined. Requires an explicit rule for at least: standing available
+ weekly unavailable; standing unavailable + weekly `available_extra`; standing morning +
weekly `preferred_off` morning; standing morning + weekly available evening; no standing
pattern + weekly available.

**Q9 — What happens to a published rota when the agreement changes?** If Alice has a published
Friday 22:00–06:00 shift and a new standing pattern becomes effective saying mornings only:
the shift must not disappear. Probably becomes a conflict warning. Effective-from may need to
default to the next unpublished scheduling period. **Standing-pattern edits must never silently
mutate published rota truth.**

**Q10 — Scheduling agreement or employment-contract term?** Proposed: call it a *scheduling
agreement* unless legal review says otherwise. ForecourtOS must not accidentally claim that a
screen modifies someone's employment contract — that is a much larger product and legal
commitment.

**Q11 — What is an override?** One consistent definition is needed across: manual assignment
despite `unavailable`; outside the standing pattern; during `preferred_off`; with no
declaration at all. These should probably not all carry the same severity of acknowledgement.

---

## 10. Proposed sequence

**CORRECTED FROM v1.** Feasibility moved earlier; H094 groundwork made explicit.

| Phase | Scope |
|---|---|
| **Availability.1** | Timed weekly declared availability. Type semantics (axis 1). Full containment. `preferred_off` behaviour. Same-source contradiction rules. Declared-layer no-row semantics. Manual override boundary. Retain overnight rejection. Consolidate the duplicated matcher. **No migration required.** |
| **Feasibility.1** | Explain uncovered demand and per-candidate exclusion reasons, using the four categories in section 5. |
| **H094 groundwork** | Multi-store identity and assignment model, where required for shared staff. |
| **Availability.2** | Standing scheduling baseline. Effective-dated history. Mutual visibility. Composition rule (Q8). |
| **Availability.3** | Pattern-change lifecycle, history, acknowledgement. |
| **Precedence phase** | Provenance-preserving admin authority, superseding D048's destructive replacement. Unscheduled. |
| **Cross-site phase** | Conflict surfacing. Depends on H094. |

### Availability.1 ships declared-only

v1 argued weekly availability is meaningless without the standing layer. **That was
overstated.** "I can work Monday 09:00–17:00 this week" is meaningful on its own. The standing
layer later tells us whether that week is normal, exceptional, narrower than usual, or extra
flexibility — but it is not required for the weekly layer to be coherent.

Making the weekly semantics future-compatible now is what matters: if `unavailable` is defined
as decisive-for-automatic-assignment from the start and `preferred_off` as the soft signal, the
standing layer later adds a baseline rather than downgrading anything employees were previously
told.

### Scope warning

This document describes roughly six phases touching the schema, the recommendation engine, both
portals, and possibly a new request model. The identified risk is that **Availability.1 quietly
absorbs all of it** — the exact failure mode the project's phase discipline exists to prevent,
currently occurring in conversation rather than in code, which makes it harder to notice.

---

## 11. Review status

The narrow second pass is complete. All four fencing points passed:

| Point | Status |
|---|---|
| Two-axis matrix | Passed, with effective-outcome column and scope wording added |
| Same-source contradiction vs cross-source precedence | Passed, cleanly separated |
| D048 fencing | Passed. Current, proposed-target, and Availability.1 scope kept distinct |
| No-row wording | Passed after correcting the "affirmative" contradiction |

**No further architecture review is required before adjudication.**

### Outstanding for Vachan

One substantive choice, plus the open questions in section 9:

> Should `available_extra` receive a ranking bonus over ordinary `available` in
> Availability.1? Proposed: no. See section 4.

Once the Availability.1 rules are adjudicated, the accepted decisions are recorded in
`DECISIONS.md` — and only then does the Codex prompt get drafted.

### Test to apply to any proposed rule

> Can the proposed rule explain why the site is impossible to staff, without silently violating
> what employees told us?

If it cannot, reject the rule.
