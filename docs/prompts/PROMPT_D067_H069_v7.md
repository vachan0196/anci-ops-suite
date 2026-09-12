# Codex implementation prompt — D067 + H069 (bundled)

**Version:** v7. Supersedes v1 through v6 entirely.
**Resumes** the second halt reported by Codex at `e9716b1`. Gate 3 is
redesigned (§6.4) and §6.5's reachability claim is corrected — v6 overstated
it and Codex falsified it.
**Status:** draft, pending a final blind adversarial review before Codex.
**Lane:** authentication and credentials. Full review loop required.

## Provenance — controller-assembled. Verify present; never derive or rewrite.

```text
Prompt written against            e9716b1
Governing documents exported at   e9716b1
Landed between                    nothing — same commit
Section 5 facts established at    e9716b1, two independent inspections
```

---

## 0. Blocking preflight — run before reading anything else

```bash
cd ~/code/anci-ops-suite
git status --short --branch
git rev-parse --short HEAD
git fetch origin
git rev-list --left-right --count origin/main...HEAD
```

```text
REQUIRED   HEAD is e9716b1
REQUIRED   working tree clean
REQUIRED   branch main, synced with origin
```

**Any mismatch: HALT and report before proceeding.** Section 5's facts describe
the topology at `e9716b1`. Confirming a function name still exists does not
confirm you are modifying the topology those facts describe.

---

## 1. Read first, in this order

```text
docs/HANDOVER.md
IMPLEMENTATION_STATUS.md
DECISIONS.md          — D067 in full, and D034, D036, D037, D040, D041,
                        D065, D066
HARDENING_BACKLOG.md  — H069 in full, and H133, H153, H155, H156
README.md
docs/AI_WORKFLOW.md
CLAUDE.md
AGENTS.md
```

---

## 2. The restatement prohibition — enforced, not asserted

The failure recorded in `docs/HANDOVER.md` under "The correction worth
remembering": a rule entering through a prompt rather than adjudication,
surviving review because it read as a restatement.

**v3 of this prompt violated its own prohibition and the violation was
material** — its paraphrase of D067's negative conditions omitted the
malformed-`sid` case that D067's own test block contains. That is the defect
shape, reproduced inside the document that bans it.

v4's rule:

```text
this prompt contains implementation facts, file anchors, Vachan's
  adjudications, mechanical instructions, and POINTERS to authority

it contains no sentence that translates, interprets, summarises or
  restates what D067 or H069 require

where a rule must appear here, it appears as a marked verbatim
  quotation, never as a paraphrase

where the bridge from authority to implementation is not mechanical,
  HALT — do not write the bridge as prose

if this prompt and DECISIONS.md or HARDENING_BACKLOG.md appear to
  differ: the authority wins, this prompt is wrong, HALT and report
```

**Do not test this prompt's wording. Test the authority's wording.**

---

## 3. Phase identity

```text
Phase        D067 + H069 implementation
Base         e9716b1
Gates        Q.5.3a-2
Authority    D067 (Accepted 2026-09-10), H069 (Open, resolution
             adjudicated 2026-09-10)
Closes       H153, and H069 if its closure criteria pass
Corrects     H153's FACT block — its entry-point list is incomplete
Opens        new backlog entries, section 9.3
Type         backend, tests, documentation. No migration. No frontend.
```

---

## 4. Non-negotiables

```text
Alembic migrations only. No create_all.
Preserve tenant isolation, site isolation, RBAC, audit logging.
Additive implementation. No architecture redesign.
No commit. No push. Vachan reviews via git show and commits.
Test dates derive from date.today(). Never absolute calendar dates.
On divergence: HALT and report. Never self-resolve.
Collect ALL divergences in one pass. Do not stop at the first.
```

### 4.1 Commit split — and the executable protocol that decides it

Proposed:

```text
1  feat: D067 session revalidation on every authenticated request
2  feat: H069 retire refresh-token compatibility paths
3  docs: record D067 + H069 completion, close H153
```

**Textually separate hunks do not establish independence.** A shared helper
changed in patch 1 and relied on by patch 2 entangles them without touching
the same lines. Self-attestation that they are separable is not evidence.

**Protocol — no commits are made at any point:**

**Step 0 — symbol and invariant ownership, before any patching.**

```text
list the production symbols each part introduces or modifies
list the invariants each part establishes

REJECT the split if Part B modifies, depends on, or is required for
  correctness of any D067 invariant Part A introduces — even where the
  two patches touch no common line
```

Byte restoration does not establish invariant independence. Part B can depend
on a helper Part A introduced, reversing B still reproduces A exactly, and
both suite runs stay green while the two changes are entangled.

**Steps a–h. No commits are made at any point.**

