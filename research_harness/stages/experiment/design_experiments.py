from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"callers": 0})
def design_experiments(idea: str, runtime: Runtime) -> str:
    """Design a rigorous, complete experiment plan for the given idea.

    The plan MUST include, as markdown sections:
    1. Research Questions (RQ1, RQ2, RQ3...)
    2. Datasets / task suite: which ones, why, train/val/test (or task) splits
    3. Baselines: recent methods (within ~2 years), justify each
    4. Evaluation Metrics: which metrics, why they're appropriate
    5. Ablation Study: which components to ablate
    6. Implementation Details: framework, hardware, hyperparameter ranges
    7. Expected Experiment Types:
       - Overall Performance (all datasets x all baselines)
       - Ablation Study (remove key modules)
       - Parameter Analysis (vary hyperparameters)
       - Efficiency Study (time/space)
       - Case Study / Visualization

    Each experiment should map to a specific research question. Be specific
    about what to measure and how to interpret results.

    Output ONLY the structured markdown experiment plan — start directly with
    the first heading, no preamble, no "what would you like" questions, no
    file-system or saving talk (the caller persists your output).
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Research idea / context:\n{idea}"},
    ])
