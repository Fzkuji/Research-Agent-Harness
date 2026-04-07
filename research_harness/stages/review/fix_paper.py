from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def fix_paper(paper_content: str, review_feedback: str,
              round_num: int, runtime: Runtime) -> str:
    """Fix the paper based on reviewer feedback.

    Address EVERY weakness mentioned. Do NOT weaken existing strengths.
    Rewrite actual paragraphs — don't just describe what should change.
    Maintain LaTeX formatting.

    Output the COMPLETE fixed paper content.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Round {round_num}\n\n"
            f"Reviewer feedback:\n{review_feedback}\n\n"
            f"Current paper:\n{paper_content}"
        )},
    ])
