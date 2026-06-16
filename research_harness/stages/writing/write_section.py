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


@agentic_function()
def write_section(section: str, context: str, runtime: Runtime) -> str:
    """Write one section of a publication-ready academic paper in LaTeX.

    Follows the project's WRITING_PRINCIPLES (Nanda/Farquhar/Gopen&Swan/
    Lipton — narrative What/Why/So-What, 5-sentence abstract, sentence-level
    clarity, concrete word choice) and CITATION_DISCIPLINE (never invent
    citations; mark unverifiable ones [VERIFY]); the full texts are supplied
    in the prompt below.

    Output rules:
    - Output ONLY the LaTeX body for this section (no \\documentclass, no
      preamble, no \\begin{document}; just the \\section{...} content the
      caller will assemble into the paper). Start directly with the LaTeX.
    - Continuous paragraphs, no bullet lists. Present tense for methods/
      results. No AI-flavor words (leverage, delve, tapestry, utilize).
    - Cite with \\citep{key}/\\citet{key}; never fabricate a key — when a
      citation can't be verified, write \\cite{PLACEHOLDER_...} and a
      ``% [VERIFY] ...`` comment.

    Knowledge isolation:
    - Prefer the provided materials over parametric memory for every factual
      statement (results, numbers, citations, procedures).
    - When a needed fact is NOT in the materials, do NOT fill it from memory.
      Write the sentence with an explicit ``% [MATERIAL GAP: what is missing]``
      LaTeX comment so the gap stays visible.

    No preamble, no "what would you like" questions, no talk about saving
    files (the caller persists your output).
    """
    from research_harness.references.writing_principles import WRITING_PRINCIPLES
    from research_harness.references.citation_discipline import CITATION_DISCIPLINE
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"{WRITING_PRINCIPLES}\n\n"
            f"{CITATION_DISCIPLINE}\n\n"
            f"=== Section to write (LaTeX body only) ===\n{section}\n\n"
            f"=== Project context / materials ===\n{context}"
        )},
    ])
