# KER v1.16.0

**See your API usage — how many tokens you've spent today, and how many are left.**

The API-keys screen from v1.15.0 now opens with a **usage card**: today's proxy
token spend against your tier's daily allowance, with a progress bar.

- **Metered tiers** (Plus) show `used / limit` with how many tokens remain and a
  bar that turns red when the day's allowance is spent.
- **Pro** shows the running total with an "unlimited" badge — no ceiling.
- When the server has the proxy switched off there is nothing to meter, so the
  card simply doesn't appear.

It reads from a new `GET /v1/usage` endpoint that reports the meter's snapshot
for the caller. Unlike a chat request, it answers even when you are **over** the
limit — so the screen can show "лимит исчерпан" instead of only ever getting a
`429`.

## ✅ Verified

Driven in a real web view: the usage card renders `320 000 / 1 000 000, осталось
680 000` with a filled bar above the key list. On the API side, usage reports
zero on a fresh account, the exact spend after a completion, `remaining: 0` once
over the limit (still `200`, not `429`), unlimited for Pro, and `403` for a Free
account with no API access.

**695 automated tests, all green** — 11 new across the `/v1/usage` endpoint (spend
tracking, over-limit reporting, Pro-unlimited, Free-refused) and the desktop
bridge's usage action (including a graceful "unavailable" when the server has no
proxy).

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
