from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
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
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": log},
    ])
