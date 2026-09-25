# WALK.1 — end-to-end walkthrough observations

**Date:** 2026-09-24
**Repository HEAD at start:** `c4c2deb`, clean, synced with origin
**Last implementation commit:** `0be2084` (H154, under D069)
**Suite at session start:** 1522 passed / 0 failed / 6 skipped
**Environment:** local Docker stack only. `ENV=development` throughout.

## Authority of this document

**This file records observations. It decides nothing.**

Nothing here has been adjudicated. No backlog entry has been created from it,
no D-number taken, and no fix applied. Where an item is a question rather than
a finding, it says so. Where a claim rests on evidence weaker than a terminal
command or a verbatim file read, the caveat is stated inline.

Items are identified `WALK.1-<step>-<letter>` and are referenced by those ids
in any later backlog entry or phase prompt.

---

## 1. Session scope and fences

The session walked the product end to end in a browser against the running
local stack, to establish what is broken in the product before any work is
done to make a deployment safe.

Fences held throughout:

```text
no product features
no NI numbers, passports or document uploads
no H181, H184 or H180 work
no live Resend key on this machine (D068 rule 5)
email on the local backend only
no real employee data at any point
D036's same-origin model not weakened
ENV stays development
fixes not in scope by default
```

Steps 3 (seeding), 4 (Cloudflare tunnel) and 5 (second-laptop walk) were not
started. Step 4 remains scoping work for H068.

---

## 2. Environment facts established

Each was established by a command run on the machine or in the container.

```text
OpenAPI is served at /openapi.json, not /api/v1/openapi.json
Postgres credentials: user anci, database anci_ops
Mailpit is gated behind `profiles: [mailbox]` in infra/docker-compose.yml,
  so a plain `docker compose up` does not start it
The local database carries rows from earlier development; store_opening_hours
  contains many stores' worth of mixed patterns. It is not a clean dataset,
  and anything read from it must be filtered by store.
```

### Configuration change made during the session

`infra/docker-compose.yml`, one line, **uncommitted**:

```text
-      EMAIL_BACKEND: ${LOCAL_EMAIL_BACKEND:-local_log}
+      EMAIL_BACKEND: local_smtp
```

Made so that verification and password-reset mail reaches Mailpit rather than
the application log. D068 rule 6 already names `local_smtp` to Mailpit as the
permitted development mapping and `local_log` as retained where no delivery is
expected, so both values are permitted and this is configuration, not a
decision.

**Observation:** the original line carried a `${LOCAL_EMAIL_BACKEND:-…}`
override hook. Exporting `LOCAL_EMAIL_BACKEND=local_smtp` would have achieved
the same result without editing a tracked file. Whether the committed
development default should be the variable form with a `local_smtp` fallback
is undecided.

### Test data created

```text
company   solomvp
site      solo-001 "solo state", 24/7, Europe/London
staff     6, roles assigned
weeks     21-27 Sept (published), 28 Sept - 04 Oct (draft)
```

---

## 3. Steps walked and outcomes

| Step | Outcome |
|---|---|
| A1 register owner | pass |
| A2 admin login | pass |
| A3 email verification | pass; single-use token confirmed |
| A4 2FA enrolment | pass after blocking issue below |
| A5 2FA re-login | pass; recovery code single-use, wrong-code rejection, lockout |
| A6 company setup | pass |
| A7 create site | pass |
| A8 opening hours | written; see A8-a |
| A10 create staff | pass |
| A11 rota readiness gate | pass |
| A12 shifts and recommendations | pass; see A12-d |
| A13 publish | pass, full "Published" |
| B1 employee login | pass |
| B2 employee home | pass |
| B3 availability | pass |
| B4 cover request | pass |
| C1 admin approval | pass mechanically; see C1-a |
| C2 session refresh | pass |

**Not walked:** B5 (swap — required a second employee with published shifts,
which did not exist) and B6 (earnings — confirmed absent from the codebase, so
there was nothing to walk).

### Behaviour verified in a browser for the first time

1. **Overnight shifts.** A 22:00–06:00 shift was created through the admin UI,
   stored, and rendered on the following day as "Overnight carry-over until
   06:00". Coverage.1bA's work holds in the product.
   - This contradicts H101's note that the admin UI blocks overnight creation
     twice (`validateCreateShiftDraft` and `buildShiftDateTime`). That note is
     now out of date.
