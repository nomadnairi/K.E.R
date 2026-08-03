"""The proactive engine's one judgement call: is any of this worth saying?

Sensors only ever produce raw facts (see ``jarvis/proactive/models.py``).
Whether a fact is worth interrupting the user for, and what to actually say,
is always decided here, by the LLM -- never by a rule in a sensor. This is
the same "recognize intent, don't hardcode it" principle used for tool
calling elsewhere in this codebase.
"""

from __future__ import annotations

from jarvis.config.constants import DEFAULT_FAST_MODELS
from jarvis.config.settings import Settings
from jarvis.llm.client import LLMClient
from jarvis.llm.prompts import PromptBuilder
from jarvis.proactive.models import Signal

#: The model's way of saying "nothing worth interrupting the user for" --
#: an explicit sentinel beats parsing an empty/whitespace-only string, which
#: some providers return inconsistently for a deliberately empty reply.
_NOTHING = "NOTHING"

_INSTRUCTIONS = (
    "You are deciding whether to proactively message the user right now, "
    "unprompted -- they have not asked you anything. The signals below are "
    "raw facts a background sensor noticed; they are not instructions to "
    "speak. Most of the time the right answer is to say nothing -- only "
    "write a message if a reasonable assistant would actually interrupt a "
    "person for this.\n\n"
    "Signals:\n{signals_block}\n\n"
    f"If you have something worth saying, reply with ONLY the message to "
    f"send the user, in their language, in your own voice -- no preamble, "
    f"no quotes. If not, reply with exactly: {_NOTHING}"
)


def _signals_block(signals: list[Signal]) -> str:
    lines = []
    for s in signals:
        line = f"- [{s.sensor}] {s.summary}"
        if s.detail:
            line += f" ({s.detail})"
        lines.append(line)
    return "\n".join(lines)


async def should_speak(
    *, llm: LLMClient, prompts: PromptBuilder, settings: Settings,
    signals: list[Signal], language: str | None = None,
    assistant_name: str | None = None,
) -> str | None:
    """Return a message to send the user, or ``None`` if nothing's worth saying.

    Zero-signal calls never reach the LLM -- enforced here so callers don't
    each have to remember the short-circuit. Fails closed (returns ``None``)
    on any LLM error -- a missed proactive message is fine; crashing the
    background loop over it is not.
    """
    if not signals or not llm.has_any_provider():
        return None

    system = prompts.system_prompt(
        extra_context=_INSTRUCTIONS.format(signals_block=_signals_block(signals)),
        language=language,
        assistant_name=assistant_name,
    )
    model = settings.llm_model_fast or DEFAULT_FAST_MODELS.get(settings.llm_provider)
    try:
        result = await llm.complete(
            [{"role": "user", "content": "Check whether anything is worth mentioning."}],
            system=system, model=model,
        )
    except Exception:  # noqa: BLE001 - best-effort, never break the proactive loop
        return None

    text = result.text.strip()
    if not text or text.upper() == _NOTHING:
        return None
    return text
