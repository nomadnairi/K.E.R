"""
What a subscription actually unlocks.

A tier is not a branch in the code — it is a **set of capabilities**. Adding
"Pro Ultimate" later should mean one entry in the table below, not a hunt for
``if plan == "pro"`` across the app.

## What is enforced, and where

Be honest about this, because the two halves are not the same:

* **Server-enforced.** Anything that spends the operator's resources — the
  daily and monthly message allowance on the operator's API key, image
  generation, model choice, hosted voice. The server owns these, so refusing
  them is real.
* **Interface-only.** Anything that runs on the user's own machine: files, the
  shell, desktop control, MCP servers, a local model. The engine executes those
  locally, the server never sees the call, and the core is open source — so
  hiding them is *packaging*, not security. They are bundled with the higher
  tiers because that is the product story, and they are gated on the user's own
  machine by their own consent (see :mod:`jarvis.security`).

The commercial lever is not the microphone; it is the brain. A local assistant
without a model is an empty box, and the model access is what a subscription
pays for.
"""

from __future__ import annotations

from jarvis.billing.plans import FREE, PLUS, PRO

# -- capabilities -----------------------------------------------------------

#: Text conversation. Everyone has it; it is the product.
CHAT = "chat"
#: Persistent memory: remembering facts and recalling them later.
MEMORY = "memory"
#: Web search as a tool.
SEARCH = "search"
#: Speech in and out.
VOICE = "voice"
#: The model catalogue and the right to pick any model.
MODELS = "models"
#: Image generation.
IMAGES = "images"
#: Weather, smart home, Telegram and friends.
INTEGRATIONS = "integrations"
#: Scheduled tasks and reminders that run on their own.
AUTOMATION = "automation"
#: Files, shell and desktop control on the user's own machine. Local.
PC_ACCESS = "pc_access"
#: Connecting external MCP servers. Local.
MCP = "mcp"
#: Running a local model (Ollama, LM Studio, vLLM, llama.cpp). Local.
LOCAL_AI = "local_ai"
#: The engine's log and diagnostics. Local.
LOGS = "logs"
#: One-tap update to a new release.
AUTO_UPDATE = "auto_update"
#: Programmatic access to the hosted API.
API_ACCESS = "api_access"

#: Capabilities the server can genuinely refuse, because it performs them.
SERVER_ENFORCED = frozenset({MODELS, IMAGES, API_ACCESS, AUTO_UPDATE})

#: Capabilities that run on the user's machine — bundled, not policed.
LOCAL_ONLY = frozenset({PC_ACCESS, MCP, LOCAL_AI, LOGS})

# -- who gets what ----------------------------------------------------------

_FREE = frozenset({CHAT, MEMORY, INTEGRATIONS})
_PLUS = _FREE | {SEARCH, VOICE, MODELS, IMAGES, AUTOMATION, AUTO_UPDATE,
                 API_ACCESS}
_PRO = _PLUS | LOCAL_ONLY

FEATURES_BY_TIER: dict[str, frozenset[str]] = {
    FREE: _FREE,
    PLUS: _PLUS,
    PRO: _PRO,
}

#: Everything there is — what the operator's own account gets.
ALL_FEATURES: frozenset[str] = _PRO

#: Human labels, so one place decides what a capability is called.
LABELS = {
    CHAT: "Чат с ассистентом",
    MEMORY: "Память",
    SEARCH: "Поиск в интернете",
    VOICE: "Голос",
    MODELS: "Все модели",
    IMAGES: "Генерация изображений",
    INTEGRATIONS: "Интеграции",
    AUTOMATION: "Автоматизации",
    PC_ACCESS: "Доступ к компьютеру",
    MCP: "MCP-серверы",
    LOCAL_AI: "Локальные модели",
    LOGS: "Журнал и диагностика",
    AUTO_UPDATE: "Автообновление",
    API_ACCESS: "Доступ к API",
}

#: Order used when listing capabilities to a person.
ORDER = (CHAT, MEMORY, SEARCH, VOICE, MODELS, IMAGES, INTEGRATIONS,
         AUTOMATION, PC_ACCESS, MCP, LOCAL_AI, LOGS, AUTO_UPDATE, API_ACCESS)


def features_for(tier: str, *, owner: bool = False) -> frozenset[str]:
    """Capabilities unlocked by ``tier``; the operator's account gets all."""
    if owner:
        return ALL_FEATURES
    return FEATURES_BY_TIER.get(tier, _FREE)


def tier_that_unlocks(feature: str) -> str | None:
    """The cheapest tier including ``feature`` — for "available in …" copy."""
    for tier in (FREE, PLUS, PRO):
        if feature in FEATURES_BY_TIER[tier]:
            return tier
    return None


def describe(tier: str) -> list[dict]:
    """Every capability with whether ``tier`` has it — for a comparison table."""
    granted = FEATURES_BY_TIER.get(tier, _FREE)
    return [
        {
            "name": name,
            "label": LABELS.get(name, name),
            "included": name in granted,
            "local": name in LOCAL_ONLY,
        }
        for name in ORDER
    ]