```text
a  materialise Part A only. Save the diff as part_a.patch.
   Record a WORKING-TREE CONTENT proof — hash the actual file
   contents of the tracked working tree, including unstaged edits.
   `git rev-parse HEAD^{tree}` is NOT that: it ignores the working
   tree entirely and would make step (f) vacuous.
b  docker compose ... --build --force-recreate api
c  run the full suite. Record the result. It MUST be green.
d  apply Part B. Save the diff as part_b.patch.
e  reverse-apply ONLY part_b.patch
f  assert the working-tree content proof matches (a) exactly
g  rebuild, rerun the suite, assert the same green result as (c)
h  re-apply part_b.patch
```

**If step 0 rejects, or (c) is not green, or (f) or (g) fails: collapse Part A
and Part B into one atomic implementation commit and report why.** The
documentation commit stays separate regardless.

Report the ownership lists, both patch files, and both suite results.

---

## 5. Established facts — `read` or `executed` at `e9716b1`

Line anchors were correct at `e9716b1` and will move. Confirm by name.

### 5.1 The complete bearer-authentication entry-point inventory

Two independent enumerations. The second did not start from a list.

```text
decode_access_token_payload    security.py:77   sole caller of jwt.decode
decode_access_token            security.py      calls the above
```

Every production call site of those two is enclosed by exactly six functions.
Seven bearer entry points result:

```text
ENTRY POINT                          ANCHOR         reads auth_sessions
get_current_user                     deps.py:74     no
get_current_tenant_id                deps.py:104    no — chains
require_tenant_member                deps.py:136    no — chains
require_tenant_role                  deps.py:143    no — chains
get_current_employee_account         deps.py:320    no
get_current_admin_user_and_session   deps.py:164    YES
_get_current_admin_user              auth.py:796    no
me                                   auth.py:1704   no — inline decode
request_email_verification           auth.py:1723   no — inline decode
```

Reaching `get_current_admin_user_and_session` transitively:

```text
require_sensitive_admin_action       deps.py:246
step_up_2fa                          auth.py:1650
```

No middleware establishes a principal; the only repository-defined middleware
is `add_request_id` (`main.py:40`). `oauth2_scheme` is
`OAuth2PasswordBearer` and does not decode.

`_get_current_admin_user` is router-local and chains through nothing. It is a
`Depends` dependency for five endpoints:

```text
/auth/2fa/status                       auth.py:1063
/auth/2fa/totp/enrol/begin             auth.py:1094
/auth/2fa/totp/enrol/confirm           auth.py:1142
/auth/2fa/disable                      auth.py:1539
/auth/2fa/recovery-codes/regenerate    auth.py:1599
```

**H153's FACT block lists six entry points and omits this one.**

### 5.2 The fix surface — five sites

```text
deps.py   get_current_user               covers the three chaining deps
deps.py   get_current_employee_account
auth.py   _get_current_admin_user
auth.py   me
auth.py   request_email_verification
```

**Vachan's adjudication, 2026-09-11:** `_get_current_admin_user` is in the set
of sites that gain session validation.

For what session validation requires, and for the conditions to test:

```text
D067 §1                  apply verbatim
D067 §2                  apply verbatim
D067 "Test to apply"     apply verbatim, all three groups
```

**Do not work from any list of conditions in this prompt. There is none.**

### 5.3 The tenant-drift trap

`get_current_admin_user_and_session` applies a tenant-drift rejection before
returning to either caller (`read`, deps.py:164).

The cheapest implementation — routing the five sites through that helper —
would extend that rejection to all five 2FA endpoints, `/auth/me` and the
email-verification request, with a green suite.

**Read D067 §4 verbatim before choosing a factoring.** Both of its clauses.

**Mechanical halt triggers.** HALT and report if achieving §5.2 requires any
of:

```text
1  duplicating the tenant-drift predicate

2  relocating the tenant-drift predicate

3  changing the tenant-drift error code, status, or ordering relative
   to other checks

4  changing the TENANT-DRIFT observable contract of
   require_sensitive_admin_action or step_up_2fa

5  changing the ordering or outcome of any account, activity,
   membership or role check at any of the five sites

6  the NEW session validator or session lookup reading, joining on,
   filtering by, or comparing the principal's current or active tenant
   — at any of the five sites
```

**Trigger 4 is scoped to tenant drift, corrected in v6.** v5 wrote it as "the
observable contract", which read as freezing every observable behaviour of
those two endpoints — including the malformed-`sid` 500 that section 6.5 now
repairs. §5.3's subject is tenant drift and nothing else. Every other aspect of
those endpoints stays covered by triggers 1-3, 5 and 6.

