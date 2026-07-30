# Hosted API — "API от меня"

KER can serve **your** models to your subscribers at an OpenAI-compatible
endpoint. A Pro user points their own tools at your server and uses the models
you pay for — without ever holding a raw provider key they could copy, share, or
run up without limit. Every call is authenticated against a live account, so
revocation is instant.

## Turn it on (operator)

```bash
AUTH_ENABLED=true          # accounts are required
PROXY_ENABLED=true         # expose /v1/*
# daily token allowance per tier (0 = unlimited)
PROXY_PLUS_DAILY_TOKENS=1000000
PROXY_PRO_DAILY_TOKENS=0
PROXY_MAX_OUTPUT_TOKENS=4096
```

The proxy forwards to whatever providers the server already has configured
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, a local model).
Only the tiers whose entitlements include `api_access` — Plus and Pro — may
reach it; Free is refused with `403`.

## Get a key (user)

An API key is minted from the account, over the normal login token:

```bash
curl -s https://your-server/auth/api-keys \
  -H "Authorization: Bearer <login-token>" \
  -H "Content-Type: application/json" -d '{"label":"my laptop"}'
# → {"key":"ker-…","note":"Store this now — it is shown only once."}
```

List them (metadata only, never the secret) with `GET /auth/api-keys`; revoke
one with `DELETE /auth/api-keys/{id}` — effective on the very next request.

## Use it

It speaks the OpenAI wire format, so most tools work by changing only the base
URL and the key.

```bash
curl -s https://your-server/v1/chat/completions \
  -H "Authorization: Bearer ker-…" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude","messages":[{"role":"user","content":"Привет!"}]}'
```

With the OpenAI Python SDK:

```python
from openai import OpenAI

client = OpenAI(base_url="https://your-server/v1", api_key="ker-…")
resp = client.chat.completions.create(
    model="claude",                       # or "gpt", "openrouter", "vendor/model"
    messages=[{"role": "user", "content": "Привет!"}],
)
print(resp.choices[0].message.content)
```

Streaming (`"stream": true`) returns Server-Sent Events in the
`chat.completion.chunk` shape, terminated by `data: [DONE]`.

`GET /v1/models` lists the models this server exposes.

### Choosing a model

- a **profile name** (`claude`, `gpt`, `openrouter`, `local`) pins that provider;
- a **`vendor/model`** id is routed through OpenRouter when it is configured;
- anything else is passed through as a model override on the default provider.

## Limits

Each request is metered against the tier's daily token allowance. When it is
spent the proxy answers `429` with a `Retry-After`; Pro (allowance `0`) is never
metered out. The allowance is separate from the bot's daily *message* counter,
because API access spends tokens far faster than chat does.
