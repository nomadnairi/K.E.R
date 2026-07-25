# KER v1.10.0

**The exe is the interface.** Everything the design promised now actually
renders inside the Windows app — including the way in.

## 🩹 Why the app didn't look like this before

Two real defects, both found by driving the app rather than reading the code:

1. **The build threw the web view away.** The packaging spec listed
   `PySide6.QtWebEngineCore` and `QtWebEngineWidgets` under *excludes*, so the
   binary shipped without a web view and the app quietly fell back to plain
   widgets. That is why the exe showed a grey dialog while the interface looked
   right everywhere else. WebEngine (and the Quick/QML stack it stands on) is
   now bundled, and a test fails if it is ever excluded again.
2. **The interface couldn't reach its own engine.** The window's page sits on a
   different origin than the local API, and the API sent no CORS headers, so
   the browser blocked every request — CPU, memory, model, provider and voice
   all rendered as "—" no matter how healthy the engine was. The API now
   answers with the right headers (`API_CORS_ORIGINS`, open by default since
   requests carry a key).

The binary grows to roughly 300–400 MB. That is the web view; it is what the
interface is made of.

## 🔐 A way in that belongs to the product

The plain Qt login dialog is gone. Signing in now happens in
`static/desktop_login.html` — the deck's design, the deck's motion, the user's
language — with all three real paths: **this PC**, **account**, and a
**Telegram login code** from the bot. Choosing local mode is remembered, so an
owner is not asked again on every launch.

## 🎛 One window, and every switch does something

The app is the deck: no native header duplicating the wordmark, no tab bar, no
second design language. The settings inside it are wired to the real config
through a native bridge, and the app acts on each change immediately —

- **Интерфейс** — language, theme (both layers restyle at once), notifications,
  tray behaviour, start with the system (writes the real autostart entry)
- **Ассистент** — rename your assistant; the new name shows up everywhere
- **AI** — provider, model, Anthropic and OpenAI keys, **and the engine
  restarts itself** so a key works the moment you save it
- **Доступ к ПК** — file read/write, shell, desktop control, workspace root,
  shown next to what the running engine currently enforces
- **Голос** — STT/TTS backends and voice, next to a live `/voice/status` check
- **Интеграции** — weather, Home Assistant, Telegram
- **Обновления** — auto-update and channel, persisted for real
- **Журнал** — the log file as it is on disk, with optional auto-refresh

Secrets never travel back to the page: it is told *whether* a key is set, never
what it is, and saving an empty field keeps the key you already had. The page
may only write fields on an allow-list, and values outside the allowed set are
refused.

The microphone is granted to the interface, so the mic button records for real.

## ✅ Verified, not assumed

Checked by driving the actual app under a real Qt/Chromium session: the sign-in
screen renders in Russian with all three ways in; clicking *Продолжить локально*
really signs in and writes the config; the deck loads with 38 live config
fields; flipping a switch lands in `desktop.json` **and** reaches the app; the
log view shows the real file. One JavaScript error found this way and fixed
(the model catalogue was loading before its own state existed).

**556 automated tests, all green.**

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