**Trigger 6 exists because triggers 1 to 5 only constrain the existing
predicate.** A new session lookup scoped by the user's active tenant, or a new
binding check that compares current tenant state, duplicates nothing,
relocates nothing, leaves both existing callers untouched — and introduces
tenant-dependent rejection anyway.

These six are the boundary. "Clean" is not a criterion and is not used here.

**Test differentially, not absolutely.** Do not assert that a drifted-tenant
request to the five sites succeeds — that pressures the implementation to
weaken an unrelated check to make it true. Instead:

```text
control     an otherwise-identical request, no tenant drift
subject     the same request, tenant drifted
assert      the two outcomes are identical at the five sites
assert      the two outcomes DIFFER at require_sensitive_admin_action
            and at step_up_2fa, with today's rejection unchanged
```

**Comparing final HTTP responses is not sufficient.** If the control already
fails for an unrelated reason before reaching the drift-sensitive branch, both
requests return the same status while the forbidden check exists downstream.
**Assert that control and subject reach the same point after session
validation**, not merely that they produce the same response.

### 5.4 The OpenAPI denominator

`executed` at `e9716b1`:

```text
89 paths, 112 operations, 100 declaring security, 12 without
```

Method — the repository provides no generation script; only `app.openapi()`
and the unauthenticated `GET /openapi.json` (H155):

```bash
docker compose -f infra/docker-compose.yml exec -e PYTHONPATH=/app api \
  python -c 'from apps.api.main import app; ...app.openapi()...'
```

`app.openapi()` and a curl of live `/openapi.json` were byte-equal.

The scheme is `OAuth2PasswordBearer` (`type: oauth2`, password flow), not an
`http`/`bearer` scheme.

The 12 unsecured at `e9716b1`:

```text
register, login, 2fa/verify, email-verification/confirm,
password-reset/request, password-reset/confirm, employee/login,
refresh, logout, health, public/sites/lookup,
GET /hot-food/forecast (H156)
```

For this phase's obligation regarding this count, see D067's denominator
paragraph. Apply it verbatim.

**Pin the declaration, not a boolean.** A count of 100 survives one operation
losing its security declaration while another gains one. A
secured/unsecured boolean survives an operation keeping a `security` block
whose contents weaken — an added `{}` alternative making auth optional, a
changed scheme, changed scopes.

```text
capture the exact operation → OpenAPI `security` VALUE mapping, the
  full declaration per operation, at e9716b1

capture it again on the post-change reviewed working tree based on
  e9716b1

assert the two mappings are IDENTICAL — this phase adds no operations

assert separately that each protected operation's auth dependency root
  is MANDATORY, not merely present in the Dependant graph. An optional
  auth dependency remains visible to Gate 3 while the operation becomes
  anonymously callable.

if optional-auth is representable in this codebase, mutation-test it:
  make one operation's auth optional, confirm the assertion fails,
  revert

report any divergence for adjudication; do not reconcile it
```

**On "the phase commit".** You do not commit, so you cannot know its hash. The
evidence point is the **post-change reviewed working tree based on
`e9716b1`**. The durable record naming the actual implementation commit is
written after Vachan creates it — see 9.3.

### 5.5 The refresh-token surface

`read` at `e9716b1`. All four H069 claims confirmed:

```text
five issuance paths, four endpoints
  TokenResponse            auth.py:1055   admin login
  TokenResponse            auth.py:1528   2FA verify
  EmployeeLoginResponse    auth.py:2068   employee login
  RefreshTokenResponse     auth.py:2173   admin AND employee refresh
  (the 2fa_pending return at auth.py:1029 issues no refresh token)

two body-accepting endpoints
  RefreshTokenRequest.refresh_token   schemas/auth.py:195-212
  LogoutRequest.refresh_token         schemas/auth.py:195-212
  consumed at auth.py:2091-2092 and auth.py:2187

selector           auth.py:407-408
  payload_token or request.cookies.get(...)

CSRF early return  auth.py:428-429
  branches on `is not None`
```

`RefreshTokenResponse` (`schemas/auth.py:202`) has one construction site,
`auth.py:2173`; `refresh` is its only caller. The admin and employee branches
converge on one return.

**Empty-string CSRF bypass, `executed` over HTTP** — upgrading H069's
helper-level evidence. Cookie present, no `X-Requested-With`:

```text
body omitted             → 403 AUTH_CSRF_REQUIRED
body refresh_token null  → 403 AUTH_CSRF_REQUIRED
body refresh_token ""    → 401 AUTH_REFRESH_INVALID
                           ← passed the CSRF guard, reached
                             _load_refresh_session with the COOKIE value
```

