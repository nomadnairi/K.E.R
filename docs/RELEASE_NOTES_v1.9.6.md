# KER v1.9.6

One app, one look — and four themes to pick from.

## 🪟 The app is now a single window

The desktop app used to be a styled web deck sitting inside a default Qt frame
with native tabs that duplicated it. Now the **Command Deck fills the window**
and everything day-to-day lives there in one design language: chat, voice,
memory, models, MCP, preferences. The tab bar disappears entirely for signed-in
guests. Owner-only technical panels (provider keys, PC capability switches,
integrations, logs) remain as native tabs.

## 🎨 Four themes, applied to the whole app

Pick a look in **Общие → Тема** or in the deck's **Настройки → Интерфейс** —
either one restyles *both* layers (window, sign-in dialog and deck) at once:

| Theme | Feel |
|---|---|
| **Obsidian Amber** | deep near-black green + amber — confident pro tool (default) |
| **Aurora Glass** | violet/cyan bloom, frosted panels, soft radii |
| **Carbon Minimal** | graphite monochrome, thin type, no glow — fastest |
| **Reactor HUD** | cyan sci-fi console: scanlines, bracket corners, uppercase mono |

Frosted glass in Aurora is **enabled only on capable hardware** — on a weak
laptop the theme keeps its colours but drops the expensive blur.

## 🔧 Fixes

- The sign-in dialog no longer clashes with the deck: both layers now share one
  palette (the shell defaulted to a blue theme while the deck was amber).
- The theme picker used to live on a screen most users never opened; it is now
  in the settings where you would look for it.
- The deck's "Тема" dropdown was decorative — it now actually switches themes.
- Design pass on every surface: layered elevation, hairline borders, restrained
  accent, styled scrollbars and focus rings, fine grain on large dark areas.

**Measured, not assumed:** the design layer was profiled in a real browser —
an early glass-everywhere version dropped the reactor from 51 to 15 fps, so
card blur was replaced with layered opaque surfaces. All four themes now hold
~52 fps with the 3D core running, even under software rendering.

**524 automated tests, all green.**

## 💻 Desktop app
Windows installer and portable build are attached below.

---
🤖 Built with automated tests and CI on every commit.
