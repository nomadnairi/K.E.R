# K.E.R. Web Dashboard

The browser client for the AI Core. **Not built yet** — `index.html` here is a
placeholder so nginx has something to serve at `dashboard.ker-ai.online`
instead of failing. `make dashboard` copies it into `dist/`, which is what the
nginx container bind-mounts (`dist/` is gitignored, so the placeholder has to
live outside it).

The backend it will use is already in place:

- `POST /api/auth/web/session` — trade a bot-issued code for a session cookie
- `GET  /api/auth/web/session` — who am I
- `GET  /api/auth/me` — tier, limits, capabilities
- `GET  /api/dashboard/plan` — subscription
- `GET  /api/dashboard/sessions` — chat history
- `GET  /api/dashboard/memory` (+ search, delete, forget)
- `GET  /api/dashboard/tasks` — goals
- `GET  /api/dashboard/automations` — schedules and reminders
- `GET  /api/dashboard/devices` — which machines are online
- `GET  /api/auth/api-keys` (+ create, revoke)
- `WS   /api/dashboard/ws` — live state

When building it, reuse `@ker/ui` from `web/packages/ui` — that is what keeps
the dashboard visually identical to the site and the desktop Command Deck.
