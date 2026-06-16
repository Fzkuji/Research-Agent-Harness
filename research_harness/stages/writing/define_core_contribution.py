from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def define_core_contribution(repo_context: str, runtime: Runtime) -> str:
    """Consolidate a paper's contribution into ONE sentence with three pillars.

    A paper sells ONE thing. If the core contribution cannot be stated in a
    single sentence, the framing has not converged yet (Karpathy/Nanda).

    By the end of the Introduction the reader must understand three pillars:
    - The What: 1-3 specific, falsifiable claims.
    - The Why: the evidence that supports those claims.
    - The So What: why the community should care.

    Use the one-sentence contribution test — the sentence must look like one
    of these, not a topic description:
    - "We prove that X converges under assumption Y."
    - "We show that method A improves B by 15% on benchmark C."
    - "We identify failure mode D and propose mechanism E that removes it."
    Reject vague forms like "We study X" / "We perform extensive experiments."

    Ground the claims in the provided repo/results materials — do not invent
    results. If the materials don't support a strong claim, say so and state
    the strongest claim they DO support.

    Output ONLY:
      1. The one-sentence contribution.
      2. Three short bullets: What / Why / So What.
    No preamble, no file-saving talk (the caller persists your output).
    """
    from research_harness.references.writing_principles import WRITING_PRINCIPLES
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"{WRITING_PRINCIPLES}\n\n"
            f"=== Repo / results materials ===\n{repo_context}"
        )},
    ])
