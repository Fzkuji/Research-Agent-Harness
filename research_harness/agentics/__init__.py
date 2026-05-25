"""Agentic entry points for the research harness.

Discovered automatically by OpenProgram via the
``AGENTIC_FUNCTIONS`` convention — when this package is symlinked
into ``openprogram/functions/agentics/``, the loader walks for any
``<pkg>/agentics/__init__.py`` exporting an ``AGENTIC_FUNCTIONS``
list and imports it (the ``@agentic_function`` decorators fire as
side effects and self-register).
"""
from __future__ import annotations

try:
    from ..main import research_agent
    AGENTIC_FUNCTIONS = [research_agent]
except ImportError:
    AGENTIC_FUNCTIONS = []

__all__ = ["AGENTIC_FUNCTIONS"]
