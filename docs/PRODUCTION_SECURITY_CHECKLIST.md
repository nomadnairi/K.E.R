# KER — Production Security Checklist

Pass every item before serving real users. Grouped by the areas a reviewer (or
an automated scanner) checks. ✅ = enforced/available in KER; ⚙️ = operator must
configure.

## Authentication & authorization

- [x] Passwords hashed with **Argon2id** (scrypt fallback); legacy PBKDF2
      upgraded on login. ✅
- [x] Login tokens, API keys, licence keys stored **hashed** (SHA-256); shown
      once. ✅
- [x] Constant-time secret comparison (`hmac.compare_digest`). ✅
- [x] Tokens are short-lived (`AUTH_TOKEN_TTL_HOURS`) and **revocable**;
      revoking a key/deactivating an account cuts access on the next request. ✅
- [x] Entitlements enforced server-side for what the server performs (models,
      images, API access, quotas). ✅
- [ ] ⚙️ `OWNER_PASSWORD` is long and unique (≥12 chars; boot self-check warns
      otherwise).

## Data protection

- [x] Memory, chats and documents encrypted at rest with **AES-256-GCM** when a
      key is set; AAD binds ciphertext to its owner. ✅
- [ ] ⚙️ `KER_DATA_KEY` set from a secret manager / KMS (boot warns if missing
      while accounts are on).
- [x] Per-account isolation by `principal` everywhere (memory, documents,
      quotas). ✅
- [x] Secret redaction before memory storage and in the audit log. ✅
- [x] No plaintext secret is stored: passwords/tokens/keys hashed, user text
      encrypted, provider keys from env. ✅

## Transport & network

- [ ] ⚙️ **HTTPS/TLS** in front of the API (PaaS domain or Caddy/nginx + Let's
      Encrypt). *The single most important remaining item.*
- [x] One port exposed (8000); the container binds only that. ✅
- [ ] ⚙️ `API_CORS_ORIGINS` narrowed from `*` to your origins.

## API surface

- [x] OpenAPI docs can be turned off (`API_DOCS_ENABLED=false`); boot warns if
      on. ✅ / ⚙️
- [x] The proxy does not log request/response bodies. ✅
- [x] Errors return generic messages upstream (no stack traces to callers). ✅
- [ ] ⚙️ `API_KEY` set, or accounts required — no unauthenticated API in prod.

## Container & runtime

- [x] Runs as a **non-root** user (uid 1000). ✅
- [x] Slim base image, no secrets baked in, `.env` never copied with values. ✅
- [x] `data/` and `logs/` are volumes; DB/audit persist. ✅
- [ ] ⚙️ Secrets injected at runtime from the platform's secret store.

## Logging & audit

- [x] Auth events (login ok/fail, account create, key create/revoke, owner
      bootstrap) recorded to `jarvis.security.audit` with **no secrets**. ✅
- [x] Capability use (files/shell/desktop) audited by the security manager. ✅
- [ ] ⚙️ Ship logs to your platform/SIEM and set retention.

## Dependencies & supply chain

- [x] `cryptography` and `argon2-cffi` pinned to current majors. ✅
- [ ] ⚙️ Run `pip-audit` (or Dependabot) in CI and before each release.
- [x] Token-leak guard before pushes; no secrets in the repo. ✅

## Compliance posture (when scaling)

- [ ] Privacy Policy, Terms of Service, and a DPA listing sub-processors
      (LLM providers, hosting, payments).
- [ ] Data-erasure and export paths documented and tested.
- [ ] Incident-response plan; breach notification target ≤72h (GDPR).

> Boot-time self-check: the server logs any `high`/`medium` finding on startup
> (`jarvis/security/audit.py`). A clean start = no such warnings.