Also `executed`: non-JSON content types get 422 before the guard, so a browser
needs a preflighted JSON request; the cookie is `SameSite=strict`. The same
guard serves logout.

### 5.6 Where the 422 exception reaches

`executed` at `e9716b1` with a real Sentry client on a dummy DSN and a
capturing transport, plus root-log capture:

```text
HTTP response      YES. errors.py:52-66 puts str(exc) in `message` and
                   details[].input verbatim. For a model-level error the
                   whole body was echoed in both fields.
                   str(exc) ALSO contains the endpoint's server file
                   path and line number.

application logs   NO. The handler has no logger call. errors.py's only
                   logger is in generic_exception_handler, which this
                   exception never reaches. Uvicorn's access line
                   carries method/path/status only. Zero captured
                   records held the marker.

Sentry             NO, today. sentry-sdk 2.68.1's patched
                   ExceptionMiddleware captures only when
                   exp.status_code is 500-599. RequestValidationError
                   has no status_code attribute. Empirically 0 events.

audit storage      NO. Body validation fails before the endpoint body
                   executes — no _add_auth_security_event, no AuditLog
                   write.

security events    NO. Same reason.
```

Currently unreachable, not currently defended. If the exception were ever
captured, `str(exc)` becomes `exception.values[].value`, which `_before_send`
does not touch. H133 strips `frames[].vars` and key-redacts
`request`/`contexts`/`extra` only.

**Vachan's adjudication, 2026-09-11: defend it in this phase, scoped.** See
6.3.

### 5.7 Environment and baseline

```text
executed   the api service has NO bind mount. infra/docker-compose.yml
           declares build, environment, depends_on, ports — no volumes.
           Source enters only via COPY in the Dockerfile.

executed   656 passed, 0 failed, 6 skipped, 2 warnings, 393 s
           docker compose -f infra/docker-compose.yml exec -T \
             -e PYTHONPATH=/app api pytest -q

read       _before_send is exercised as a pure function today —
           test_phase_q0_hardening_baseline.py:26 and seven tests in
           test_phase_q5_3a_0_security_config.py:31-146. The SDK
           PIPELINE is exercised nowhere: the init test mocks
           sentry_sdk.init, and conftest.py leaves SENTRY_DSN unset so
           init_observability() returns at observability.py:118.

executed   the pipeline IS exercisable: set a dummy SENTRY_DSN before
           importing apps.api.main, replace
           sentry_sdk.get_client().transport with a Transport subclass
           whose capture_envelope collects payloads, drive requests
           through TestClient.
```

---

## 6. Implementation

### 6.1 Part A — D067

```text
D067 §1 through §5   apply verbatim
```

Apply at the five sites in 5.2, subject to 5.3's halt triggers and
differential test.

**The three chaining dependencies.** 5.1 records, as a fact at `e9716b1`, that
they authenticate transitively through `get_current_user`. That is a
pre-change fact and does not survive the edit by itself — rebinding
`get_current_user`, wrapping it, or changing an imported alias can leave
descendants on the old path while the new tests pass.

```text
"no production edit expected"   defensible
"no verification needed"        not
```

Exercise a revoked-session request through `get_current_tenant_id`,
`require_tenant_member` and `require_tenant_role` individually, after the
change.

**For what happens to tests that construct tokens directly: D067 §3, final
two paragraphs. Apply verbatim.**

### 6.2 Part B — H069

```text
H069 "Resolution — cookie only"        apply verbatim
H069 "Explicitly NOT in scope"         apply verbatim
```

```text
H069 closure criterion 5                apply verbatim
H069 "On criterion 5"                   apply verbatim
```

Implementation anchor: `auth.py:428-429`. 5.5 gives the exact HTTP-level
behaviour at `e9716b1` to regress against.

### 6.3 Part B2 — defend the validation exception, scoped

**Vachan's adjudication, 2026-09-11, option A of two presented:**

```text
CHOSEN    scope the strip to the credential-bearing validation-exception
          shape. Ordinary exception values continue to reach Sentry.

REJECTED  unconditional deletion of exception.values[].value for every
          exception event. That is an observability policy, not a
          credential fix, and it was not adjudicated.
```

Implement the narrower control.

**The preservation control must be a non-credential `RequestValidationError`
with the same Sentry event shape.** Not a `RuntimeError`, not an arbitrary
exception. Using a different exception class lets an implementation strip
`exception.values[].value` from *every* validation error — exactly the global
behaviour that was rejected — while the preservation test passes on a class
the strip never touched.

```text
subject    a credential-bearing RequestValidationError
           → exception.values[].value STRIPPED

control    a non-credential RequestValidationError, same event shape
           → exception.values[].value SURVIVES intact
```

