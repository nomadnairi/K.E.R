# KER v1.11.0

Everything reported after the last release, plus two defects found while
building it — one of which had quietly broken memory for every Russian-speaking
user.

## 🐞 Semantic memory did not work in Russian at all

The word tokenizer matched `[a-zA-Z0-9']` only, so Cyrillic text produced **zero
tokens** and therefore an all-zero embedding. Facts were stored and never
recalled — no error, no warning, just an assistant that never remembered
anything you told it in Russian. The tokenizer is Unicode-aware now (Russian,
Uzbek with its apostrophe, anything else), and six tests pin it so it cannot
come back.

## 🔐 Three-state PC access, with confirmation

"Allowed / not allowed" was too blunt. Each capability — reading files, writing
files, running commands, controlling the PC — is now one of three:

| | |
|---|---|
| **Запретить** | refused outright |
| **Спрашивать** | the assistant stops mid-action and asks you, every time |
| **Разрешить** | allowed silently |

In *ask* mode the engine really is blocked: a prompt shows what is about to
happen (the exact command, with secrets redacted), and the action only proceeds
when you say yes. **Silence is a no** — nobody answering means refused, so an
unattended machine cannot be talked into granting itself permissions. Every
outcome, including what you answered, goes to the audit trail.

You can answer with the buttons or, with **Спрашивать голосом** switched on,
have the question spoken and reply "да" / "нет" — anything else is ignored
rather than guessed at.

## 🔑 Every provider has its key field

OpenRouter was missing, so the provider was selectable but unusable. The AI
screen now carries Anthropic, OpenAI, **OpenRouter**, and a **local model**
(base URL + optional key, for Ollama / LM Studio / vLLM / llama.cpp). The model
field hints at the right format for whichever provider you picked, and saving a
key restarts the engine so it works immediately.

## 🌐 Internet is a real screen

The old screen told you to go edit `.env`. Now it lists every search backend
with what it is good for, shows which ones the engine reports as usable, lets
you paste keys for Tavily, Exa, Brave, Perplexity and SerpAPI, pick the default
provider (or leave it on automatic), and **run a real test search** so a key is
proven rather than assumed. DuckDuckGo keeps working with no key at all.

## 🧠 Memory is a real screen

See what the assistant actually remembers: every stored fact with its kind,
conversation and time, real counts, semantic search across them, **Забыть** on
any single memory, and "forget everything". Backed by new list/delete support
in the store and its own API endpoints.

## 🤖 The app has its own icon

A robot mark — drawn by a script in the repo, not a mystery binary, so it can
be re-rendered at any size. Baked into the exe, the installer, the window and
the tray, at every size Windows asks for.

## 🐞 Also fixed

- **The interface never opened its live socket.** After the app handed the deck
  its API address it called `loadState()` but not `connectWS()`, so the window
  showed a single frozen snapshot and could never have received a permission
  question. It now connects, and reconnects when the engine restarts.
- A confirmation button was styled with a CSS variable that does not exist in
  the desktop palette, which made the whole declaration invalid — dark text on
  no background. Colours are derived from the active accent now.
- The first-run greeting pointed at tabs that no longer exist.

**599 automated tests, all green** — 43 new ones covering confirmations,
memory browsing, tokenisation and the new endpoints.

## 💻 Desktop app
The Windows installer is attached below.

---
🤖 Built with automated tests and CI on every commit.
