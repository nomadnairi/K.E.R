"""
J.A.R.V.I.S. — Just A Rather Very Intelligent System.

A personal AI assistant framework with a modular, layered architecture:

    interfaces (CLI / API / voice)
        └── JarvisEngine ── pipeline ── skills / LLM
                 ├── events (pub/sub bus)
                 ├── telemetry (metrics)
                 ├── memory
                 └── integrations (planned)

Public entry points:
    JarvisEngine   — the orchestrator you talk to.
    get_settings   — cached, typed configuration.
"""

__version__ = "1.18.0"
__author__ = "nomadnairi"

from jarvis.config.settings import get_settings
from jarvis.core.engine import JarvisEngine

__all__ = ["JarvisEngine", "get_settings", "__version__"]