2. **Overnight declared availability.** An employee entry of 21:00–06:00 was
   accepted and persisted. Coverage.1bB's cross-date work holds in the product.
3. **Cookie session refresh.** After roughly 30 minutes idle, two calls
   returned 401, `POST /auth/refresh` returned 200, and the calls replayed
   successfully with no visible interruption. D036's memory-only access token
   model recovering live, which C2 was intended to prove.

---

## 4. Blocking issue, resolved during the session

### WALK.1-A4 — 2FA enrolment returned 500

`POST /api/v1/auth/2fa/totp/enrol/begin` returned 500. The browser console
reported a CORS failure, which was a consequence rather than the cause: a 500
raised inside the handler bypasses the CORS middleware's header injection.

Traceback, from the container log:

```text
apps/api/routers/auth.py:1109  begin_totp_enrolment
apps/api/services/totp_crypto.py:29  encrypt_totp_secret
apps/api/services/totp_crypto.py:25  decode_totp_encryption_key
apps/api/core/totp_key.py:10  validate_totp_key
ValueError: TOTP_ENCRYPTION_KEY is required for TOTP secret encryption
```

Cause: `TOTP_ENCRYPTION_KEY` was absent from the container after a
`--force-recreate` run from a shell without the export set. This is H169's
recorded failure mode reproducing in the browser, not a new defect and not a
regression from the email-backend change.

Resolved by re-exporting and recreating. Enrolment then completed: QR code plus
manual fallback, **10 recovery codes** issued (a count not previously recorded
in any governing document).

#### Three presence checks that gave false positives

```text
docker compose exec api sh -lc 'echo ${TOTP_ENCRYPTION_KEY:+present}'
  → printed "present" when the value was the literal placeholder "<your key>"

shell history 1721 and 1726: test -n "TOTP_ENCRYPTION_KEY"
  → missing "$". Tests a 19-character literal. Has never actually checked.

The reliable check is the decoder, not the variable:
docker compose exec api sh -lc \
  'python3 -c "from apps.api.core.settings import settings; \
   from apps.api.services.totp_crypto import decode_totp_encryption_key; \
   decode_totp_encryption_key(settings.TOTP_ENCRYPTION_KEY); print(\"key valid\")"'
```

#### Standing risk, not adjudicated

The key exists only as a shell export, regenerated by `openssl rand -base64 32`
each time it is lost. Every container recreate can silently drop it, and the
loss surfaces only when something encrypts a TOTP secret. D069 closed this for
staging and production by refusing to boot; local, development and test were
deliberately left to discover a missing key at enrolment.

Same class of problem as Mailpit's profile gate: the development stack has
hidden preconditions that are not evident from the compose file. Whether to
close it (for example with a gitignored `.env` beside the compose file
carrying a development-only key) is undecided, and would need its own entry.

---

## 5. Items needing adjudication

### WALK.1-A8-a — the 24/7 toggle stores 00:00–23:59

The site-creation form offers an Opening Hours Type toggle with a `24_7`
option. Selecting it writes seven rows of 00:00–23:59 with `is_closed=false`.

Confirmed by query:

```text
   code   |    name    | day_of_week | open_time | close_time | is_closed
 solo-001 | solo state |           0 | 00:00:00  | 23:59:00   | f
 …seven rows, identical pattern…
```

The site is labelled 24/7 in the product and declared as closing for one
minute a day in the data. This is the exact substitution H101 names.

Current cost is display inaccuracy only: H101's inspection established that
nothing in `rota.py`, `shifts.py`, `rota_recommendations.py` or
`apps/api/services/` reads `open_time` or `close_time`. The only consumers are
two readiness `COUNT(*)` predicates and a display round-trip.

Durable cost: a truly continuous site and a site that closes at 23:59 are now
indistinguishable in the data. No later logic can recover the difference,
because the information was never recorded.

Owner: SiteHours.24h.

### WALK.1-B3-b — availability type semantics

Four types exist. Their meanings are not stated anywhere, and nothing declares
whether declared availability is exhaustive or additive.

