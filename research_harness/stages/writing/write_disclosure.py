from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def write_disclosure(paper_path: str, venue: str = "",
                     runtime: Runtime = None) -> str:
    """Draft the venue-specific AI-usage disclosure statement for a paper.

    # Role
    You prepare the AI-assistance disclosure that accompanies a paper
    submission. Transparency is the goal: state plainly what AI tools were
    used for, never minimize or obfuscate.

    # Task
    Read the paper at `paper_path` (and any project notes beside it that
    describe how it was produced). Draft a disclosure statement covering:
    1. Which parts of the work involved AI assistance (literature search,
       drafting, editing/polish, code, figures, review preparation).
    2. The nature of that assistance (generation vs editing vs checking).
    3. What the human authors verified and take responsibility for.

    # Constraints
    - Match the venue's actual policy language when `venue` is given
      (e.g. ACL/ARR "AI assistance" checklist style; NeurIPS/ICML LLM
      policy paragraphs; Nature-style methods statement). Unknown venue →
      a concise generic statement usable anywhere.
    - 80-180 words, first person plural, no marketing tone.
    - State facts only — if how something was produced is not evident
      from the materials, write [TO CONFIRM: ...] rather than guessing.

    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Paper path: {paper_path}\n"
            f"Target venue: {venue or '(not specified — generic statement)'}"
        )},
    ])
