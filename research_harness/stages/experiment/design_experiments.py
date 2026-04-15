from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def design_experiments(idea: str, runtime: Runtime) -> str:
    """Design a complete experiment plan for a research idea.

    You are a meticulous ML researcher designing rigorous experiments.

    The plan must include:
    1. Research Questions (RQ1, RQ2, RQ3...)
    2. Datasets: which ones, why, train/val/test splits
    3. Baselines: recent methods (within 2 years), justify each
    4. Evaluation Metrics: which metrics, why they're appropriate
    5. Ablation Study: which components to ablate
    6. Implementation Details: framework, hardware, hyperparameter ranges
    7. Expected Experiment Types:
       - Overall Performance (all datasets × all baselines)
       - Ablation Study (remove key modules)
       - Parameter Analysis (vary hyperparameters)
       - Efficiency Study (time/space)
       - Case Study / Visualization

    Each experiment should map to a specific research question.
    Be specific about what to measure and how to interpret results.

    Output: Structured markdown experiment plan.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": idea},
    ])