Vachan's intended model, stated during the session:

| Type | Intended meaning |
|---|---|
| Available | can work these hours; the rest of the day is preferred-not but possible |
| Unavailable | a day off — the whole day |
| Prefer not to work | soft negative |
| Extra availability | normally a day off, but willing to work it |

Code inspection (section 6 below) shows the backend model already matches this
in substance. What is missing is a **full day vs specific times** choice on
Unavailable — the form currently always demands times.

Sits under D057, D059, D060, D061 and Availability.1a. Any change to type
meanings would amend those. Adding the full-day option appears additive.

### WALK.1-A12-d — unexplained assignment over declared Unavailable

**Status: unverified. Do not treat as a finding.**

On screen, after Generate recommendations ran against 28 Sept – 04 Oct, lee
yang was shown assigned to five shifts. Two of them — 30 Sept and 04 Oct, both
06:00–15:00 — fell inside dates where he had declared `Unavailable ·
06:00–15:00`.

Code inspection shows this should not be possible:

```text
declared_availability.py:23   HARD_NEGATIVE_TYPE = "unavailable"
declared_availability.py:152  elif entry.type == HARD_NEGATIVE_TYPE:
declared_availability.py:153      if intervals_overlap(…):
declared_availability.py:154          overlapping_negatives.append(entry)
declared_availability.py:200  if overlapping_negatives:
declared_availability.py:201      return DeclaredAvailabilityResult(eligible=False, …
                                    exclusion_cause=…UNAVAILABLE)

rota_recommendations.py:330   if not availability.eligible:
rota_recommendations.py:333       continue
```

Unavailable is a hard block, checked before the positive check, and an
ineligible candidate is skipped.

Candidate explanations, none tested:

```text
the entries did not reach _build_availability_map — that query filters on
  store_id == store_id OR store_id IS NULL, and on a date window of
  week_start - 1 day to week_start + 7 days
the two assignments were manually created shifts rather than applied
  recommendation output; applying a draft is a separate action
```

**Before anything is concluded**, the actual `availability_entries` rows for
that user and week, and the draft's stored reason strings, need to be read.

Also noted from the same inspection, not adjudicated: `declared_availability.py`
applies asymmetric interval rules. A positive entry must fully contain the
shift to count (line 150, `interval.start <= shift_start and interval.end >=
shift_end`), while a negative needs only to overlap (line 153). That asymmetry
is deliberate-looking but is not recorded in any decision this session read.

---

## 6. Code facts established by inspection

Retrieved verbatim during the session. Recorded because later work depends on
them and they were not previously written down.

```text
AvailabilityType = Literal["unavailable", "preferred_off",
                           "available_extra", "available"]
                                      apps/api/schemas/availability.py:7

HARD_POSITIVE_TYPES = frozenset({"available", "available_extra"})
HARD_NEGATIVE_TYPE  = "unavailable"
                                      apps/api/services/declared_availability.py:22-23
```

Eligibility order in `evaluate_declared_availability`:

```text
unknown provenance conflict  → ineligible
same-source conflict         → ineligible
cross-source conflict        → ineligible
any overlapping negative     → ineligible (cause UNAVAILABLE)
no applicable positive       → ineligible (cause NO_DECLARATION)
otherwise                    → eligible
```

Site create and edit surfaces, field sets:

```text
both surfaces   site code, location name, street address, city, postcode,
                site phone, site email, timezone, notes
create only     opening hours type (24_7 / custom) → separate endpoint
                status → maps to is_active
                manager first/last name, email, phone, role
```

`StoreUpdateInput` carries `is_active` and `manager_user_id`;
`POST /stores/{store_id}/deactivate` exists as a route with no frontend caller.

**Caveat:** `apps/api/schemas/stores.py` was never retrieved — the panel
returned ABSENT for it and supplied frontend TypeScript types instead. Every
claim above about what the backend accepts rests on the client's view of the
contract, not the server's, and should be confirmed before anything is built
on it.

---

## 7. Product-quality observations

### Data integrity

