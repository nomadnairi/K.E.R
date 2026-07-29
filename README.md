<div align="center">

# KER

**Your own AI assistant — one you name, run, and actually own.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/Version-1.12.0-orange)](https://github.com/nomadnairi/K.E.R/releases)

**English** · [Русский](README.ru.md) · [O'zbek](README.uz.md)

</div>

---

## What this is

KER is a personal AI assistant you host yourself. You talk to it in Telegram
or in a desktop app, and behind the scenes it's a real engine — it remembers
your conversations, calls tools to get things done, speaks and listens, runs
tasks on a schedule, and can plug into your smart home.

Two things make it different from "just another chatbot wrapper":

- **It's yours.** No name is baked in. Call it KER, call it anything — each
  person can name their own assistant, and it'll answer to that name (and to a
  second nickname too, if you want). You bring your own API key, your own
  server, your own data.
- **It's a whole product, not a script.** A polished Telegram bot with buttons
  instead of commands, a desktop "Command Deck" with a live dashboard,
  accounts and subscription tiers, auto-updates — the pieces you'd actually
  need if you wanted to give this to other people (or sell it).

Everything runs locally. The simple stuff (time, math, diagnostics) works even
without an API key.

> **⚡ Free vs. full version.** What's here on GitHub is the **free core** —
> enough to run your own assistant. The **full version** (all premium features
> and higher limits) is available **only through the Telegram bot**, by
> subscription. Start the bot: [@jar_v1_s](https://t.me/jar_v1_s).

---

## Editions

Pick how much of KER you want. Subscription tiers (Free / Plus / Pro) apply
*inside* any edition — they're separate from the edition you choose.

| Edition | What's included | Status |
|---|---|---|
| 🤖 **KER Bot** | The Telegram assistant | ✅ available |
| 💻 **KER Desktop** | Telegram bot + desktop app (`.exe`) | ✅ available |
| 🏠 **KER Home** | Telegram bot + desktop + Raspberry Pi voice | 🔜 coming soon |

---

## What it can do

**Talk & remember.** Chat by text or voice. It keeps a real memory — it
remembers your conversations across restarts and quietly distils lasting facts
about you so it can bring them up later. Pasted passwords, tokens and card
numbers are stripped out before anything is ever stored.

**Actually do things.** The model doesn't just answer — it can call tools:
search the web, read and write files, run shell commands, control the desktop,
check the weather, talk to your smart home. Dangerous powers are off by default
and switched on one at a time.

**Plug in more tools (MCP).** KER speaks the Model Context Protocol, so any MCP
server's tools show up as native skills the assistant can use. Point it at a
config or add one at runtime from the dashboard.

**Run on its own.** Tell it "every day at 9am give me a summary" or "check my
email every 3 hours" and it schedules the task, does it, and reports back —
then reschedules itself.

**Speak your language.** Full interface and replies in English, Russian and
Uzbek. Send a voice note and it transcribes, answers, and can speak back — in
whatever language you used. Voice can run fully free and offline.

**Bring your own brain.** Works with Anthropic (Claude), OpenAI (GPT),
OpenRouter, or a local model (Ollama, LM Studio, vLLM, llama.cpp) — no cloud
key needed if you go local. It retries and falls back automatically, and a
router can send easy questions to a fast model and hard ones to a strong one.

---

## Make it yours (white-label)

This is the part most assistants don't give you.

- **Name it.** Ships as **KER**, but every user can rename their assistant from
  the bot's settings — the new name shows up in the menu, in the replies, and
  on the desktop dashboard. Operators can set a default name for the whole
  deployment.
- **Extra nicknames.** Set `ASSISTANT_ALIASES` and it'll answer to more than one
  name — handy as a personal wake-word. (Left blank by default so a copy you
  hand to someone else stays clean.)
- **Your key, your server, your data.** Users can even bring their own API key
  (BYOK). Nothing phones home.

```env
ASSISTANT_NAME=KER
ASSISTANT_ALIASES=Jarvis   # optional — answers to both
```

---

## Quick start

**You'll need:** Python 3.10+ and an API key (or a local model).

```bash
git clone https://github.com/nomadnairi/K.E.R.git
cd K.E.R

python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # add ANTHROPIC_API_KEY (or OPENAI_API_KEY),
                                 # or point it at a local model
python -m jarvis
```

Prefer `make`? `make install`, `make run`, `make test`, `make lint`.

---

## Talk to it in Telegram — the full version

The easiest and most complete way to use KER is the **hosted bot**:
**[@jar_v1_s](https://t.me/jar_v1_s)**. Nothing to install or run — it's the
managed product. Button-driven (no commands to memorise), it remembers each
person separately, answers by voice, and has subscription tiers (Free / Plus /
Pro) that unlock the premium features and higher limits.

Settings live in tidy nested menus: language, the assistant's name, your AI
model, memory, voice, integrations and more.

---

## The desktop app — "Command Deck"

`jarvis-desktop` is a real desktop app (PySide6, builds to a Windows `.exe`),
and the interface *is* the app: one window, no second design language. An
animated reactor home screen with live system telemetry, chat with history, the
model catalogue, memory, MCP servers, the log, and settings — all wired to the
real engine over a bundled local API, updating in real time.

Signing in happens in that same design: a **username and password**, or a
**Telegram login code** the bot hands you. Everyone signs in the same way, the
operator included — their account simply unlocks everything.

What you see afterwards follows your subscription. Free talks and remembers;
Plus adds web search, voice, every model and images; Pro adds the powers that
only exist where the engine runs on your own machine — files, shell, desktop
control, MCP servers and local models. Sections your plan doesn't include stay
visible with what would unlock them, rather than quietly disappearing.

The settings in that window are the real thing — language, theme, the
assistant's name, provider and API keys, PC capabilities, voice backends,
integrations, auto-updates — and the app acts on each change at once, restarting
its own engine when the change calls for it. It can check for and install
updates on its own.

The Windows installer is on the
[**Releases**](https://github.com/nomadnairi/K.E.R/releases) page.

---

## Raspberry Pi (coming soon)

An always-listening voice assistant on a Raspberry Pi — say the name from
across the room and it answers, Tony-Stark style. Setup guide and image will
land here.

---

## Open core

This repository is the **open core** — the engine and the desktop client, MIT
licensed. The **full managed experience** (the hosted bot, subscriptions,
accounts and updates) is the product, available through
[@jar_v1_s](https://t.me/jar_v1_s). You're free to run the core yourself; you
pay for the convenience of the hosted service.

---

## Under the hood

Python 3.10+, async throughout. A provider-agnostic LLM client with retry and
fallback, a skill/tool system with a fast deterministic path, SQLite-backed
memory with semantic recall, a pub/sub event bus, a capability-gated security
layer, FastAPI + WebSocket, and an aiogram Telegram bot. Config is typed
(pydantic-settings). Tested with pytest and linted with ruff on every commit.

```
jarvis/
├── core/            engine, pipeline, sessions, rate limiting, diagnostics
├── llm/ · routing/  provider-agnostic LLM client + model-tier router
├── skills/ · mcp/   built-in tools + Model Context Protocol client
├── memory/          persistent history + semantic recall (RAG)
├── voice/ · i18n/   STT/TTS backends + EN/RU/UZ localisation
├── integrations/    weather, Home Assistant, per-user connectors
├── interfaces/      Telegram bot, reminders, automations
├── desktop_app/     PySide6 app + live Command Deck dashboard
├── api/             FastAPI + WebSocket server
├── licensing/ · billing/   accounts, login codes, plans
└── security/        capability gating + audit
```

The bigger picture and component status live in [VISION.md](VISION.md) and
[ROADMAP.md](ROADMAP.md); the design is in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## What's next

Done: the assistant core, memory, the Telegram bot, voice, integrations, the
API, the desktop Command Deck, MCP, task automation, auto-updates, accounts and
tiers, and full white-label naming.

On the way: an always-listening voice assistant on a Raspberry Pi (say the name
from across the room), more integrations (calendar, email), and multi-room
setups.

---

## Contributing & contact

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md), and please run
`make test` and `make lint` first.

- Telegram: [@deathgu11](https://t.me/deathgu11)
- Channel: [@jar_v1_s](https://t.me/jar_v1_s)
- Bugs & ideas: [GitHub Issues](https://github.com/nomadnairi/K.E.R/issues)

Licensed under the [MIT License](LICENSE).
