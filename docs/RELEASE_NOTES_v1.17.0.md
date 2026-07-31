# KER v1.17.0

**A big one: MCP servers, document intelligence, an owner account from one env
var, a baked-in server address — and a real security pass (Argon2id + encryption
at rest).**

## 🖥 MCP servers, managed in the app

A real **API-ключи**-style screen for external tool servers: list your MCP
servers, add one (a stdio command + args, or an SSE URL) with the config
validated, remove one — each with its live status (connected · tool count) from
the running engine. Servers live in the app config and the engine rebuilds to
mount their tools. Pro capability.

## 📄 Document Intelligence

Give KER a document and it answers from the contents. Ingest splits a file into
overlapping passages, embeds and stores them; questions return the closest
passages across your library with the source named. SQLite-backed, per-account,
and (see below) **encrypted at rest**.

## 👤 Owner account from the environment

Set `OWNER_USERNAME` and `OWNER_PASSWORD` in the server env and the owner account
is created (or its password realigned) on startup — sign in on the **Account**
tab and everything is unlocked. No CLI step.

## 🌐 The app knows your server

The sign-in screen no longer shows a deceptively empty address box behind a grey
placeholder (the "enter the server" trap). It prefills the operator's baked-in
address (`KER_SERVER_URL` / `DEFAULT_SERVER_URL`) — a customer never types one —
and an empty server is caught in the user's own language.

## 🔒 Security pass

- **Passwords → Argon2id** (memory-hard; scrypt fallback). Old PBKDF2 hashes
  upgrade automatically on the next login — no password reset.
- **AES-256-GCM at rest** for memory, chat history and documents, keyed by
  `KER_DATA_KEY` from your secret manager (never in source). On disk it is
  ciphertext; in memory, plaintext. No key = transparent (dev).
- **Auth audit log** — logins, account/key create & revoke, owner bootstrap —
  with identifiers and outcomes only, never secrets.
- **Boot-time self-audit** warns about insecure production config (no encryption
  key, public `/docs`, wildcard CORS, weak owner password).
- **`API_DOCS_ENABLED=false`** hides the OpenAPI surface in production.
- New docs: `SECURITY_ARCHITECTURE.md`, `SECURITY.md`, `DEPLOYMENT_CHECKLIST.md`,
  `PRODUCTION_SECURITY_CHECKLIST.md`, `SECURITY_AUDIT_REPORT.md` (no
  critical/high issues open).

## ✅ Verified

All new surfaces driven in a real web view (MCP + API-key screens, sign-in in
four server states) with no JavaScript errors; encryption confirmed as
ciphertext on disk and plaintext in memory; the audit log confirmed to carry no
secrets. **750 automated tests, all green** (~90 new across MCP, documents, the
cipher, Argon2id, at-rest encryption, the owner bootstrap and the hardening
audit).

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
