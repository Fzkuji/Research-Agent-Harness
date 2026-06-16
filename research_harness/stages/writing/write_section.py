from __future__ import annotations

# Citation discipline draws on academic-research-skills v3.12.0
# (https://github.com/Imbad0202/academic-research-skills),
# (c) Cheng-I Wu, CC BY-NC 4.0. We DEPART from its anti-leakage protocol:
# instead of leaving visible [MATERIAL GAP] / [VERIFY] markers, the section
# is written as a finished paper — verify-and-cite or rephrase-to-not-need,
# never leave scaffolding (see the docstring + CITATION_DISCIPLINE).
from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def write_section(section: str, context: str, runtime: Runtime) -> str:
    """Write one section of a finished, publication-ready academic paper in LaTeX.

    Follows the project's WRITING_PRINCIPLES (Nanda/Farquhar/Gopen&Swan/
    Lipton — narrative What/Why/So-What, 5-sentence abstract, sentence-level
    clarity, concrete word choice); the full text is supplied below.

    Write it as a FINISHED PAPER, not a status report. Hard rules:
    - Write the section as if for camera-ready submission. Just write the
      content. Do NOT insert meta-commentary about what is missing,
      pending, planned, illustrative, or to-be-done. NEVER emit phrases
      like "results are illustrative", "in a full evaluation", "[MATERIAL
      GAP]", "[TODO]", "pending measurement", "future runs will", or any
      LaTeX comment narrating a gap. A reader must see a complete paper,
      not scaffolding.
    - Use the provided materials (measured results, run records, literature
      synthesis) as the basis for what you write. When the materials give
      numbers, state them as the paper's results in past tense. Write the
      Results/Experiments sections as a normal paper reports findings —
      directly, no hedging about completeness.
    - Do NOT fabricate specific quantitative claims or citation keys out of
      thin air. Cite with \\citep{key}/\\citet{key} using keys grounded in
      the provided materials. This is about not inventing data — it is NOT a
      license to annotate the paper with what's absent; simply write the
      parts you can write, fully and confidently.

    Output rules:
    - Output ONLY the LaTeX body for this section (no \\documentclass, no
      preamble, no \\begin{document}; just the \\section{...} content the
      caller will assemble into the paper). Start directly with the LaTeX.
    - Do NOT think out loud or restate the task. Your FIRST characters must
      be the section's actual prose. NEVER begin with planning text such as
      "Looking at this task, I need to...", "Here is the section...", "My job
      is to...", or a numbered outline of what you will write. Such
      meta-commentary leaks into the paper and must never appear.
    - Do NOT wrap the output in markdown code fences (no ```latex / ```).
      Emit raw LaTeX only.
    - Continuous paragraphs, no bullet lists. Present tense for methods,
      past tense for results. No AI-flavor words (leverage, delve, tapestry,
      utilize).

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
