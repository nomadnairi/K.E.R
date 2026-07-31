"""
Split a document into overlapping passages for retrieval.

Whole documents are too big to embed or to hand a model as context, so text is
cut into passages small enough to embed meaningfully and to quote back. The
split follows the text's own shape — it breaks on blank lines (paragraphs)
first, and only falls back to a hard character cut for a paragraph that is
itself larger than the target. Consecutive passages overlap a little so a
sentence spanning a boundary is not lost to whichever half a query matches.

Deliberately dependency-free and deterministic, so the same document always
chunks the same way and the whole thing is unit-testable.
"""

from __future__ import annotations

import re

_PARA_RE = re.compile(r"\n\s*\n")


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    """Cut an over-long block into ``size`` windows that overlap by ``overlap``."""
    out: list[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        piece = text[start:start + size].strip()
        if piece:
            out.append(piece)
        if start + size >= len(text):
            break
    return out


def chunk_text(text: str, *, size: int = 800, overlap: int = 150) -> list[str]:
    """Split ``text`` into passages of about ``size`` characters.

    Paragraphs are packed together up to ``size``; a paragraph larger than
    ``size`` is hard-split. Each passage after the first repeats the tail of the
    previous one (``overlap`` characters) so a boundary-spanning sentence stays
    findable from either side.
    """
    text = (text or "").strip()
    if not text:
        return []
    if overlap >= size:
        overlap = size // 4

    paragraphs = [p.strip() for p in _PARA_RE.split(text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_hard_split(para, size, overlap))
            continue
        if not buf:
            buf = para
        elif len(buf) + 2 + len(para) <= size:
            buf += "\n\n" + para
        else:
            chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)

    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    # Prepend the tail of each previous chunk to the next, so the seam overlaps.
    stitched = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        tail = prev[-overlap:]
        # Start the overlap on a word boundary so it reads cleanly.
        cut = tail.find(" ")
        if 0 < cut < len(tail) - 1:
            tail = tail[cut + 1:]
        stitched.append((tail + "\n" + cur).strip())
    return stitched
