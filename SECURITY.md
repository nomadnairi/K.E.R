# Security

J.A.R.V.I.S. can act on your machine (files, shell, desktop) and your home
(smart devices). That power is governed so it is **safe by default** — but you
should understand the model before enabling the powerful bits.

## Safe by default

Dangerous capabilities are **off** out of the box and must be turned on
explicitly:

| Capability | Setting | Default |
|------------|---------|---------|
| Write files | `ALLOW_FILE_WRITE` | off |
| Run shell commands | `ALLOW_SHELL` | off |
| Control the desktop | `ALLOW_DESKTOP_CONTROL` | off |
| Read files | `ALLOW_FILE_READ` | on (sandboxed) |

Every attempt — allowed or denied — is checked by the **security module**
(`jarvis/security`) and written to an audit log (`AUDIT_LOG_PATH`) with secrets
redacted.

Other built-in protections:

- **Filesystem sandbox** — file tools are confined to `WORKSPACE_ROOT`; paths
  that escape it (`..`, absolute paths, symlinks) are rejected.
- **Secret redaction** — tokens, API keys and card-like numbers are stripped
  before anything is written to memory, history or the audit log.
- **Rate limiting** — per-session token bucket (`RATE_LIMIT_*`) guards against
  abuse and runaway cost.
- **Input validation** — e.g. Home Assistant entity ids are pattern-checked so
  a model-supplied value can't escape the API path.
- **Safe evaluation** — the calculator uses a restricted AST walker, never
  `eval`. All database access is parameterised (no SQL injection).

## Threat model & guidance

The main residual risk with any LLM agent is **prompt injection**: untrusted
text (a file you ask it to read, a web/API result, a message from another user)
could contain instructions trying to make the model call a dangerous tool.

Mitigations already in place: dangerous capabilities are off by default, gated,
and audited. To stay safe:

- **Never enable `ALLOW_SHELL`, `ALLOW_FILE_WRITE` or `ALLOW_DESKTOP_CONTROL`
  on a publicly reachable bot.** Combined with an open `TELEGRAM_ALLOWED_USERS`,
  that would let anyone drive those tools.
- On a shared bot, set `TELEGRAM_ALLOWED_USERS` to trusted user ids.
- Point `WORKSPACE_ROOT` at a dedicated folder, not your home directory.
- Keep secrets (API keys, bot tokens) in `.env` only — never commit them. If a
  token leaks, revoke it (e.g. `/revoke` in @BotFather) and issue a new one.
- Review the audit log when you enable powerful capabilities.

## How your data is protected (server deployments)

When KER runs as a service with accounts (`AUTH_ENABLED=true`):

- **Passwords** are hashed with **Argon2id** (memory-hard; scrypt fallback).
  Legacy PBKDF2 hashes are upgraded automatically on the next login. The
  plaintext password is never stored.
- **Login tokens, API keys and licence keys** are stored only as **SHA-256
  hashes**; the plaintext is shown once and never persisted.
- **Memory, chat history and documents** are encrypted at rest with
  **AES-256-GCM** when `KER_DATA_KEY` is set (from your secret manager / KMS).
  The encryption key never lives in source or the repository.
- **Auth events** (logins, key create/revoke, owner bootstrap) are written to a
  security audit log with **identifiers and outcomes only** — never secrets.
- **Local-only capabilities** (files, shell, desktop, MCP, local models) run on
  the user's own machine; the server never receives those calls.

See `docs/SECURITY_ARCHITECTURE.md` for the full model, and
`docs/PRODUCTION_SECURITY_CHECKLIST.md` before going live.

## Supported versions

Security fixes land on the latest minor release. Run a current version — the
desktop app can auto-update, and the server is a `pip install -U` / redeploy.

## Reporting a vulnerability

Found a vulnerability? Please report it **privately** via
[@deathgu11](https://t.me/deathgu11) rather than opening a public issue, and
allow reasonable time for a fix before any public disclosure. Include steps to
reproduce and the affected version. We aim to acknowledge within 72 hours.
