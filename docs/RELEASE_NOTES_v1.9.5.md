# KER v1.9.5

Real voice in the desktop app, a proper 3D core, and motion that stays smooth
on modest hardware.

## 🎙 Voice actually works now

The dashboard's microphone was decorative — the API had no voice endpoints at
all. Now it does, wired to the same voice service the Telegram bot uses:

- `POST /voice/stt` — upload audio, get a transcription.
- `POST /voice/tts` — get spoken audio back for a reply.
- `GET /voice/status` — honest per-backend availability.

In the app: tap the mic, speak, and your words are transcribed, sent to the
engine, and (when TTS is configured) the answer is spoken back. If a backend
isn't configured the endpoint returns a clear **503** — it never fakes a result.

## 🌀 A real 3D core, tuned for weak machines

- The WebGL reactor is now the centrepiece of the Home screen (it had shrunk to
  a 64 px thumbnail) with the name, live status and capability chips beneath it.
- **Performance governor**: detects low-end hardware (cores / memory), caps the
  frame rate, scales render resolution to the measured frame cost, and **stops
  drawing entirely** whenever the Home screen isn't visible or the window is
  hidden — no GPU burn in the background. If a machine still can't keep up it
  steps down gracefully and finally falls back to the CSS reactor.
- Honours `prefers-reduced-motion` and the in-app "animations off" switch.

## ✨ Motion & polish

- Spring-y press feedback and a click ripple on every button, card and row.
- Smooth screen transitions, staggered card entrances, animated chat bubbles,
  a pulsing mic while recording.
- Provider failures now read like a product, not a stack trace: *"Ключ
  AI-провайдера отклонён. Проверьте API-ключ в Настройках → AI."*

## 🔧 Fixes

- **Real CPU / memory telemetry in the exe** — `psutil` was missing from the
  desktop build, so those panels always showed "—".
- Capability chips are back on Home (they were lost in the 1.9.4 redesign).
- No more 404 favicon request in the embedded view.
- The API no longer fails to start when `python-multipart` is absent; the
  upload route degrades to a clear 503 instead.

**519 automated tests, all green** — including new tests covering every voice
endpoint (success, empty upload, unconfigured backend) and real telemetry.

## 💻 Desktop app
Windows installer and portable build are attached below. Choose **"Continue
locally"** on sign-in to run standalone with the live dashboard.

---
🤖 Built with automated tests and CI on every commit.
