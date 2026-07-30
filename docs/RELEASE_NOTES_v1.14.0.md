# KER v1.14.0

**"API от меня", done properly — metered and revocable, not a key handed out in the open.**

Pro's promise is "use my API". The obvious way to deliver that — hand the user a
raw provider key — is also the wrong way: a key in someone else's tool can be
copied, shared, and run up without limit, and the only way to stop it is to
rotate the key for *everyone*. This release does it the way it should be done.

## 🔌 A hosted, OpenAI-compatible endpoint

The server now exposes `POST /v1/chat/completions` and `GET /v1/models` in
OpenAI's wire format, so a subscriber points their own tools at KER by changing
only the base URL and the key:

```python
client = OpenAI(base_url="https://your-server/v1", api_key="ker-…")
client.chat.completions.create(model="claude",
                               messages=[{"role": "user", "content": "Привет!"}])
```

Streaming works too (`chat.completion.chunk` SSE, terminated by `[DONE]`). The
proxy forwards to whatever providers the operator already runs — Anthropic,
OpenAI, OpenRouter, a local model — and a requested model resolves to a provider
profile, an OpenRouter `vendor/model` id, or a pass-through override.

## 🔑 Per-account API keys

Keys are minted from the account, shown once, and stored only as a hash — with a
short visible prefix so a person can tell their keys apart without the server
ever holding the secret.

- `POST /auth/api-keys` → `ker-…` (once)
- `GET /auth/api-keys` → metadata only
- `DELETE /auth/api-keys/{id}` → revoked, effective on the **next** request

Because every call is checked against a live account, revocation is immediate:
revoke the key, deactivate the account, or let the licence lapse, and the next
request is refused. One user's key is theirs alone — you cannot revoke or use
another account's key.

## 📊 Metered per tier, and honest about it

A tier is a **daily token allowance**, enforced by a meter that reads how much
the account has already spent today and refuses once the ceiling is reached
(`429` with `Retry-After`):

| Tier | API access | Daily tokens |
|---|---|---|
| Free | — (refused with 403) | — |
| Plus | ✅ | 1,000,000 (configurable) |
| Pro | ✅ | unlimited |

The proxy's counter is separate from the bot's daily *message* counter, because
API access spends tokens far faster than chat does. The on/off is the
`api_access` **entitlement**, never a number that could read as "unlimited" by
accident, and a mislabelled tier gets the tightest allowance rather than a free
pass. A broken ledger keeps the gate shut, never open — a failure can't mint free
tokens.

## ⚙️ Operator switches

Off by default. `PROXY_ENABLED=true` (with `AUTH_ENABLED=true`) turns it on;
`PROXY_PLUS_DAILY_TOKENS` / `PROXY_PRO_DAILY_TOKENS` set the allowances;
`PROXY_MAX_OUTPUT_TOKENS` caps a single request so one call cannot drain a day.
Full guide in `docs/API.md`.

## ✅ Verified

**682 automated tests, all green** — 41 new across the meter's arithmetic
(quotas, overshoot, per-account isolation, a namespace that never touches the
message counter, a broken ledger that stays shut), API-key lifecycle (mint,
hashed storage, scoping, instant revocation, deactivated accounts), and the
endpoint end to end (Plus completes, Free is 403, no key is 401, the daily limit
is 429, Pro is never metered out, a revoked key stops at once, streaming SSE, and
the whole surface returns 404 when disabled).

## 💻 Desktop app
The Windows installer is attached below. Managing keys from inside the app's own
window is the next step; today they are minted over the API.

---
🤖 Built with automated tests and CI on every commit.
