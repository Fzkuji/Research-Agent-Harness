from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def refine_research(direction: str, runtime: Runtime) -> str:
    """Refine a vague research direction into a concrete, focused plan.

    Four principles:
    1. Do not lose the original problem. Freeze a Problem Anchor.
    2. The smallest adequate mechanism wins. Minimal intervention.
    3. One paper, one dominant contribution.
    4. Modern leverage (LLM/VLM/RL) is a prior, not a decoration.

    Output a focused proposal:
    - Problem Anchor (immutable)
    - Technical gap identified
    - Proposed method (minimal, elegant)
    - Why this is the sharpest route
    - Minimal validation plan
    - One-sentence thesis

    Output: Structured research plan document.
    """
    return runtime.exec(content=[
        {"type": "text", "text": direction},
    ])
