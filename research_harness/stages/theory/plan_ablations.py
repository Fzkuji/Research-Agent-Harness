from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def plan_ablations(method_description: str, results: str,
                   claims: str, runtime: Runtime) -> str:
    """Design ablation studies from a reviewer's perspective.

    For each ablation:
    1. Name: what to change (remove module X, replace Y with Z)
    2. What it tests: the specific question this answers
    3. Expected outcome if component matters
    4. Priority: 1 (must-run) to 5 (nice-to-have)

    Also provide:
    - Coverage: what reviewer questions these ablations answer
    - Unnecessary ablations: experiments that seem useful but won't add insight
    - Suggested run order: maximize early information
    - Compute estimate: total GPU-hours

    Output: Structured ablation plan.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Method:\n{method_description}\n\n"
            f"Results:\n{results}\n\n"
            f"Claims:\n{claims}"
        )},
    ])
