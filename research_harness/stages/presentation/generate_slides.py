from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_slides(paper_content: str, venue: str, talk_type: str,
                    minutes: int, runtime: Runtime) -> str:
    """Generate conference presentation slides (Beamer LaTeX) from a compiled paper.

    This skill takes a compiled paper and generates a presentation slide deck for
    conference oral talks, spotlight presentations, or poster lightning talks.
    Unlike posters (single page, visual-first), slides tell a temporal story:
    each slide builds on the previous one, with progressive revelation of the
    research narrative.

    Talk types and slide counts:
    - poster-talk (3-5 min): 5-8 slides — Problem + 1 method + 1 result + conclusion
    - spotlight (5-8 min): 8-12 slides — Problem + 2 method + 2 results + conclusion
    - oral (15-20 min): 15-22 slides — Full story with motivation, method detail,
      experiments, analysis
    - invited (30-45 min): 25-40 slides — Comprehensive: background, related work,
      deep method, extensive results, discussion

    Oral slide template (15-22 slides):
    1. Title slide
    2. Outline
    3-4. Motivation & Problem (from Introduction)
    5. Key Insight (contribution)
    6-9. Method (with hero figure)
    10-14. Results (figure per slide)
    15-16. Analysis / Ablations
    17. Limitations
    18. Conclusion / Takeaway
    19. Thank You + QR code

    Presentation rules (enforced strictly):
    - One message per slide: if a slide has two ideas, split it
    - Max 6 lines per slide: more = wall of text
    - Max 8 words per line: audience reads, not listens, if text is long
    - Sentence fragments, not sentences: "Improves F1 by 3.2%%" not
      "Our method improves the F1 score by 3.2 percentage points"
    - Figure slides: figure >= 60%% area. The figure IS the content;
      bullets are annotations
    - Bold key numbers: "Achieves **94.3%%** accuracy"
    - Progressive disclosure: use \\\\pause or \\\\onslide for complex slides
    - No Related Work slide (unless invited talk 30+ min)
    - Tell a STORY, not a summary. Build understanding progressively.
    - ~1 slide per minute for oral, ~1.5 slides per minute for spotlight
    - Include \\\\note{{}} blocks for speaker notes (2-3 sentences of what to say)

    Venue color schemes:
    - NeurIPS: primary #8B5CF6, accent #2563EB
    - ICML: primary #DC2626, accent #1D4ED8
    - ICLR: primary #059669, accent #0284C7
    - CVPR: primary #2563EB, accent #7C3AED
    - GENERIC: primary #334155, accent #2563EB

    Output: Complete Beamer LaTeX source code with speaker notes.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n"
            f"Talk type: {talk_type} ({minutes} minutes)\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])