**WALK.1-A10-a — number inputs change value on scroll.**
Base Hourly Rate, weekly working-hour soft cap, monthly working-hour soft cap.
Hovering a number input while scrolling the page alters the value silently:
12.12 became 13.14 during the walk. No user action, no error, no indication.
Corrupts pay data. The highest-severity item in this section.

**WALK.1-A12-c — the shift time field cannot accept 24-hour input.**
The field renders in 12-hour mode with a separate AM/PM segment. Typing `23`
yields `2`; typing `13` yields `1`. The hour segment accepts 1–12 only and
discards the rest of the keystroke rather than rejecting it. Every other
surface in the product displays 24-hour times.

Likely `<input type="time">` inheriting a browser locale of `en-US`. Because
native time inputs take their clock format from the viewer's locale rather
than from the application, this may behave differently on another machine —
worth watching for during the second-laptop walk.

### Validation

```text
A7-a / A10-b   no country code selector on any phone field
               (site, manager, staff)
A7-b / A10-c   no phone length or format validation. Accepted:
               "123456789123456" (15 digits), "2548" (4 digits),
               "+447404093665" and "07404093665444" in the same form
A10-d / A7-c   email validates shape but not domain. Accepted:
               sr@gmmaila.com, ly@gmail.om, solomvpstate@gmai.com,
               solomvp@gmai.com
```

Malformed email *is* caught, with a clear inline message, a highlighted field
and a summary banner. Typo'd domains at valid-shaped addresses cannot be
caught by a pattern check; only a did-you-mean suggestion on common
misspellings, or a confirmed send, would catch them. These are two different
problems and should not be treated as one.

Noted for whenever phone handling is addressed: the established approach is
E.164 storage (`+447404093665`), a country selector defaulted from the site or
company country, and per-country validation. There is no universal digit
count — UK mobiles are 11 digits nationally, Indian 10, US 10 — so a single
global length rule would be wrong. The standard library is Google's
`libphonenumber` (`libphonenumber-js` in a React frontend). This touches every
phone field in the product and wants one shared component rather than three
separate fixes.

### Site lifecycle

**WALK.1-A7-d — a lifecycle surface is promised and does not exist.**

The edit page states: *"Update normal site profile details. Lifecycle actions
are managed separately."* No such surface exists anywhere in the product.

Consequences:

```text
a 24/7 site cannot be changed to custom hours, or the reverse
a site cannot be deactivated
a manager cannot be reassigned
```

The site list card also omits trading hours entirely, so an operator scanning
their sites cannot tell which are 24/7.

See the caveat in section 6 about the unretrieved backend schema.

### Employee portal

```text
B1-a   the "Employee Portal" tab on the admin login is not clickable
       (not-allowed cursor). It looks interactive and is not.
B1-b   employee login requires a site code, and nothing surfaces it.
       Three things must reach the employee — site code, username,
       temporary password — and no surface presents them as a set.
B1-c   there is no password reset on the employee portal. With H102
       (no admin reset path), a forgotten employee password is a
       complete dead end.
B1-e   temporary passwords are never forced to change. With B1-c, an
       admin-issued password stays in use indefinitely.
B1-d   the employee portal header shows a raw site UUID:
       "lee yang at site fa4218d8-1ed1-4f66-833e-b7194742a9b9"
```

### Requests

**WALK.1-C1-a — approved cover requests tell the admin and the employee
different things.**

The Request Queue header states the model:

```text
Leave approvals open affected shifts for cover.
Target-accepted cover approvals can reassign one shift.
Target-accepted swap approvals can exchange both modelled shifts
  after manager approval.
```

The employee's Cover request form has a shift selector and a reason field and
**no target-employee selector** — only the Swap form has one. An employee
therefore cannot name a target, which means every cover request they raise
necessarily approves without reassigning anything.

On approval the admin sees: *"Cover request approved. No target employee was
assigned, so rota was not changed."*

The employee sees only *"Cover · approved"*, while the shift remains on their
rota marked *scheduled*. Nothing tells them the rota was unchanged. An employee
can reasonably conclude they no longer need to attend a shift they are still
rostered on.

```text
C1-b   two cover requests were raised against the same shift and both
       were approved. Nothing prevented the duplicate.
C1-c   the employee request list shows raw shift UUIDs. With C1-b this
       produced two rows distinguishable only by a typo in the reason text.
B4-b   the requests page defaults to a week in which the employee has no
       upcoming shifts, while their shifts sit in the following week.
       Previous / This week / Next controls exist, so it is navigable.
```

