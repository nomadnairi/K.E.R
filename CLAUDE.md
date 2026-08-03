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

## Design principle for exe/desktop-control work

**No hardcoded command table.** The user was explicit — this is not "match
the phrase 'open X' in code and run a scripted action," it's the LLM
recognizing intent and invoking a real tool call (agentic, via the existing
tool-calling/Desktop Control plumbing), the same way any other tool use works
in this codebase. Don't regress to a keyword/regex command parser.

Status (02.08.2026): investigated why "KER, open YouTube" didn't work in the
exe. `jarvis/desktop/tools.py`/`controller.py` were never stubs — `OpenUrlSkill`
→ `DesktopController.open_url` → real `webbrowser.open`, security-gated via
`SecurityManager` (already covered by `tests/test_desktop.py`). The actual gap
was the system prompt never told the model to (a) call the tool instead of
just narrating, or (b) only claim success the tool result actually confirms —
fixed in `jarvis/llm/prompts.py` (`PromptBuilder.persona`'s new "Acting in the
real world" section). `allow_desktop_control` is still off by default
(security-by-default, three-state toggle in the Deck's Capabilities screen) —
that's correct behavior, not a bug; the fix makes the assistant honest about
it being off rather than pretending, and act on it correctly once it's on.

Known, low-priority, NOT fixed: the desktop app's native-Qt fallback settings
tabs (`_save_capabilities`/`_save_voice`/`_save_assistant`/`_save_integrations`/
`_save_general` in `jarvis/desktop_app/app.py`) never call
`on_settings_changed(...)`, so toggles made there don't reach a running local
engine without an app restart — only the Deck (QtWebEngine) path does this
correctly, and every shipped build uses the Deck, so this is dead-code-path
risk rather than a live bug. Worth a follow-up pass if the Qt fallback is ever
exercised for real.

## Device relay (03.08.2026) — controlling the customer's PC when the AI runs on the server

Follow-up to the above: the user wants Free/Plus/Pro customers to keep using
**the operator's own server/API** for the AI brain (billing, no user API key
needed), but PC-control actions (open a URL, type, press a key, screenshot)
have to run **on the customer's machine**, not the server. Built a device
relay — `jarvis/desktop/device_registry.py` (server) +
`jarvis/desktop/agent.py` (client, embedded in the exe and standalone via
`python -m jarvis.desktop.agent`) — see that commit's message for the full
design. Second-opinion review (via ChatGPT, at the user's request) confirmed
the core architecture (outbound WSS, permission decision stays on the
controlled machine, no MCP/RDP) and suggested generalizing toward a
"Device Agent" abstraction (multi-platform, capability negotiation, task
queue, event bus, offline queueing). Adopted the two cheap parts —
`(principal, device_id)` keying and a capabilities handshake on connect —
and explicitly rejected the rest for now:

- **No task queue.** The engine's whole tool-calling loop
  (`_ask_llm`/`_run_tools`) is synchronous end-to-end already, same as
  `ConfirmationBroker`'s blocking-with-timeout design; every relayed action
  here completes in a second or two. A queue would mean rearchitecting that
  loop for a problem that doesn't exist yet.
- **No event bus** (device → cloud proactive events like "battery low").
  Real feature, zero relation to making "open YouTube" work — separate work.
- **No offline queueing.** A device that's offline gets a clean "PC isn't
  connected" refusal, not a job that fires whenever it happens to reconnect
  — queueing physical actions for an unpredictable later moment is a UX risk,
  not just complexity.
- **No multi-platform build-out now** — the user already said Raspberry Pi
  is "for later" at the very start of this project; the same reasoning
  applies to Android/Linux agents. The key/capability shape leaves room for
  them without a rewrite when that day comes.

Status: done on both sides — server + `LocalAgent` (private `server` repo) and
the exe wiring in `jarvis/desktop_app/app.py`'s remote mode (public `origin`
repo, `_start_device_agent`/`_stop_device_agent`). Known follow-up: "ask"-mode
confirmation in remote-mode device control has no GUI dialog yet — the agent
is built with `confirmer=None` there, so it refuses honestly instead of
hanging on a half-built dialog. Standalone-agent packaging as an installer is
also still just `python -m jarvis.desktop.agent`, not a shipped exe.

## Screen sharing (03.08.2026) — the AI can look at the screen, on request

Follow-up to the device relay: the user wants something like a video-call
screen share — turn it on, and KER can see what's on screen while you talk
(e.g. "explain this code" while VS Code is open). Chose the practical version
of this instead of literal video streaming: LLM chat APIs take discrete
images in messages, not a live video feed, so "share mode" is a per-message
snapshot, not a frame stream. Confirmed with the user: capture only when they
actually send a message while sharing is on (not a background timer) — the
cheaper, "recommended" option from the two offered.

- **`desktop.share_screen`** (`jarvis/desktop/tools.py`) — a real tool the
  model calls itself (`{"enabled": true/false}`), same "no hardcoded
  commands" philosophy as everything else here: saying "включи демонстрацию
  экрана" works because the LLM recognizes the intent and calls the tool, not
  because of a keyword match. Just flips `session.scratch["share_screen"]`.
- **`desktop.capture_screen`** — internal only (no `parameters`, so never
  offered to the model as a callable tool). `jarvis/core/engine.py`'s new
  `_ask_llm` step, `_attach_screen`, invokes it directly by name once per
  turn when the flag is on, exactly like `_run_tools` already invokes tools —
  same relay-or-local branching as every other desktop skill, so it works
  identically whether the engine is local or server-hosted (relayed to the
  customer's device). Fails open on any problem (no device connected, denied,
  no display) — screen sharing just silently doesn't attach an image that
  turn, never breaks the conversation.
- **`DesktopController.capture_png_b64`** — captures straight to memory
  (base64 PNG), no file write, unlike the existing `screenshot()` tool.
- **Vision wire format**: `LLMProvider.vision_user_message()` (new, default
  = OpenAI content-parts shape, inherited as-is by OpenRouter/local since
  they're all OpenAI-compatible); `AnthropicProvider` overrides it for
  Anthropic's block shape. `LLMClient.provider_for(profile, override)` mirrors
  `complete()`'s own selection precedence so the engine can ask the *actual*
  acting provider for its format before the first completion of the turn
  (same known, accepted limitation as `continuation_messages` already has:
  if the fallback chain hops to a different provider mid-conversation, a
  previously-built message may not match that provider's shape — rare, and
  already true for tool-call continuations, not something this feature needs
  to solve first).
- Persisted conversation history (`Conversation`/`Message`) is untouched —
  still plain text forever; only the one outgoing wire message for a shared
  turn gets swapped for a multimodal version. Screenshots never bloat stored
  history.

Not doing in this pass: a bot-menu/UI toggle button (voice/text "turn on
sharing" already covers the ask); redacting/blurring sensitive screen content
before sending it to a cloud provider (flagged to the user as a real privacy
consideration — screen contents leave the machine to whatever LLM API is
configured — but out of scope for this pass).

## Speed (03.08.2026) — voice replies were silently stuck on the slow default

User reported both voice and text replies taking 10-20s, "обязательно,
очень обязательно" to fix. Root cause for voice specifically: the "voice
prefers a fast model" logic (`JarvisEngine._ask_llm`) only activated if the
operator had already set `LLM_MODEL_FAST` — nobody had, so voice silently ran
on the same model as everything else. Fixed with a per-provider fast-model
fallback table (`DEFAULT_FAST_MODELS` in `jarvis/config/constants.py` —
Anthropic → Haiku, OpenAI → gpt-4o-mini) used when `llm_model_fast` is unset;
an explicit `LLM_MODEL_FAST` still wins. Text replies have the equivalent
lever (`AI_ROUTER_ENABLED` + `LLM_MODEL_FAST`/`LLM_MODEL_STRONG`) but it's an
operator `.env` setting on the VPS, not something fixable from here — told
the user what to set.

## Proactive engine (03.08.2026) — KER speaks up first, "real movie Jarvis"

User wants ambient/background behavior: KER notices things (system load,
screen, smart home, "anything not even on this list") and messages the user
*unprompted*, not just replies. Explicitly separate from and does **not**
include autonomous action-taking ("сам исправляет") — user asked to discuss
that boundary in a later, separate conversation. This feature only ever
sends a message; it never executes a tool unprompted, no change to
`SecurityManager` gating.

Researched first (two Explore passes) rather than assumed: the *only* real
background-initiated push channel anywhere in the codebase is
`jarvis/interfaces/telegram_bot.py`'s `_proactive_worker()` (reminders/
automations/morning-greeting/idle-nudge, gated by the existing
`prefs.list_proactive()` opt-in). `/ws/{session_id}` has no connection
registry (can't push into an open chat socket from outside); desktop app has
working push-to-UI primitives (`_notify()` tray toast, JS `toast()`) but
nothing triggers them from a backend event yet; Android has no push infra at
all. **v1 ships Telegram-only** — the other channels are real, understood
fast-follows, not attempted here.

Built `jarvis/proactive/` (mirrors `jarvis/goals/`'s shape): `Signal`
(a plain fact record — `sensor`/`summary`/`detail`/`severity`, `severity`
is metadata for the prompt only, never branched on in code — that would just
be a hardcoded trigger table under a different name), `ProactiveSensor` ABC
(the one extension point — "anything not on the list" is a new small class,
nothing else changes), `SystemHealthSensor` (psutil CPU/RAM, fires only on
sustained breach across `consecutive_ticks`, not a single noisy sample),
`decision.should_speak()` (one plain LLM call via the *existing*
`PromptBuilder.system_prompt(extra_context=...)`, fast model by the same
precedence voice already uses, a `NOTHING` sentinel instead of parsing an
empty string, zero-signal ticks never reach the LLM at all), and
`ProactiveEngine` (per-user loop: cooldown gate before sensors even run,
`asyncio.gather` + a semaphore bound on concurrent per-tick I/O, wired into
`telegram_bot.py`'s startup as a *second*, separate task next to
`_proactive_worker` — deliberately not merged into it, so reminders/
automations (already working, already tested) are completely untouched).

Deliberately deferred/stubbed for a later pass (from the Plan agent's
review, confirmed by reading the actual code, not assumed):
- **Schedule is not migrated into `jarvis/proactive/`.** Reminders are
  user-authored text with deterministic delivery; routing them through an
  LLM-decides pipeline would let the model paraphrase text the user typed
  themselves, for zero benefit. `_proactive_worker` keeps doing this exactly
  as before.
- **`IntegrationsSensor`/`ScreenSensor` are not built yet** (rollout order:
  system-health first as a fully self-contained, reviewable slice; then
  integrations via an additive `BaseIntegration.snapshot()`; screen last).
  The screen sensor specifically has a real wiring gap: `desktop.
  capture_screen`'s relay only fires when `session.scratch["device_relay"]`
  is set, which today only ever happens on the API/license-account path
  (`_apply_device_relay` in `jarvis/api/app.py`) — `telegram_bot.py` never
  sets it, so a naive proactive screen sensor for Telegram users would
  silently capture *the bot server's own screen* in a multi-tenant
  deployment. Needs a Telegram-user → license-account → `DeviceRegistry`
  principal mapping before it can default on; ship it off by default with
  this documented, not silently wrong.
- `/ws/{session_id}` connection registry, desktop app `_notify()`/toast
  trigger wiring, Android push (FCM, from scratch) — real fast-follows once
  the Telegram-only v1 is proven, not blockers for it.

**Correction, same day**: the user's primary product is the exe, not the
Telegram bot — v1 shipping Telegram-only wasn't communicated clearly enough
up front. Second slice added the exact same `ProactiveEngine` as a delivery
channel inside the desktop app, **local mode only**: `EngineThread.submit()`
runs it on the engine's own loop (same pattern `start_api()` already uses
for uvicorn), a new `ReplyBridge.proactive` Qt signal hops it back to the
GUI thread (same cross-thread pattern every other engine-thread callback in
`app.py` already uses), and `LocalProactivePrefs`
(`jarvis/desktop_app/proactive_prefs.py`) is a tiny duck-typed stand-in for
`UserPreferences` — local mode is one user, not a SQLite table of chat ids.
Off by default (`AppConfig.proactive_enabled`); toggling it starts/stops the
task without a full engine restart. Also fixed a real bug found while
building this: a sent proactive message was never appended to
`session.conversation` (so a reply referencing it had no context), and
`ProactiveEngine` assumed a prefs row's `user_id` IS the engine session id,
which is wrong for Telegram (`session_id_for(uid) == "tg-<uid>"`) — added an
injectable `session_id_for` mapping, defaulting to identity (correct for the
desktop app's single "desktop" session).

Remote mode is still untouched — same reason as before, no push-capable
transport exists for it yet (`/ws/{session_id}` still has no connection
registry). **Repo routing note**: this slice's `jarvis/desktop_app/*` files
went to the public `origin` repo (exe-specific, per the routing rule); the
shared `jarvis/proactive/engine.py` fix + the Telegram `session_id_for` wiring
went to `server`. Cherry-picking the exe commit onto origin's tip conflicted
in one spot (`on_settings_changed`'s `elif` chain, since origin already has
the earlier device-relay feature's own `elif` branch there that `server`'s
branch doesn't) — resolved by keeping both branches side by side; worth
knowing if this happens again on the next exe-only cherry-pick.
