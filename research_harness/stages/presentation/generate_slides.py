from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_slides(paper_content: str, venue: str, talk_type: str,
                    minutes: int, runtime: Runtime) -> str:
    """Generate Beamer presentation slides from a paper.

    Talk types and slide counts:
    - poster-talk (3-5 min): 5-8 slides
    - spotlight (5-8 min): 8-12 slides
    - oral (15-20 min): 15-22 slides
    - invited (30-45 min): 25-40 slides

    Slide structure for oral/spotlight:
    1. Title slide
    2. Problem & Motivation (why should the audience care?)
    3. Key insight / contribution (the "aha" moment)
    4. Method overview (1-2 slides, visual-first)
    5. Key results (most impactful numbers/figures)
    6. Analysis / ablation (1 slide)
    7. Conclusion & future work
    8. Thank you + QR code to paper

    Rules:
    - Tell a STORY, not a summary. Build understanding progressively.
    - One message per slide. If you need two points, use two slides.
    - Figures > text. Minimize bullet points.
    - ~1 slide per minute for oral, ~1.5 for spotlight.
    - Include \\note{} blocks for speaker notes.
    - Use venue-appropriate color scheme.

    Output: Complete Beamer LaTeX source code.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n"
            f"Talk type: {talk_type} ({minutes} minutes)\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])