### Forms and layout

```text
A6-a   the save confirmation banner renders at the top of the company
       setup form while the save button sits at the bottom. The user
       cannot see it, assumes failure, and clicks repeatedly — visible
       as repeated PATCH /company/profile calls in the network panel.
A6-b   "Cancel / Back to dashboard" is one control doing two jobs.
       Discarding and navigating are different intents.
A6-c   registered address is a single freeform textarea. No line 1 /
       line 2 / town / county / postcode. Splitting it is a schema
       change plus a migration plus a backfill, not a frontend edit.
A10-e  staff directory cards are fully expanded by default — eight
       labelled rows per person. Six staff already fills several
       screens. The axis that matters is summary vs detail, not
       horizontal vs vertical: an operator with forty staff needs to
       scan and find. Direction discussed: compact rows carrying name,
       role, location and one contact field, with the existing
       "View profile" control expanding the rest.
A12-a  the shift time picker is a scrolling column dropdown. A
       Material-style clock face was raised as the preferred
       alternative. Note that clock faces suit touch and typed entry
       suits desktop; this interacts with A12-c, since replacing the
       native input is what would give control over the clock format.
A12-b  rota grid columns misaligned and shift cards overflowed their
       cells. Observed once, not reproduced in later screenshots.
       Possibly a mid-load rendering state.
```

**WALK.1-B3-a — the availability Type helper text is a single hardcoded
string.** `apps/web/app/employee/availability/page.tsx:303` renders
*"This records a preference not to work. It does not by itself mark you as
available."* regardless of which of the four types is selected. It describes
`preferred_off` only, and is therefore wrong for the other three. Confirmed by
file inspection, not only by observation.

### Behaviour that was correct and is worth recording

```text
B3-c   the publish lock is enforced and explained: "This week is locked
       because your rota has already been published."
       Past dates are also refused: "date must not be in the past."
B4-c   Submit swap was correctly disabled with the cause visible:
       "No published target shifts available."
A11    publish stayed disabled with readiness satisfied and zero shifts,
       and the hint explained why.
A12    the recommendation engine explained an empty result rather than
       failing silently: "No eligible candidate. Check staff
       availability, role requirements, and hard hour limits." Apply was
       disabled with "There are no staff assignments to apply."
       Soft-cap warnings fired on assigned shifts and did not block,
       matching the form's own stated behaviour.
A3/A5  single-use tokens and recovery codes were rejected on reuse with
       clear, distinct messages for wrong code, used code, and too many
       attempts.
```

---

## 8. Known limits confirmed, not defects

| Behaviour | Owner |
|---|---|
| 24-hour opening hours unrepresentable | H101 / SiteHours.24h |
| No earnings or payroll surface | not built. `GET /employee/me/labour-intelligence` has no frontend caller; the "Payroll & Compensation" nav item has no `href` and falls through to `showSetupComingNext` |
| Hot Food, Reports, Employee Profile, Settings are stubs | not built |
| No UI to regenerate recovery codes or disable 2FA | H170 |
| No admin path to reset an employee password | H102 |
| Swap rota application not implemented | the product states this itself |

---

## 9. What this leaves open

```text
A12-d needs the availability_entries rows and the draft reason strings
  before it can be classified
apps/api/schemas/stores.py has still not been read; A7-d's contract
  claims rest on frontend types
B5 (swap) was never walked and needs a second employee with published
  shifts
B3-b needs Vachan's adjudication before anything touching availability
  semantics is built
```

Carried into the tunnel stage (step 4, H068 scoping):

```text
APP_BASE_URL=http://localhost:3000, so every reset and verification link
  will point at the laptop rather than the tunnel hostname
Mailpit is behind a compose profile and will not start by default
TOTP_ENCRYPTION_KEY lives in a shell export and does not survive a
  recreate from a different shell
```

Hand entry of company, site, opening hours and six staff was slow enough that
repeating it on a second machine would be tedious. That answers the question
step 3 was written to answer: seeding is worth doing before the second-laptop
walk.
