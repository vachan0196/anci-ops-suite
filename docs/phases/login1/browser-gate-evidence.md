# LOGIN1 browser gate evidence

## Result

All three gates passed on 2026-09-17.

All timestamps below are UTC, taken from the `auth_security_events` table,
not from recollection. Recovery codes are never recorded here.

## 2026-09-17 — Gate 1: QR enrolment round trip — PASS

Proves H172.

```text
20:33:52  auth.session.issued                   registration
20:34:01  auth.email_verification.requested
20:34:35  auth.email_verification.completed
20:34:53  auth.2fa.enrolment_started
20:35:50  auth.2fa.enrolment_completed           elapsed 57s, QR scanned with a phone authenticator
20:38:45  auth.session.revoked                  sign out
21:46:17  auth.2fa.verification_succeeded
21:46:17  auth.session.issued
```

The verification and session issuance at 21:46:17 share the same timestamp
and transaction: signed back in with a code from the authenticator.
The round trip, not the scan alone, proves enrolment yields a working factor.

## 2026-09-17 — Gate 2: Manual secret fallback — PASS

Proves H172 preserved manual entry rather than replacing it.

```text
21:16:22  auth.session.issued                   registration
21:16:40  auth.email_verification.completed
21:16:50  auth.2fa.enrolment_started
21:19:37  auth.2fa.enrolment_completed           elapsed 2m47s, 32-character secret typed by hand
```

The measured 57s QR enrolment against 2m47s manual enrolment is the case that H172 was a usability blocker rather than polish.

## 2026-09-17 — Gate 3: Expired challenge recovery — PASS

Proves the H171 residual.

```text
20:51:42  auth.2fa.verification_failed           rejection_reason challenge_expired
```

Observed in the browser: "Your two-factor authentication challenge expired.
Please sign in again." rendered on the sign-in form; challenge state cleared.

In contrast, the [Q.5.3b browser gate evidence](../q5-3b/browser-gate-evidence.md)
records eight `challenge_expired` submissions across two challenges that
neither locked the challenge nor returned the user to sign in.
