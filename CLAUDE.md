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
