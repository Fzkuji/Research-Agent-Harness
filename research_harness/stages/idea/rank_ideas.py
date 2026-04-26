from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def rank_ideas(ideas: str, novelty_results: str, runtime: Runtime) -> str:
    """Rank research ideas by overall promise.

    Consider: novelty, feasibility, potential impact, risk.
    Weight novelty and feasibility highest — a brilliant but infeasible
    idea is worse than a solid, executable one.

    Output JSON:
    {"ranking": [{"rank": 1, "title": "...", "score": 8.5,
                  "reasoning": "why this ranks here"}]}
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Ideas:\n{ideas}\n\n"
            f"Novelty assessments:\n{novelty_results}"
        )},
    ])
