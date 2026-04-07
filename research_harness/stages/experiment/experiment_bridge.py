from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def experiment_bridge(plan: str, runtime: Runtime) -> str:
    """Bridge from experiment plan to running code.

    Read the experiment plan, then:
    1. Implement experiment code (model, training loop, evaluation)
    2. Set up data loading and preprocessing
    3. Run a sanity check (smallest config) first to catch setup bugs
    4. If sanity passes, launch the full experiment suite
    5. Collect initial results

    You have full freedom to write code, install packages, run commands.
    Start with the simplest experiment to validate the setup before scaling.

    Report: what was implemented, sanity check results, what's running.
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Experiment plan to implement:\n{plan}"},
    ])
