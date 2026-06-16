from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
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
    

    """
    return runtime.exec(content=[
        {"type": "text", "text": idea},
    ])
