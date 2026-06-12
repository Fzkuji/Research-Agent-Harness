from __future__ import annotations

# The "Knowledge isolation" docstring block is adapted from
# academic-research-skills v3.12.0
# (https://github.com/Imbad0202/academic-research-skills),
# (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: ARS's anti-leakage protocol (academic-paper/references/
# anti_leakage_protocol.md) is condensed into prompt rules with an
# inline [MATERIAL GAP: ...] marker contract.
from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def write_section(section: str, context: str, runtime: Runtime) -> str:
    """Write one section of an academic paper in LaTeX.

    Write at the level expected by a top venue (NeurIPS/ICML/ICLR).

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

    Knowledge isolation:
    - Prefer the provided context/materials over your parametric memory for
      every factual statement (results, numbers, citations, procedures).
    - When a needed fact is NOT in the materials, do NOT fill it from memory.
      Write the sentence with an explicit [MATERIAL GAP: what is missing]
      marker so the gap stays visible downstream.

    Output ONLY the LaTeX content for the section. No explanation.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Section to write: {section}\n\n"
            f"Project context:\n{context}"
        )},
    ])
