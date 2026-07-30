# KER v1.15.0

**Manage your API keys from inside the app — no curl required.**

v1.14.0 added the hosted proxy ("API от меня") but keys could only be minted over
the API with a `curl` call. Now there is a screen for it, right in the app's own
window.

## 🔑 An API-keys screen in the deck

A new **API-ключи** section in the rail, gated on the `api_access` entitlement —
so a Free account sees it locked with "available in Plus", and a Plus or Pro
account sees the real thing:

- **Create a key** with an optional label. The plaintext `ker-…` is shown
  **once**, in a highlighted panel with a Copy button, and never again — exactly
  as the server stores it (only the hash, plus a short prefix).
- **See your keys** — each row shows its prefix, label, when it was created, and
  whether it has been used. The secret itself never comes back.
- **Revoke** any key with one button; it stops working on the very next request.
- A short **how-to** block shows the ready-to-paste `base_url`, key and model
  line for an OpenAI-compatible client.

Everything runs over the same native bridge as the rest of the deck — the page
holds no credential of its own, and the create/list/revoke calls go straight to
the account on the server.

## 🧹 Also

- The home screen's version chip now shows the real running build instead of a
  stale hard-coded number.

## ✅ Verified

Driven in a real web view (`ker://deck/`): a Plus account opens the screen,
creates a labelled key (the plaintext appears once, the list shows only the
prefix), and revokes it (the row disappears); a Free account finds the section
locked. **No JavaScript errors.**

**688 automated tests, all green** — new coverage across the desktop bridge's
key actions (create returns the secret once, list carries metadata only, revoke
by id) and the deck's markup (the screen exists, is gated on the entitlement, and
reveals the secret exactly once).

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