7.3 does not cover this. 7.3 preserves ordinary HTTP 422 *responses*; this
preserves Sentry exception *values*. Different sinks, both required.

**Make no claim, in code comments or documentation, that this removes a
D066-style re-proof obligation on SDK upgrade.** A future SDK serialising
exception text into a different field would falsify it.

### 6.4 Part A2 — closed-path guards

**A decoder-call-site count is not sufficient and must not be what you
build.** It certifies one spelling of the current topology. A bypass ships
green via an aliased import, a wrapper, a direct `jwt.decode` call, manual
`Authorization` parsing, copied decode logic, or a new route taking another
path while the old call sites remain.

**Guard 1 — the root.** `jwt.decode` has exactly one production caller,
`decode_access_token_payload` (5.1). Assert it. A new direct caller fails the
suite.

**Guard 2 — the enclosing set. SEVEN items, corrected in v6.** Production call
sites of `decode_access_token` and `decode_access_token_payload` are enclosed
by exactly:

```text
the six authentication functions in 5.1
security.py:decode_access_token — the internal wrapper, which calls
  decode_access_token_payload
```

v5 said "six functions", dropping the wrapper. Codex caught it.

**Mark the wrapper as a wrapper in the approved set**, so the allowance cannot
later admit an authentication function under it. Assert the set by identity
where the language permits, not by textual match. State how test-only call
sites are excluded.

**Gate 3 — route-to-validator, asserted behaviourally. Redesigned in v7.**

v6 specified traversal of the FastAPI `Dependant` graph. Codex established
that this cannot work: store deactivation's graph reaches the sensitive-action
closure, `OAuth2PasswordBearer` and `get_db`, but the session helper is an
ordinary Python call at `deps.py:253` and is absent from the graph entirely.

Codex proposed resolving Python call edges by callable identity. **Rejected.**
Static call-edge resolution in Python is fragile against aliasing, indirection
and wrappers, and it would build a brittle approximation of a property that
can be tested directly.

**Assert the property instead of inferring it:**

```text
for EVERY operation declaring security in 5.4's identity map:
    issue a request bearing a token whose session is REVOKED
    assert the request fails authentication
```

```text
no graph traversal
no call-edge resolution
no assumption about HOW the validator is reached

an operation that skips the validator fails the sweep, whatever the
  mechanism — including one that decodes a token by some route guards
  1 and 2 do not cover
```

**Requests need not succeed.** They need to reach authentication, which
happens before the handler body. Supply syntactically valid path and query
parameters; whether the referenced rows exist is irrelevant, because
authentication fails first.

**The three endpoint-body authenticators need no special handling.** `me`,
`request_email_verification` and `step_up_2fa` are operations like any other
and are covered by the same sweep. v6's separate-assertion requirement for
them is withdrawn.

**Gate 3's universe is 5.4's identity map.** An operation silently losing its
security declaration leaves that universe; the map is what detects it. The map
pins WHICH operations declare security; the sweep proves EACH ONE reaches the
validator. Both are required.

**Mutation-test the sweep.** Remove the session check from one entry point,
confirm the sweep goes red on the operations behind it, restore.

**If guard 1 or 2 is unreliable against this codebase — dynamic dispatch,
indirection — say so and propose the alternative. Do not silently weaken one
to a grep count.**

**If some operation in the identity map cannot be driven to authentication by
the sweep, HALT and report which and why.** Do not exclude it silently; an
operation the sweep cannot reach is exactly the kind Gate 3 exists to find.

### 6.5 Part A3 — malformed typed JWT claims must not produce 500

**Classified as a DEFECT, not a product decision** — an unhandled exception on
malformed input at a trust boundary is a bug, so this needs no D-number and no
adjudication. Two new H-numbers, opened and closed by this phase, at different
severities.

**Why it stays in scope after v7's correction.** The original justification was
reach, and that justification is gone. What remains: this phase is already
editing the decode path, an unhandled exception at a trust boundary is a defect
regardless of who can reach it, and the fix is a type guard and an `except`
clause. That is a weaker case than v6 made, and it is stated plainly rather
than repaired with a better-sounding one.

Established by execution at `e9716b1`, by Codex and independently by the
panel:

