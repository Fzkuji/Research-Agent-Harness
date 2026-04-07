from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def comprehensive_lit_review(topic: str, subtopics: str,
                             runtime: Runtime) -> str:
    """Write a comprehensive, publication-ready related work section.

    Deeper than survey_topic — this produces a full Related Work section
    suitable for direct inclusion in a paper.

    Structure per subsection (choose progression or parallel style):

    Progression style:
    - Start with foundational concept, list existing works, end with limitations.

    Parallel style:
    - Overview sentence → subtopic 1 works → subtopic 2 works → our novelty.

    Rules:
    - End each subsection discussing limitations vs our method.
    - Use \\citep{} for parenthetical, \\citet{} for textual.
    - Never use citations as sentence subjects.
    - Cite published versions over arXiv when available.
    - Include recent work (within 2 years) for baselines.

    Output: LaTeX related work section with proper citations.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Topic: {topic}\n\n"
            f"Subtopics to cover:\n{subtopics}"
        )},
    ])
