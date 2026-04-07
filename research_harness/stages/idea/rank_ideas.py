from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def rank_ideas(ideas: str, novelty_results: str, runtime: Runtime) -> str:
    """Rank research ideas by overall promise.

    Consider: novelty, feasibility, potential impact, risk.
    Weight novelty and feasibility highest — a brilliant but infeasible
    idea is worse than a solid, executable one.

    Output JSON:
    {"ranking": [{"rank": 1, "title": "...", "score": 8.5,
                  "reasoning": "why this ranks here"}]}
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Ideas:\n{ideas}\n\n"
            f"Novelty assessments:\n{novelty_results}"
        )},
    ])
