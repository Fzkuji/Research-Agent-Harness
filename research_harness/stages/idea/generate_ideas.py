from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_ideas(topic: str, gaps: str, runtime: Runtime) -> str:
    """Generate research ideas that address identified gaps.

    You are a creative ML researcher brainstorming novel approaches.

    For each idea:
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
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research topic: {topic}\n\n"
            f"Identified gaps:\n{gaps}"
        )},
    ])
