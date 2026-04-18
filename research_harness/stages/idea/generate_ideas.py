from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_ideas(topic: str, gaps: str, runtime: Runtime) -> str:
    """Generate research ideas that address identified gaps.

    Brainstorm novel approaches. For each idea:
    1. Title: concise, descriptive name
    2. Hypothesis: what you believe and why
    3. Approach: high-level method (2-3 sentences)
    4. Expected outcome: what success looks like
    5. Feasibility: resources/time estimate (low/medium/high effort)
    6. Risk: what could go wrong

    Generate 3-5 diverse ideas ranging from incremental to ambitious.
    Each idea should directly address at least one identified gap.
    Prefer ideas that are testable with existing datasets/benchmarks.

    Output: Structured markdown with numbered ideas.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research topic: {topic}\n\n"
            f"Identified gaps:\n{gaps}"
        )},
    ])
