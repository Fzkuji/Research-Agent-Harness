from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def check_novelty(idea: str, runtime: Runtime) -> str:
    """Check if a research idea is novel.

    Search your knowledge for existing work that:
    - Solves the same problem with the same approach
    - Uses a very similar method on the same task
    - Has already been published at a top venue

    Be honest: if the idea is incremental, say so.
    If truly novel, explain what makes it different from closest work.

    Output JSON:
    {"novel": true/false, "confidence": 0.0-1.0,
     "closest_work": "description of most similar existing work",
     "differentiation": "what makes this idea different"}
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": idea},
    ])
