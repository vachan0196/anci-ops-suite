# Login.1 — implementation and validation record

Date: 2026-09-17. Uncommitted implementation based on `c73e80b`.

**Complete, with H174 explicitly deferred.** Vachan reports the final backend
suite as **1075 passed / 0 failed / 6 skipped** and all three browser gates
passed on 2026-09-17. See [browser gate evidence](browser-gate-evidence.md).
These final results supersede the earlier implementation-session halt recorded
below; that run is retained as historical evidence, not a current phase blocker.

No recovery-code generation, hashing, normalization, input length or format copy
changed. Existing unused recovery codes remain valid. H174 receives its own
phase and gate because a normalization mismatch fails silently and must not land
at the end of a time-boxed session. Its proposed format was confirmed by Vachan
and is recorded under H174, but remains unimplemented.

## Implemented

- H172: `POST /api/v1/auth/2fa/totp/enrol/begin` adds required string
  `qr_code_data_uri`, an SVG data URI generated from the existing `otpauth_url`
  at response time. Neither provisioning field changes. The UI renders an
  `<img>` with secret-free alt text and keeps the manual key visible underneath.
  The QR is not persisted or logged.
- H171 residual: an expired login challenge returns HTTP 400 with
  `AUTH_2FA_CHALLENGE_EXPIRED`. The challenge form calls the existing abandonment
  callback, restores password sign-in and shows accurate expiry copy. Wrong and
  reused codes retain `AUTH_2FA_INVALID`; counted reasons and the five-attempt
  lock are unchanged.
- H175 items 2–4: enrolment removes `maxLength`, strips whitespace before checking
  and submitting six digits, clears errors on edit and associates errors using
  `aria-invalid` / `aria-describedby`. The native input `pattern` was removed
  because it would reject whitespace before the normalized submit handler ran.

No migrations, frontend dependencies, permission changes or lifecycle UI.
H170 and H175 item 1 remain open.

## Dependency and API contract

Added `segno==1.6.6`, pure Python with no runtime dependencies on Python 3.12
(the package declares `importlib-metadata` only for Python below 3.10). This
keeps the audit surface small under D066. Package identity and SVG serialization were checked against
[PyPI](https://pypi.org/project/segno/1.6.6/) and the
[official Segno documentation](https://segno.readthedocs.io/en/stable/).

The permission matrix records the expiry response. No checked-in generated
OpenAPI artifact was found. Runtime OpenAPI includes the required QR field;
the API still has 89 paths and 112 operations.

## Final validation

Vachan reports **1075 passed / 0 failed / 6 skipped** in the documentation-pass
prompt. The frontend build, standalone TypeScript check and Python audit passed
in the implementation session. Vachan also passed the three browser gates.

`test_phase_q5_1_totp_2fa.py:457` asserts `AUTH_2FA_INVALID`; line 490 asserts
`AUTH_2FA_CHALLENGE_EXPIRED`. The permission matrix was updated for this contract.
`admin-login-form.tsx`, although absent from the prompt's file list, is the
necessary parent half of the expiry fix: it owns and clears `challengeToken`.

## Earlier implementation-session evidence

Docker's CLI reports that Docker is unavailable in this WSL distro. The existing
repository venv also had an outdated dependency set. A fresh temporary Python
3.12 environment at `/tmp/anci-login1-venv` was installed from the current
requirements for validation. This is local suite evidence, not a container
rebuild or PostgreSQL migration result.

- Python audit: exit 0, `No known vulnerabilities found, 2 ignored`, using
  `pip-audit -r apps/api/requirements.txt --ignore-vuln PYSEC-2026-1325`.
  The only explicit suppression is the existing H147 R-2 / D066 acceptance;
  no suppression was added. Output: `/tmp/login1-pip-audit.txt`.
- Focused 2FA suite: **19 passed, 0 failed, 3 skipped**. Existing rate-limit
  tests skip with rate limiting disabled. Output:
  `/tmp/login1-targeted-unsandboxed.txt`.
- Frontend production build: exit 0. Output: `/tmp/login1-web-build.txt`.
- Standalone TypeScript check (`tsc --noEmit`): exit 0, empty capture at
  `/tmp/login1-typecheck.txt`.
- Full backend suite: **653 passed, 2 failed, 9 skipped, 417 setup errors**
  in 351.99 seconds; exit 1. All 417 setup errors report
  `KeyError: 'DATABASE_URL'`. The affected integration fixtures require
  PostgreSQL, and no local service is reachable at port 5432. Output:
  `/tmp/login1-backend-suite.txt`.
- The two assertion failures are in existing
  `test_h069_validation_telemetry.py` tests:
  `test_production_sentry_configuration_does_not_capture_validation_error`
  receives a Sentry sessions envelope where it expects none;
  `test_forced_real_sentry_pipeline_strips_credential_exception_value`
  receives two envelopes where it expects one, with an additional sessions
  envelope. Neither test nor Sentry behavior was changed. The root cause has
  not been established in that session; implementation stopped under AGENTS.md's
  unexpected-test halt rule. This run did not satisfy the backend gate; Vachan's
  subsequent successful full-suite result above is the final gate evidence.

The sandboxed API test process stalled at its first HTTP request and was stopped.
The focused replacement run outside the sandbox completed normally.

The existing enrolment test still asserts `otpauth://totp/`; it now parses the
SVG and compares its module paths to the real encoder's output for that URL,
then checks application and persisted audit logs for the QR field and secret
values. The expiry/lock test now checks both error codes, six successive expiry
rejections with zero counted attempts, and the unchanged fifth-failure lock.
Its clock derives from `date.today()`.

## Deferred work

H174 remains open with a confirmed proposed format, not an implementation. Its
phase must implement and test shared generator/consumer normalization, update
frontend length and copy, record the accepted invalidation and entropy, and run
its own gate. Printed-entry verification of the new format belongs to that phase.
H170 and H175 item 1 remain open.

The three Login.1 browser gates are complete, reported by Vachan. Browser tests
must use a rebuilt API; the earlier Codex session could not rebuild because its
Docker CLI was unavailable. This record does not invent a later rebuild command
or timestamp.
