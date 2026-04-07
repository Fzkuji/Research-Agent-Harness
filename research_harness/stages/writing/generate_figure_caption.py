from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_figure_caption(description: str, runtime: Runtime) -> str:
    """Generate an English figure caption for a top-tier conference paper.

    Title Case for noun phrases (no period). Sentence case for sentences (with period).
    Minimal style: never start with "The figure shows..."
    Use "show", "compare", "present" — avoid "showcase", "depict".
    Do NOT include "Figure X:" prefix — just the caption text.

    Output: English caption text only.
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])