```text
CLAIM        sid — custom claim, python-jose does not type-check it
PATH         get_current_admin_user_and_session, uuid.UUID(session_id_raw)
             catches (TypeError, ValueError) only
INPUT        1, [], {}  → AttributeError → 500 INTERNAL_ERROR
             "not-a-uuid" → 401 AUTH_INVALID_TOKEN (already correct)
REACH        the two session-validating paths today; ALL FIVE NEW SITES
             inherit it the moment they begin validating sessions

CLAIM        exp, iat, nbf — standard claims, parsed by python-jose with
             int(claim) catching ValueError only
PATH         inside jwt.decode, BEFORE repository code sees the payload.
             The repository decoder catches JWTError only, so TypeError
             escapes.
INPUT        None, [], {} → TypeError → 500 INTERNAL_ERROR
REACH        corrected in v7. v6 stated "requires no valid credential".
             That was WRONG and Codex falsified it by execution:

                 valid signature   → 500 INTERNAL_ERROR
                 invalid signature → 401 AUTH_INVALID_TOKEN

             The crash requires a VALID SIGNATURE. It does NOT require
             a live account or an unrevoked session. Crafting a token
             with a malformed exp requires re-signing, which requires
             JWT_SECRET_KEY — and anyone holding that key can forge any
             token, so this is not an exposed attack surface.

SEVERITY     LOW. Record it as such. Do not carry v6's overstatement
             into HARDENING_BACKLOG.md.

NOT AFFECTED sub, aud, jti — python-jose type-checks these and raises
             JWTClaimsError, which the decoder already converts to 401.
             Verified across all seven entry points.
```

**The rule, applied at both points:**

```text
a malformed typed JWT claim produces an authentication failure
  (401 AUTH_INVALID_TOKEN), never a 500
```

**Narrowest fixes, per the panel's inspection:**

```text
sid            an explicit string type guard immediately before
               uuid.UUID(session_id_raw). Preferred over widening the
               except tuple to AttributeError — a type guard validates
               the claim's required type directly rather than
               classifying by whichever exception happens to escape.

exp/iat/nbf    handle TypeError around jwt.decode. The failure occurs
               inside the library, so this is the narrowest available
               boundary in repository code.
```

**Neither changes the outcome for any currently valid token.** Valid tokens
carry `sid` as a UUID string and integer time claims; both continue through
the same paths unchanged. Prove that rather than asserting it.

**Tests required:**

```text
for sid: 1, [], {}, "not-a-uuid", and absent — each produces an
  authentication failure, at every site that validates sessions after
  this phase, not only the two that do today

for exp, iat, nbf independently: None, [], {} — each produces an
  authentication failure, on a representative secured operation from
  each of the seven entry points in 5.1. Use a VALIDLY SIGNED token;
  an invalidly signed one returns 401 before reaching the crash and
  would pass vacuously.

a currently-valid token authenticates unchanged — the regression that
  proves the fix is narrow
```

**Scope boundary, stated because this is an expansion.** This phase repairs
these two claim-parsing sites and nothing else. If inspection surfaces a third
malformed-input crash elsewhere, it gets a backlog entry with the evidence
attached and a suggested phase — it does not join this one.

---

## 7. The preservation obligation

```text
H069 "A preservation obligation, not an eighth criterion"
    apply verbatim
```

For why this obligation exists and why it is not an eighth criterion, read the
named H069 section. It is not summarised here.

5.6 establishes where the exception reaches at `e9716b1`. **That measurement
predates the change. Re-execute the proof after the change; do not inherit
it.**

Use one distinctive marker value appearing nowhere else in the repository or
any fixture. Submit it as a body-supplied `refresh_token` post-removal.

### 7.1 Three telemetry tests, not one

v3 required the marker absent at both the `_before_send` input and the
transport boundary. **That was wrong in both directions** — under production
config no event reaches the hook, so input-absence proves nothing; and under
forced capture the marker must be present at input, or the redactor is not
being exercised.

```text
TEST 1 — production configuration
  drive the real 422
  assert ZERO Sentry error events reach _before_send
  assert ZERO envelopes reach the transport
  this documents 5.6's status quo and regresses it

TEST 2 — forced capture, the defence under test
  drive the REAL HTTP request through TestClient, the real Starlette
    and Sentry middleware, and the real SDK event construction
  change ONLY the configuration or predicate that currently excludes
    422s from capture
  assert _before_send is INVOKED
  assert the marker IS PRESENT in the event on entry
  assert the marker is ABSENT from the returned event
  assert the marker is ABSENT from the transport envelope

TEST 3 — pure function control
  the existing _before_send unit-test pattern, extended
```

**The forcing is constrained to the capture decision. Nothing downstream.**
Test 2's whole value is that the real exception-to-event conversion runs. A
synthesised event, a directly-invoked event processor, or an integration
monkeypatched after event construction all produce a green test against a
hand-built event shape, while the real conversion — which is where a future
capture would serialise the credential — stays untested.

```text
PERMITTED   widening the capture predicate or configuration that
            currently excludes 422s

FORBIDDEN   inserting any synthetic event downstream of the middleware
            capture point
FORBIDDEN   invoking an event processor directly
FORBIDDEN   monkeypatching the integration after event construction
FORBIDDEN   mocking capture_exception — per 5.6 this exception reaches
            the SDK through the patched ExceptionMiddleware, not an
            explicit capture call
```

