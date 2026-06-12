"""Agentic entry points for the research harness.

Discovered automatically by OpenProgram via the
``AGENTIC_FUNCTIONS`` convention — when this package is symlinked
into ``openprogram/functions/agentics/``, the loader walks for any
``<pkg>/agentics/__init__.py`` exporting an ``AGENTIC_FUNCTIONS``
list and imports it (the ``@agentic_function`` decorators fire as
side effects and self-register).
"""
from __future__ import annotations


def __getattr__(name):
    # PEP 562 lazy export: importing research_agent eagerly here recurses
    # into research_harness.__init__ -> main -> openprogram's registry
    # loader while THIS module is still initializing, so the eager
    # `from ..main import ...` always hit ImportError and exported [].
    if name == "AGENTIC_FUNCTIONS":
        try:
            from research_harness.main import research_agent
        except ImportError:
            # Deps-less machine (installing-harnesses.md rule 2):
            # discovery must never break the whole registry load.
            return []
        return [research_agent]
    raise AttributeError(name)


__all__ = ["AGENTIC_FUNCTIONS"]
