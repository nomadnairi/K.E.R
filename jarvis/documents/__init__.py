"""Document Intelligence: ingest documents and answer questions over them."""

from jarvis.documents.chunking import chunk_text
from jarvis.documents.service import (
    Document,
    DocumentIntelligence,
    Passage,
)

__all__ = ["DocumentIntelligence", "Document", "Passage", "chunk_text"]
