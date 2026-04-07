from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def run_experiment(plan: str, step: str, runtime: Runtime) -> str:
    """Execute one step of the experiment plan.

    You have full freedom to write code, run commands, install packages,
    and manage files. Do whatever is needed to execute this step.

    After execution, report:
    - What you did
    - Results obtained (exact numbers)
    - Any issues encountered
    - What to do next

    Output: Execution report with results.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Experiment plan:\n{plan}\n\n"
            f"Current step:\n{step}"
        )},
    ])
