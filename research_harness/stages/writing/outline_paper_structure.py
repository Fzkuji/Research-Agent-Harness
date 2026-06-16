from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def outline_paper_structure(contribution: str, context: str,
                            runtime: Runtime) -> str:
    """Produce a section-by-section outline for the paper, each with its goal.

    Build the outline around the one-sentence contribution and the three
    pillars (What/Why/So What). Standard top-venue structure:

    - Abstract: five-sentence formula (achieved / why hard / how / evidence /
      the number to remember).
    - Introduction (~1-1.5 pages): hook -> background+challenge -> approach
      overview -> 2-4 concrete falsifiable contribution bullets -> results
      preview -> optional roadmap.
    - Related Work: organized by approach, each subsection ending with its
      limitation vs ours (not paper-by-paper).
    - Method: precise notation; enable reimplementation.
    - Experiments: each result maps to a specific claim (observation ->
      reason -> conclusion).
    - Results / Discussion / Limitations (required) / Conclusion.

    Respect reviewer reading order (Title -> Abstract -> Intro -> Figure 1 ->
    rest): put the strongest result early; Figure 1 explains the core method
    or shows the strongest comparison.

    Output ONLY the outline: for each section, its name and 1-3 bullet goals
    (what that section must establish, tied to the contribution). No prose
    drafting yet, no preamble, no file-saving talk.
    """
    from research_harness.references.writing_principles import WRITING_PRINCIPLES
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"{WRITING_PRINCIPLES}\n\n"
            f"=== One-sentence contribution ===\n{contribution}\n\n"
            f"=== Project context / materials ===\n{context}"
        )},
    ])
