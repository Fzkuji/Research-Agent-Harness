from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def check_training(log: str, runtime: Runtime) -> str:
    """Check training logs for issues.

    Analyze the training log and report:
    - Is training progressing normally? (loss decreasing, metrics improving)
    - Any signs of overfitting? (train/val divergence)
    - Any NaN/Inf values?
    - Estimated time to completion?
    - Recommendation: continue / stop early / adjust hyperparameters?

    Output JSON:
    {"status": "healthy/warning/critical",
     "issues": ["list of issues"],
     "recommendation": "what to do next"}
    

    """
    return runtime.exec(content=[
        {"type": "text", "text": log},
    ])
