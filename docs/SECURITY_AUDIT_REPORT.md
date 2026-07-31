# KER — Final Pre-Release Security Audit

**Scope:** production readiness of the KER server (accounts, proxy, memory,
documents) and the desktop client. **Verdict: no CRITICAL or HIGH severity
issues open.** Remaining items are LOW / operator-configuration and are listed
below with mitigations. The project is cleared for release.

## Method

Static review of the codebase against the checklist in
`PRODUCTION_SECURITY_CHECKLIST.md`, plus the automated boot-time self-audit
(`jarvis/security/audit.py`) and the test suite (secrets never logged, ciphertext
on disk, auth paths). Areas reviewed: auth/authz, data-at-rest, transport,
container, API surface, logging, dependencies, config defaults.

## Findings by severity

### 🔴 Critical — none
None found.

### 🟠 High — none
None found.

### 🟡 Medium — none open (all resolved this cycle)

Resolved during this review:

| Was | Resolution |
|---|---|
| Passwords hashed with PBKDF2 only | **Argon2id** default + login-time upgrade |
| User text (memory/chats/docs) stored plaintext | **AES-256-GCM** at rest via `KER_DATA_KEY` |
| No auth audit trail | dedicated `jarvis.security.audit` log (no secrets) |
| OpenAPI docs always public | `API_DOCS_ENABLED` toggle; boot warns when on |
| Insecure config could ship silently | boot-time self-audit logs high/medium findings |

> These become *operator* items only if the deployment leaves the corresponding
> switch off — the boot self-check surfaces that at startup.

### 🔵 Low / operator-configuration (accepted, with mitigation)

1. **TLS is the operator's responsibility.** The app can't provision TLS for
   you. *Mitigation:* Deployment Checklist mandates HTTPS; the current test IP
   default is plain http and documented as test-only.
2. **`KER_DATA_KEY` optional.** Without it, at-rest encryption is off (dev
   convenience). *Mitigation:* boot self-check warns while accounts are on;
   checklist requires it.
3. **`API_CORS_ORIGINS` defaults to `*`.** Needed so local interfaces work out
   of the box; safe because auth is Bearer (no cookies). *Mitigation:* narrow in
   prod; boot self-check flags it.
4. **LLM proxy sees prompt content at inference time.** Inherent to a hosted
   proxy. *Mitigation:* documented; local-model mode (Pro) keeps prompts on the
   device.
5. **Dependency CVE scanning is not yet in CI.** *Mitigation:* `cryptography`
   and `argon2-cffi` pinned to current majors; add `pip-audit`/Dependabot
   (tracked below).

## Not applicable (by design, this release)

- **Cookie flags (HttpOnly/Secure/SameSite):** the API uses Bearer tokens, not
  cookies. Applies only if/when a cookie-based web dashboard ships.
- **OAuth / SSH key encryption:** the server stores neither today; the
  `SecretBox` is ready for them when they arrive.
- **JWT + rotating refresh:** KER uses opaque, revocable, TTL-bound tokens —
  equivalent security with simpler revocation.

## Phase 2 (post-release roadmap)

- KMS **envelope encryption** (master key in KMS, rotation).
- **End-to-end / Zero-Knowledge** for memory, chats, documents and BYOK secrets.
- **Passkeys / WebAuthn** and OAuth sign-in.
- `pip-audit` gate in CI; managed Postgres.

## Release decision

✅ **Cleared for release.** No critical/high issues; medium items resolved; low
items documented with mitigations and tracked for phase 2.
