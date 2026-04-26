from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, render_criteria_text,
)


@agentic_function(render_range={"depth": 0, "siblings": 0})
def lookup_venue_criteria(venue: str, runtime: Runtime) -> str:
    """Return the venue's exact review scoring criteria.

    No longer calls the LLM — reads directly from
    `references.venue_scoring`. This eliminates prior nondeterminism
    (LLM gave different scales each time) and ensures every downstream
    stage sees the same spec.

    To add a new venue or update an existing one, edit
    research_harness/references/venue_scoring.py.

    Args:
        venue:   Venue name (case-insensitive). Aliases handled
                 (NeurIPS=NIPS, EMNLP/NAACL/EACL → ARR, etc.).
        runtime: Unused (kept for compat with the agentic_function
                 framework that auto-injects runtime).
    """
    spec = get_venue_spec(venue)
    return render_criteria_text(spec)
