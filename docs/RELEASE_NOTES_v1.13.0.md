# KER v1.13.0

**The sign-in screen can now explain itself — and it has a registration tab.**

## 🐞 "Invalid or expired code" was hiding the real problem

Signing in with a Telegram code failed with a bare *Invalid or expired code*,
and that message was almost never the truth. The code flow itself is sound: the
bot issues a code, the API redeems it, and on first use it **creates** the
account. What went wrong was on the other side of the wire — a server with
`AUTH_ENABLED=false` has no accounts to redeem a code into, and an app pointed
at a different address is asking a server that never issued it.

Neither of those is something the old screen could say, because it never asked.

Now it asks. Before anything is typed, the screen probes the server's root
endpoint and reports what it found:

| What the server is | What the screen says |
|---|---|
| accounts on | 🟢 `KER 1.13.0 — аккаунты включены` |
| `AUTH_ENABLED=false` | 🟡 accounts are off here, so neither a login nor a bot code works — set `AUTH_ENABLED=true`, or enter the address of the server that sells the subscriptions |
| nothing listening | 🔴 the server is not answering, with the actual reason |

The probe re-runs when the address is corrected, so a typo is caught while you
are still looking at it.

## 📝 There is a registration tab now

Previously there was **no registration window at all** — the only way to a new
account was a Telegram code, which quietly created one on first use. That is a
fine path, but it was invisible, so it read like a broken login.

Two things changed:

* **A third tab, Регистрация**: login, password, repeat. It appears only when
  the server reports `signup: true`, because offering a form on a server that
  refuses registration is a dead end. `POST /auth/register` is the endpoint,
  gated by `AUTH_ALLOW_SIGNUP` and `AUTH_MIN_PASSWORD_LENGTH`; a taken username
  is a 409, never a silent takeover.
* **The Telegram hint now says what the code actually does** — creates the
  account on first use, Free tier, no separate registration needed.

A new account is nobody special: Free tier, ordinary role. A subscription raises
the tier without changing how you sign in — the operator signs in through the
same form and their account simply unlocks everything.

## 🧹 Screen details

- **One server field, not two.** The account tab and the Telegram tab each had
  their own address box, which invited typing two different servers and then
  wondering why one of them worked.
- Mismatched passwords are caught in the page, in your language, before
  anything reaches the network — and checked again in the app, because a page is
  never the last word.
- The card is capped at 96% of the window height and the form pane scrolls: the
  registration tab is the tallest way in and used to push the error message off
  a short screen where nobody could read it.
- The footer no longer wraps the version onto two lines.
- Dead strings from the removed "this PC" tab are gone.

## ✅ Verified

Driven in a real web view (`ker://deck/login`) against four kinds of server —
signup open, signup closed, accounts switched off, nothing listening — in all
three languages. Each produced the right banner, the register tab appeared and
disappeared as the server dictated, a mismatched repeat was refused in Russian,
and a bad Telegram code left the explanatory banner in place beside it. **No
JavaScript errors in any run.**

**641 automated tests, all green** — 22 new across registration on the API, the
server probe, the sign-in screen's markup, and translation coverage for every
string the screen asks for.

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