**If the SDK exposes no reliable way to widen that capture predicate, HALT and
report it.** Do not substitute a synthetic path.

Use 5.7's transport seam for the envelope assertion.

### 7.2 The other sinks

```text
assert the marker absent from the HTTP response body, every field
assert the marker absent from every log record, at every level
assert the marker absent from audit storage rows
assert the marker absent from security-event storage rows
run the same assertions against the SUCCESS paths
```

Absence from storage proves persistence did not occur. It does not prove the
credential never crossed a confidentiality boundary — 7.1 is what proves that.

### 7.3 Do not break the global 422 contract

The generic validation handler at `errors.py:52-66` serves every endpoint.
Nothing in this phase authorises changing what it returns for ordinary,
non-secret validation failures.

```text
capture representative non-secret 422 responses BEFORE the change
assert AFTER: same status, same error code, same ordinary validation
  structure, except for the specifically security-sensitive material
  intentionally removed
```

**If a global redaction of `details[].input` or `str(exc)` looks like the
right answer, HALT and report it for adjudication.** This phase does not
choose an application-wide validation-response policy by side effect.

---

## 8. Tests required

```text
D067 "Test to apply", all three groups        apply verbatim
H069 "Closure criteria", all seven            apply verbatim
```

**Do not test a paraphrase of either. There is none in this document.**

### 8.1 Coverage this phase adds beyond those

```text
the five 2FA endpoints behind _get_current_admin_user, explicitly
5.3's differential tenant-drift test, control and subject
6.1's post-change inheritance proof, each chaining dependency
  individually
6.3's ordinary-exception preservation test
6.4 guards 1 and 2, and gate 3's revoked-session sweep across every
  operation in the identity map
5.4's operation → security identity map, before and after
7.1's three telemetry tests
7.3's non-secret 422 preservation tests
6.5's malformed-claim tests, plus the valid-token narrowness regression
```

### 8.2 On H069's criteria — persisted state, not response shape

A test checking only status and body passes while an internal selector touches
or revokes the supplied session before the response is produced. For each
negative case:

```text
snapshot the relevant auth_sessions rows BEFORE
issue the request
assert the rows are field-equivalent AFTER:
    no revoked_at set
    no replacement or child session created
    no family state changed
```

Apply this mechanic to every negative case identified by H069's closure
criteria 2, 3 and 5 — read them; the cases are not re-enumerated here. On both
refresh and logout.

### 8.3 Suite integrity

```text
baseline 656 passed / 0 failed / 6 skipped at e9716b1
report the delta; justify every changed test individually
report any test moving from failing to passing without a corresponding
  production change — that is a signal, not a win
```

The six skips are the rate-limit tests, guarded by `RATE_LIMIT_ENABLED`.
Unchanged by this phase.

---

## 9. Acceptance criteria

```text
1   preflight passed at e9716b1, clean tree

2   D067 §1-§5 implemented at the five sites in 5.2; D067's three test
    groups all hold, applied verbatim; the five 2FA endpoints covered
    explicitly

3   5.3's differential test holds: identical outcomes at the five
    sites, reached at the same post-session-validation point; today's
    rejection unchanged at the two existing paths; no halt trigger
    fired

4   the three chaining dependencies proved to still inherit AFTER the
    change, each exercised individually

5   the operation → OpenAPI `security` VALUE map is IDENTICAL before
    and after; auth dependency roots proved mandatory; the count and
    method recorded in IMPLEMENTATION_STATUS.md

6   guards 1 and 2 in place, each DEMONSTRATED FAILING when
    deliberately violated; gate 3's revoked-session sweep covers every
    operation in the identity map and is mutation-tested by removing
    the session check from one entry point

7   H069's seven closure criteria pass, applied verbatim, with
    persisted session state asserted on every negative case

8   7.1's three telemetry tests pass as specified — including the
    marker PRESENT at _before_send entry under forced capture

9   the marker is absent from response bodies, logs, audit and
    security-event storage

10  6.3's scoped strip implemented; the preservation control is a
    non-credential RequestValidationError and its value survives

11  7.3's non-secret 422 responses unchanged

12  4.1's step 0 ownership lists produced, protocol executed, both
    patches and both suite results reported — or the split collapsed
    with a stated reason

13  suite green against 656/0/6, every delta explained

14  6.5's claim normalization implemented at both points; malformed
    sid, exp, iat and nbf each produce an authentication failure, not
    a 500; a currently-valid token authenticates unchanged

15  D067 §5's query-shape boundary either regressed with a
    statement-count assertion around each distinct shared
    authentication path, or RECORDED as unmechanised verification debt
    in HARDENING_BACKLOG.md. Criterion 2 asserts §5 is implemented; it
    does not prove the per-request query count. Do not let it stand as
    proof.
```

