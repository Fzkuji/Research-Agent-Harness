from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def review_paper(paper_content: str, venue: str, runtime: Runtime) -> str:
    """You are a rigorous, precise senior reviewer for top CS conferences.
    Evaluate the paper objectively: identify weaknesses AND acknowledge strengths.

    Review dimensions:
    - Community contribution: does this advance the field substantively?
    - Rigor: are claims supported by experiments? Fair baselines? Ablations?
    - Consistency: do intro claims match experimental validation?

    Distinguish fatal flaws from fixable issues — they carry different weight.
    Be specific: not "experiments insufficient" but "missing comparison with
    [specific method] on [specific dataset]".

    Score faithfully: if the paper is solid, give it a high score.
    Skip pleasantries, cut to core judgments.

    After your review, append a JSON block:
    ```json
    {"score": <1-10>, "passed": <true if score>=7>,
     "weaknesses": ["specific issues"],
     "strengths": ["specific strengths"],
     "verdict": "one-line summary"}
    ```
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Target venue: {venue}\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])
