"""Small text-processing helpers used across the codebase."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Collapse whitespace and strip surrounding spaces."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def truncate(text: str, max_chars: int = 120, suffix: str = "…") -> str:
    """Truncate ``text`` to ``max_chars`` characters, adding ``suffix``."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)].rstrip() + suffix


#: Word characters in any alphabet. ``\w`` is Unicode-aware in Python 3, so
#: this keeps Cyrillic and every other script; an ASCII-only pattern silently
#: turned Russian text into no tokens at all, which left semantic memory
#: unable to recall anything a Russian-speaking user told it.
_WORD_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)


def tokenize_words(text: str) -> list[str]:
    """Return lowercase word tokens (letters/digits) from ``text``.

    Works in any alphabet, not just Latin.
    """
    return _WORD_RE.findall(text.lower())


def strip_wake_word(text: str, wake_words: tuple[str, ...]) -> str:
    """Remove a leading wake word (e.g. 'jarvis') from an utterance."""
    stripped = text.strip()
    lowered = stripped.lower()
    for word in wake_words:
        if lowered.startswith(word.lower()):
            rest = stripped[len(word):].lstrip(" ,.:!")
            return rest or stripped
    return stripped
