"""The proactive engine -- KER notices things and speaks up unprompted.

Strictly message-only: this package never executes a tool or action on its
own. See ``jarvis/proactive/engine.py`` for the orchestration and
``jarvis/proactive/sensors/`` for the pluggable trigger sources.
"""

from jarvis.proactive.engine import ProactiveEngine
from jarvis.proactive.models import Signal

__all__ = ["ProactiveEngine", "Signal"]
