# K.E.R. — repo routing rules

Two git remotes point at two GitHub repos with the same working tree:

- `origin` → `nomadnairi/K.E.R` (public). Home of desktop-client releases
  (`desktop-build.yml` builds the `.exe` from whatever is on the tagged
  branch here).
- `server` → `nomadnairi/K.E.R-server` (private). Everything server-side:
  API, Telegram bot, billing, infra (Nginx/Docker/Let's Encrypt), VPS
  topology, ops docs.

## Push routing

Push based on what the work actually touches — **do not push the same
commit to both remotes by default.**

- Desktop client work (`jarvis/desktop_app/**`, installer/PyInstaller specs,
  desktop-only UI/strings) → push to **`origin` only**.
- Server/bot/infra work (`jarvis/api/**`, `jarvis/interfaces/telegram_bot.py`,
  billing, licensing internals, `docker-compose*.yml`, `deploy/**`, VPS/ops
  docs) → push to **`server` only**.
- Shared/core code that both sides import (`jarvis/config/settings.py`,
  `jarvis/security/**`, `jarvis/licensing/**`, `jarvis/core/**`, etc.) →
  push to **`server`** during day-to-day work (private repo is the source of
  truth). It reaches `origin` at release-cut time (see below) — don't push
  it to `origin` piecemeal.

## Release-cut sync (still "один релиз в конце" — batch, don't trickle)

`origin`'s branch has to be a fully buildable snapshot the moment a version
tag is pushed there (the exe build checks out that exact ref). So right
before cutting a release: merge/fast-forward `origin`'s branch to include
whatever shared-core commits have accumulated on `server` since the last
release, verify the build, tag, push. Don't do this sync on every commit —
only when a release is actually about to be cut.

If unsure which bucket a change falls into, ask rather than guessing and
pushing to the wrong repo.

## Pending — bring these up again

- **Domain / DNS / real HTTPS.** User has no domain yet (paused
  01.08.2026). `docker-compose.prod.yml` + `deploy/nginx/` are ready and
  waiting (`CERTBOT_STAGING=1`) — see `docs/INFRASTRUCTURE.md`. Once a
  domain exists: DNS A record → `2.26.80.6` (or whatever the VPS IP is by
  then) → `deploy/nginx/init-letsencrypt.sh` on the VPS. **Remind the user
  about this periodically until it's done** — they explicitly asked not to
  let it drop.

## Design principle for future exe/desktop-control work (not started yet)

When the desktop app's "do this on my PC" commands (e.g. "open YouTube") get
built out: **no hardcoded command table.** The user was explicit — this is
not "match the phrase 'open X' in code and run a scripted action," it's the
LLM recognizing intent and invoking a real tool call (agentic, via the
existing tool-calling/Desktop Control plumbing), the same way any other tool
use works in this codebase. Don't regress to a keyword/regex command parser.
