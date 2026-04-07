from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_section(section: str, context: str, runtime: Runtime) -> str:
    """Write one section of an academic paper in LaTeX.

    You are a senior ML researcher writing for a top venue (NeurIPS/ICML/ICLR).

    Rules:
    - Start each subsection with WHY (motivation), then HOW (what you did).
    - Every claim needs evidence from experiments or citations.
    - Use continuous paragraphs, never bullet lists or \\item.
    - Introduction: background → problem → existing gaps → our approach → contributions.
      Only describe model advantages, NO technical details (save for Method).
    - Method: precise symbols, \\boldsymbol for vectors/matrices, \\mathbb{R} for dims.
    - Experiments: observation → reason (from model design) → conclusion for each result.
    - Related Work: summarize approaches per subsection, end with limitations vs ours.
    - Use \\citep{} for parenthetical, \\citet{} for textual. Never use citations as subjects.
    - Present tense for methods/results, past tense only for specific historical events.
    - No AI-flavor words (leverage, delve, tapestry, utilize). Use simple, clear vocabulary.

    Output ONLY the LaTeX content for the section. No explanation.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Section to write: {section}\n\n"
            f"Project context:\n{context}"
        )},
    ])
