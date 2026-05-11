# Supply Chain Audit — Existing Dependencies

**Date:** 2026-05-11  
**Product:** ForecourtOS / Anci Ops Suite  
**Scope:** Existing direct Python and npm dependencies after Phase Q.2.2

## Purpose

This audit checks existing direct dependencies for slopsquat / hallucinated package risk after Q.2.2 introduced future dependency controls.

Q.2.2 prevents future unverified dependency additions. This audit reviews the dependencies already present in the project.

## Checks performed

- Extracted direct Python dependencies from `apps/api/requirements.txt`.
- Extracted direct npm dependencies from `apps/web/package.json`.
- Checked Python packages exist on PyPI.
- Checked npm packages exist on the npm registry.
- Ran Python known-vulnerability audit using `pip-audit`.
- Ran npm high-severity audit using `npm audit --audit-level=high`.
- Ran basic secret/path grep checks.
- Reviewed dependency names for obvious hallucination / typo / slopsquat risk.

## Results summary

### Python

- Registry existence check: TODO
- `pip-audit -r apps/api/requirements.txt`: No known vulnerabilities found.

### npm

- Registry existence check: TODO
- `npm audit --audit-level=high`: Passed after `npm audit fix`.
- Remaining npm advisories: Moderate Next/PostCSS advisory remains.
- Decision: Do not run `npm audit fix --force` because it would introduce a breaking/unsafe Next.js downgrade.

### Secrets

- Secret grep found no real committed secrets.
- `apps/web/.env.local.example` exists and is expected as an example file.

## Suspicious packages requiring follow-up

TODO: Add any packages with NOT FOUND, low downloads, suspicious names, or unclear maintainers.

## Final decision

TODO: Mark one:

- No slopsquat-style anomalies found.
- Issues found and remediated.
- Issues found and deferred with justification.

## Sign-off

Reviewed by: Vachan Sardar  
Date: 2026-05-11
