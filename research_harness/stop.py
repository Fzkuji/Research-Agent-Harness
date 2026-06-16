"""Process-level graceful-stop flag, shared across the run.

The autonomous loop's stop signal (CLI Ctrl-C, webui/TUI stop button) only
broke the OUTER stage/step loop in research_agent. Long-running orchestrators
(`run_experiments`'s step loop, `review_loop`'s round loop) ran their own
inner loops that never saw the flag, so a stop landing mid-orchestrator was a
hard interrupt instead of a graceful "finish this unit, then stop".

This module is the one place both the outer loop and any inner loop check.
research_agent installs a stop_event here; orchestrators call
``stop_requested()`` at the top of each inner iteration and break gracefully
(persist what they have, return) when it's set.

Deliberately tiny and dependency-free: a module-level holder for an object
with ``is_set()`` (a threading.Event or anything compatible). One process,
one run — a module global is the right scope (a ContextVar would not cross the
thread boundary the runtime uses for async).
"""
from __future__ import annotations

import threading

_stop_event: "threading.Event | None" = None
_lock = threading.Lock()


def install_stop_event(event) -> None:
    """Register the run's stop event (anything with ``is_set()``). None clears."""
    global _stop_event
    with _lock:
        _stop_event = event


def stop_requested() -> bool:
    """True once a graceful stop has been requested for this run."""
    ev = _stop_event
    return ev is not None and ev.is_set()


def clear() -> None:
    """Drop the registered event (call when a run ends, so the next run starts clean)."""
    install_stop_event(None)
