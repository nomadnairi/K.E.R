# KER v1.9.7

**The desktop app now has its own interface.**

## 🖥 Desktop and web are separate products

Until now the app and the browser dashboard rendered the *same* HTML file, so
neither could change without dragging the other along. They are now split:

| | File | Purpose |
|---|---|---|
| **KER Desktop** (the exe) | `static/desktop.html` | the app's own interface — everything in this release's design: 3D core, four themes, live telemetry, voice |
| **Web dashboard** | `static/dashboard.html` | the browser product, served at `/app`, free to become something entirely different |

The exe reads **desktop.html** and nothing else; the API serves the dashboard.
Both are bundled in the build, and five tests pin the split so the two can
never quietly merge back into one file.

Nothing about the app's look changes in this release — it keeps the one-window
Command Deck, the four shared themes and the ~52 fps 3D core. What changes is
that the desktop interface is now **its own thing**, and the web dashboard can
be redesigned from scratch without touching the app.

**529 automated tests, all green.**

## 💻 Desktop app
Windows installer and portable build are attached below.

---
🤖 Built with automated tests and CI on every commit.
