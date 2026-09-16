# Q.5.3b browser gate evidence

## Result

Passed on 2026-09-16, with the H171 and H173 frontend changes in place.

All times below are UTC. Recovery codes are never recorded here.

## 2026-09-14 — throwaway `soloo@gmail.com` (`8f8c8cf1…`), before H171/H173

Passed:

- enrolment via manual key entry
- ten recovery codes displayed once (D039 Decision 7)
- login under 2FA returns the challenge, not a session (H130 login-lockout
  defect proved fixed)
- TOTP login establishes a normal admin session
- five wrong codes lock the challenge and return to sign-in
- the `/2fa/verify` route limiter fires at 5/minute

Not proved that session: recovery-code login and used-code rejection.
`auth_tokens` showed ten `recovery_code` rows, all `used_at` NULL, afterwards.
Vachan confirmed on 2026-09-15 that every recovery-code attempt that session
pasted all ten codes into the input at once. See H173.

`yooloo@gmail.com` (`3fa74d6b…`) enrolled at 18:48–18:53 and was abandoned.
Neither account is the standing development owner.

## 2026-09-15 — throwaway `sampo@gmail.com`, before H171/H173

Passed:

- recovery-code login establishes a normal admin session
- a used recovery code is rejected on resubmission
- a different unused code still succeeds after that rejection

```text
19:56:57  auth.2fa.enrolment_started
19:59:14  auth.2fa.enrolment_completed
20:02:21  auth.2fa.verification_failed     invalid_code   all ten codes pasted
20:03:03  auth.2fa.verification_succeeded
20:03:03  auth.2fa.recovery_code_used
20:10:42  auth.2fa.verification_failed     invalid_code   used code resubmitted
20:11:46  auth.2fa.recovery_code_used
20:11:46  auth.2fa.verification_succeeded
```

`auth_tokens` afterwards: 2 used, 8 unused. The reused code showed the old
authenticator copy in recovery-code mode. See H171.

## 2026-09-16 — throwaway `popo@gmail.com`, with H171/H173

Stack: api and mailpit recreated with a fresh `TOTP_ENCRYPTION_KEY`,
`EMAIL_BACKEND=local_smtp`, `APP_BASE_URL=http://localhost:3000`. Backend suite
before the run: 1075 passed, 0 failed, 6 skipped. Alembic head:
`0035_coverage_templates_overnight`.

Vachan reported every step below as passed.

Enrolment:

- "When you sign in, enter one code at a time, exactly as shown." displayed
- Download codes (.txt) produced `admin-portal-recovery-codes.txt`: ten lines,
  32 characters each, nothing else

Client-side checks. These produce no server event. The copy shown exists only
in the client check and cannot come from the server.

- a five-digit value in authenticator mode showed the 6-digit message
- all ten codes pasted in recovery mode showed "This is longer than one
  recovery code."
- one code missing its last character showed "This is shorter than a recovery
  code."

Server-verified:

```text
18:54:34  auth.2fa.enrolment_started
18:56:47  auth.2fa.enrolment_completed
19:05:18  auth.2fa.verification_failed     invalid_code        not attributed to a step
19:08:27  auth.2fa.verification_failed     challenge_expired
19:08:52  auth.2fa.verification_failed     challenge_expired
19:09:30  auth.2fa.verification_failed     challenge_expired
19:10:10  auth.2fa.verification_failed     challenge_expired
19:10:57  auth.2fa.verification_failed     challenge_expired
19:11:16  auth.2fa.recovery_code_used                          one code, exact
19:11:16  auth.2fa.verification_succeeded
19:12:21  auth.2fa.verification_failed     invalid_code
19:12:37  auth.2fa.recovery_code_used                          different unused code
19:12:37  auth.2fa.verification_succeeded
19:48:45  auth.2fa.verification_failed     invalid_code        unused code, one letter's case changed
19:50:19  auth.2fa.verification_failed     invalid_code        already-used code
19:53:48  auth.2fa.verification_failed     challenge_expired
19:53:53  auth.2fa.verification_failed     challenge_expired
19:54:04  auth.2fa.verification_failed     challenge_expired
19:54:39  auth.2fa.verification_succeeded                      authenticator code, no recovery code used
```

`auth_tokens` afterwards: 2 used, 8 unused. The case-changed code did not
consume the real code.

Proved:

- recovery-code login, twice
- used-code rejection
- a code with changed letter case is rejected and not consumed
- authenticator login after recovery-code use

H171 observed live: eight `challenge_expired` submissions across two
challenges. Expired attempts do not count toward the lock, so neither
challenge locked or returned to sign-in.

## Panel diff review

`GPT-6 Astra`, `Medium`, at `2ac1ad5`. No blocking finding. Four SHOULD FIX
findings on the enrolment screen and on bfcache restoration are logged as H175.
One NOTE, that 32 non-whitespace characters of any kind pass the client check,
is the length-only design recorded in H173.
