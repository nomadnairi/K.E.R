"""
Skill registry and dispatcher.

Holds all registered skills and provides two dispatch paths:

* :meth:`find` / :meth:`dispatch` — the fast, keyword-matched path, and
* :meth:`tool_specs` / :meth:`invoke_tool` — the LLM tool-calling path.

Registration is validated so two skills cannot share a name.
"""

from __future__ import annotations

from jarvis.llm.tools import ToolSpec
from jarvis.skills.base import BaseSkill, SkillResult
from jarvis.utils.exceptions import (
    SkillExecutionError,
    SkillNotFoundError,
    SkillRegistrationError,
)
from jarvis.utils.logger import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """Registers skills and dispatches requests to them."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    # -- registration -------------------------------------------------------

    def register(self, skill: BaseSkill) -> None:
        if skill.name in self._skills:
            raise SkillRegistrationError(
                f"A skill named {skill.name!r} is already registered."
            )
        self._skills[skill.name] = skill
        logger.debug("Registered skill %r (priority=%d)", skill.name, skill.priority)

    def register_many(self, skills: list[BaseSkill]) -> None:
        for skill in skills:
            self.register(skill)

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    # -- fast path ----------------------------------------------------------

    def find(self, text: str) -> BaseSkill | None:
        """Return the highest-priority skill that can handle ``text``."""
        candidates = sorted(
            self._skills.values(), key=lambda s: s.priority, reverse=True
        )
        for skill in candidates:
            try:
                if skill.can_handle(text):
                    return skill
            except Exception:  # noqa: BLE001 - a broken matcher must not crash routing
                logger.exception("Skill %r raised in can_handle()", skill.name)
        return None

    async def dispatch(self, text: str, context: dict | None = None) -> SkillResult:
        """Route ``text`` to a matching skill via the fast path, if any."""
        skill = self.find(text)
        if skill is None:
            return SkillResult.not_handled()
        try:
            return await skill.handle(text, context)
        except Exception as exc:  # noqa: BLE001
            raise SkillExecutionError(
                f"Skill {skill.name!r} failed: {exc}",
                details={"skill": skill.name},
            ) from exc

    # -- tool path ----------------------------------------------------------

    def tool_specs(self) -> list[ToolSpec]:
        """Return tool specs for every skill exposed to the LLM."""
        specs = [s.as_tool_spec() for s in self._skills.values()]
        return [s for s in specs if s is not None]

    async def invoke_tool(self, name: str, arguments: dict,
                        context: dict | None = None) -> SkillResult:
        """Execute the tool named ``name`` with ``arguments``.

        ``context`` is the caller's session scratch dict — the same object
        already passed to the fast path's :meth:`BaseSkill.handle`. Every
        built-in skill's ``execute`` already ends in a ``**kwargs`` catch-all,
        so passing it costs nothing for skills that don't care about it.
        """
        skill = self._skills.get(name)
        if skill is None:
            raise SkillNotFoundError(f"No skill/tool named {name!r}.")
        try:
            return await skill.execute(**arguments, context=context)
        except SkillExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SkillExecutionError(
                f"Tool {name!r} failed: {exc}",
                details={"skill": name, "arguments": arguments},
            ) from exc

    # -- introspection ------------------------------------------------------

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def all(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def names(self) -> list[str]:
        return list(self._skills.keys())

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._skills)
