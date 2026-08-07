"""
Prompt construction.

Centralises the assistant's persona and any system-prompt scaffolding so the
"voice" of J.A.R.V.I.S. lives in one place rather than being scattered across
the codebase.
"""

from __future__ import annotations

from datetime import datetime


class PromptBuilder:
    """Builds system prompts for the assistant."""

    def __init__(self, assistant_name: str, user_name: str,
                 aliases: list[str] | None = None) -> None:
        self.assistant_name = assistant_name
        self.user_name = user_name
        self.aliases = aliases or []

    def persona(self, name: str | None = None) -> str:
        """The core persona / behaviour contract.

        Args:
            name: Optional per-request assistant name (white-label override).
                Falls back to the configured default.
        """
        assistant_name = name or self.assistant_name
        also = ""
        if self.aliases:
            also = (f"The user may also address you as "
                    f"{', '.join(self.aliases)}; respond to any of these.\n")
        return (
            f"You are {assistant_name}, a highly capable, witty, and "
            f"unfailingly loyal personal AI assistant.\n"
            f"{also}"
            f"You address the user as '{self.user_name}'.\n\n"
            "Principles:\n"
            "- Be concise, precise, and proactive.\n"
            "- Offer the most useful next action, not just an answer.\n"
            "- If you are unsure or lack data, say so plainly — never invent "
            "facts.\n"
            "- Keep a dry, understated wit; never be obsequious.\n\n"
            "Acting in the real world:\n"
            "- When the user asks you to DO something (open a site or app, "
            "type, click, take a screenshot, run a command, draw an image, "
            "search the web, etc.), call the matching tool — don't just "
            "describe what you would do or reply as if it already happened.\n"
            "- Only report that something succeeded if the tool result "
            "actually says so. If a tool is disabled, refused, or fails, say "
            "so plainly and tell the user how to enable it — never invent a "
            "success you didn't get, however small the ask.\n"
        )

    def system_prompt(self, *, extra_context: str | None = None,
                    include_time: bool = True, language: str | None = None,
                    assistant_name: str | None = None) -> str:
        """Assemble the full system prompt.

        Args:
            extra_context: Optional additional context (e.g. retrieved memory,
                available skills) appended to the persona.
            include_time: Whether to inject the current date/time.
            language: Human-readable language the assistant must reply in
                (e.g. "Russian"). When omitted, the model matches the user.
        """
        parts = [self.persona(assistant_name)]
        if include_time:
            now = datetime.now().strftime("%A, %d %B %Y, %H:%M")
            parts.append(f"Current date and time: {now}.")
        if language:
            parts.append(f"Always reply to the user in {language}.")
        if extra_context:
            parts.append(extra_context.strip())
        return "\n\n".join(parts)
