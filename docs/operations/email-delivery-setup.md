# Production email delivery setup

This is an operational record of external state completed on 2026-09-20. The
repository cannot itself prove provider account state, sending-domain
verification, or DNS records; D038's 2026-09-05 amendment identifies those as
external operational state.

| Field | Value |
| --- | --- |
| Provider | Resend, per D038's 2026-09-03 amendment |
| Sending domain | `mail.siteoverview.uk` — a dedicated subdomain, per D038's requirement that sending reputation be isolated from the primary domain |
| Region | `eu-west-1` (Ireland) |
| Registrar/DNS | Cloudflare |
| Verified | 2026-09-20 17:56 UTC (DNS verified 17:54) |

## DNS records

All records have Proxy status **DNS only**. Proxying breaks mail records.

```text
TXT    resend._domainkey.mail   DKIM public key
CNAME  rsend.mail               SPF
CNAME  send.mail                sending
TXT    _dmarc                   v=DMARC1; p=none; rua=mailto:<address>
```

Cloudflare appends the zone automatically, so record names are entered relative
to the zone. Entering a fully qualified name produces a doubled suffix and
verification fails.

## Credential handling

The API key has sending-access scope and is restricted to `mail.siteoverview.uk`.
It is held outside the repository. Per D068 rule 5, no live credential exists
on a development machine; H180 owns production injection.

The key, any part of it, and its name pattern must not be recorded in this or
any repository file.

## Product naming

The product is now named **siteoverview**, while the repository and all
governing documents still say **ForecourtOS**. This divergence is tracked
separately.
