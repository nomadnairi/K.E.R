# KER v1.12.0

**Sign in, and the app becomes what your subscription says it is.**

## 🔑 One ordinary way in

The sign-in screen has two tabs now: **username and password**, or a **Telegram
login code**. The "this PC" shortcut is gone — everyone signs in the same way,
the operator included. Their account simply unlocks everything.

The token is remembered, so you are not asked again. If the server cannot be
reached, the app still opens with the plan it last confirmed rather than
locking you out of a session you already had.

## 🐞 There was no Free tier at all

Signing in **required an active licence**, so an account with no subscription
was turned away at the door. A product with a Free tier cannot work that way:
nobody can see what they would be buying. A licence now decides your *tier*, not
whether the door opens. Operators selling licence-only can restore the strict
door with `AUTH_REQUIRE_LICENSE=true`.

## 🎚 A tier is a set of capabilities

Not `if plan == "pro"` scattered through the code — one table
(`jarvis/billing/entitlements.py`) mapping tiers to what they unlock. Adding a
new tier later is an entry in that table.

| | Free | Plus | Pro |
|---|---|---|---|
| Messages a day | 10 | 100 | unlimited |
| Chat, memory, integrations | ✅ | ✅ | ✅ |
| Web search, voice, all models, images | — | ✅ | ✅ |
| PC access, MCP, local models, log | — | — | ✅ |

The server answers `/auth/me` and `/dashboard/plan` with the tier, the
capabilities, the real limits and today's usage. The interface asks; it never
decides a tier for itself.

**On honesty about enforcement.** The module says plainly which capabilities
the server can genuinely refuse (message allowance, images, models, API access)
and which run on the user's own machine — files, shell, MCP, local models. The
second group is *packaging*, not security: the engine runs those locally, the
server never sees the call, and the core is open source. Pretending otherwise
would be a lie in the code. What a subscription really buys is access to the
model; a local assistant with no brain is an empty box.

## 🖥 The window follows the plan

- A **Тарифы** screen: your tier, who you signed in as, messages used and left
  today, integration allowance, support level, and every capability marked
  included or "в Plus / в Pro".
- Sections outside your plan stay visible with a lock and what unlocks them,
  instead of quietly disappearing — you can see what you would get.
- The rail carries a small badge with your tier.
- Where the engine runs is derived, not toggled: an account entitled to local
  powers *and* holding a key runs it here; everyone else uses the server.
- When the server is unreachable the plan screen says so instead of showing
  stale numbers as if they were current.

## ✅ Verified

Against a real server with two real accounts: a Free user signs in and gets
`free` with chat, memory and integrations — models, internet, MCP and the log
show as locked, the plan screen reads "0 / 10, осталось 10", and the voice
settings panel says "Доступно в Plus ⭐". The operator account signs in and
nothing is locked at all. No JavaScript errors.

**619 automated tests, all green** — 20 new across entitlements, the profile
endpoint, sign-in without a licence, and the desktop's plan cache.

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
