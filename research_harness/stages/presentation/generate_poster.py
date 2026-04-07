from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_poster(paper_content: str, venue: str,
                    runtime: Runtime) -> str:
    """Generate a conference poster from a paper.

    Poster principles:
    - ONE page, visual-first. Tell the story in 60 seconds.
    - 4 columns for landscape A0, 3 for portrait A0.
    - Figures dominant, text minimal. Bullet points only.
    - Sections: Title/Authors, Motivation, Method (diagram),
      Key Results (1-2 figures), Conclusion, QR code.

    Color scheme: deep saturated colors for primary (visible from distance).
    Text: minimum 24pt body, 32pt section headers, 48pt+ title.

    Output: Complete LaTeX poster source code (tcbposter or baposter).
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])
