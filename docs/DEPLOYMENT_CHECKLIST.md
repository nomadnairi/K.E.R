# KER — Deployment Checklist

Steps to stand up a KER server for real users. Work top to bottom; the
security-specific items are expanded in `PRODUCTION_SECURITY_CHECKLIST.md`.

## 1. Host

- [ ] Pick a host: a managed platform (Railway / Render / Fly.io) is simplest —
      it runs the container, gives a **free HTTPS domain**, and offers a managed
      volume/DB, so data lives off your own machine.
- [ ] Or a VPS + Docker (`Dockerfile` is provided, runs as non-root on port 8000).

## 2. TLS / domain (required for real users)

- [x] On a VPS: `docker-compose.prod.yml` provides the reverse proxy with TLS
      (Nginx + Let's Encrypt, auto-renewing) — see `docs/INFRASTRUCTURE.md` for
      the full setup and domain/DNS steps. On a PaaS this is automatic instead.
- [ ] Point DNS at the server and run `deploy/nginx/init-letsencrypt.sh` once
      (`docs/INFRASTRUCTURE.md` — "Настройка домена").
- [ ] Never expose plain `http://` to customers — logins and keys would travel
      in clear text.
- [ ] Point the app's baked default (`KER_SERVER_URL` / `DEFAULT_SERVER_URL`) at
      the **https** address before building the exe.

## 3. Configuration (`.env`)

- [ ] `AUTH_ENABLED=true`
- [ ] `OWNER_USERNAME` + `OWNER_PASSWORD` (long, unique) — creates your owner
      account on startup.
- [ ] `KER_DATA_KEY` = `python -c "from jarvis.security.crypto import KeyProvider; print(KeyProvider.generate())"` — from your secret manager, **not** committed.
- [ ] `API_DOCS_ENABLED=false` in production.
- [ ] `API_CORS_ORIGINS` narrowed to your own origins (not `*`).
- [ ] `PROXY_ENABLED=true` if you sell hosted API access; set the per-tier token
      limits.
- [ ] Provider keys (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY`)
      from the secret store.
- [ ] `BILLING_*` if selling via Telegram Stars / a payment webhook.

## 4. Secrets

- [ ] All secrets come from the platform's secret manager / KMS — never in the
      image, the repo, or logs.
- [ ] `.env` is git-ignored; rotate anything that ever leaked.

## 5. Data & backups

- [ ] Persist `data/` and `logs/` on a durable volume (the image declares them
      as volumes).
- [ ] Enable the platform's automated backups for the database.
- [ ] Confirm the retention/erasure path: an account can be deleted and its
      memory/chats/documents cleared.

## 6. Bot & clients

- [ ] Telegram bot token set; `TELEGRAM_ALLOWED_USERS` if the bot should not be
      public.
- [ ] Build and publish the desktop installer (CI `desktop-build.yml`) pointing
      at the production server URL.

## 7. Launch checks

- [ ] `GET /health` returns ok.
- [ ] `GET /` reports `accounts: true`, `proxy` as intended.
- [ ] Owner can sign in from the app and sees everything unlocked.
- [ ] A test Free account is limited as expected.
- [ ] Startup log shows **no `high`/`medium`** security warnings (the server
      self-audits on boot).
- [ ] `/docs` is **not** reachable in production.