**On criterion 6.** A guard that has never failed is of unknown strength. Add
a throwaway violating call site, confirm the suite goes red, remove it, report
that you did.

**A halt is not acceptance.** Halting is the designed safe outcome of this
prompt and reporting one correctly is good work — but it means the phase has
not completed. **A halt blocks section 9.3 entirely.** Do not mark H069 Done,
do not mark H153 Done, do not record Q.5.3a-2 unblocked. Report the halt and
stop.

### 9.3 Documentation commit

**The documentation commit happens AFTER Vachan creates the implementation
commit**, as a separate continuation step. It is the only step that can name
the real commit hash. Prepare the text; do not invent a hash, and do not label
an uncommitted working tree as a commit.

```text
IMPLEMENTATION_STATUS.md   phase record; OpenAPI count, method, the
                           security-declaration map result, and the
                           real implementation commit hash
HARDENING_BACKLOG.md       H069 → Done
                           H153 → Done
                           H153 FACT block CORRECTED — its entry-point
                             list omits auth.py:_get_current_admin_user
                           NEW + Done: malformed sid reaches uuid.UUID
                             at deps.py:182 and raises AttributeError,
                             uncaught, producing 500. Fixed in this
                             phase — see 6.5.
                           NEW + Done, LOW severity: malformed exp, iat
                             or nbf raises TypeError inside python-jose
                             3.5.0's int(claim), escaping the
                             repository's JWTError handler, producing
                             500. Requires a VALIDLY SIGNED token;
                             requires no live account or session.
                             Not an exposed attack surface — forging
                             the signature requires JWT_SECRET_KEY.
                             Fixed in this phase — see 6.5.
                           NEW: str(exc) in the 422 message discloses
                             the endpoint's server file path and line
                             number. Established by execution at
                             e9716b1 — see 5.6. Information disclosure,
                             unrelated to H069, NOT fixed in this phase.
docs/HANDOVER.md           phase state; Q.5.3a-2 unblocked
CLAUDE.md                  Workflow section — four parties, not three
docs/WORKFLOW.md           mirror the same
```

Record in the backlog only what this phase observed. Do not write an
unverified fact into a durable document.

---

## 10. Commands

**No bind mount (5.7).** `run` and `exec` both execute the baked image.
Rebuild before any before/after comparison or you test stale code.

```bash
docker compose -f infra/docker-compose.yml up -d --build --force-recreate api
docker compose -f infra/docker-compose.yml exec api sh -c \
  "PYTHONPATH=/app alembic -c apps/api/alembic.ini current"
```

```bash
docker compose -f infra/docker-compose.yml exec -T -e PYTHONPATH=/app api pytest -q
```

```bash
git add -N <path>    # before requesting review of any new file
```

---

## 11. Do not

Mechanical prohibitions only. For what the decisions forbid, read the
decisions — this list does not reproduce them.

```text
do not test this prompt's wording where authority exists — test the
  authority's
do not apply the fix to deps.py only — auth.py has three sites
do not route the five sites through get_current_admin_user_and_session
  as it stands — see 5.3
do not build a decoder-count guard and call it a path guard
do not assert marker-absence at _before_send entry under forced
  capture — see 7.1
do not mock capture_exception
do not strip exception.values[].value unconditionally — 6.3 is scoped
do not change the global 422 handler's ordinary output — 7.3
do not fix the str(exc) path disclosure — record it, do not fix it
do not widen the sid except tuple to AttributeError — use a type
  guard, see 6.5
do not extend 6.5 beyond the two named claim-parsing sites
do not delete tests whose fixtures are wrong — correct the fixtures
do not touch frontend surfaces
do not commit. Do not push.
```

---

## 12. Halt and report immediately if

```text
preflight fails
this prompt and an authority appear to differ
an eighth bearer entry point exists that 5.1 does not list
any mechanical halt trigger in 5.3 fires
a chaining dependency does NOT inherit after the change
the operation → security identity map diverges
guards 1 or 2 cannot be built reliably, or gate 3's sweep cannot reach
  authentication on some operation
the marker reaches any sink after the change
a global 422 change looks necessary
the patch protocol at 4.1 fails at (c), (f) or (g)
6.5's fix changes the outcome for any currently-valid token
a third malformed-input crash surfaces — record it, do not fix it
an accepted rule proves impossible against live code, or two accepted
  rules prove mutually contradictory — Vachan adjudicates, not you
```
