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


_WRITE_RULES = """\
Write one section of an academic paper at the level expected by a top venue
(NeurIPS/ICML/ICLR). Output Markdown (with inline LaTeX math where needed).

Rules:
- Start each subsection with WHY (motivation), then HOW (what you did).
- Every claim needs evidence from experiments or citations.
- Use continuous paragraphs, never bullet lists.
- Introduction: background -> problem -> existing gaps -> our approach ->
  contributions. Only describe advantages, NO technical details (save for Method).
- Method: precise notation; define every symbol.
- Experiments: observation -> reason -> conclusion for each result.
- Related Work: summarize approaches per subsection, end with limitations vs ours.
- Present tense for methods/results; past tense only for specific historical events.
- No AI-flavor words (leverage, delve, tapestry, utilize). Simple, clear vocabulary.

Knowledge isolation:
- Prefer the provided context/materials over parametric memory for every
  factual statement (results, numbers, citations, procedures).
- When a needed fact is NOT in the materials, do NOT fill it from memory.
  Write the sentence with an explicit [MATERIAL GAP: what is missing] marker.

Output ONLY the section content — start directly with the section text, no
explanation, no preamble, no "what would you like" questions, no talk about
saving files (the caller persists your output)."""


@agentic_function(render_range={"depth": 0, "siblings": 0})
def write_section(section: str, context: str, runtime: Runtime) -> str:
    """Write one section of an academic paper.

    Returns the section content. The full authoring rules are sent in the
    prompt (not just this docstring), and the caller persists the result —
    this function does no file I/O, so it works on a pure-API runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"{_WRITE_RULES}\n\n"
            f"=== Section to write ===\n{section}\n\n"
            f"=== Project context / materials ===\n{context}"
        )},
    ])
