from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def plan_ablations(method_description: str, results: str,
                   claims: str, runtime: Runtime) -> str:
    """Systematically design ablation studies that answer the questions reviewers
    will ask. Think like a rigorous ML reviewer planning ablation studies.

    Given the method and results, design ablations that:
    1. Isolate the contribution of each novel component
    2. Answer questions reviewers will definitely ask
    3. Test sensitivity to key hyperparameters
    4. Compare against natural alternative design choices

    For each ablation, specify:
    - name: what to change (e.g., "remove module X", "replace Y with Z")
    - what_it_tests: the specific question this answers
    - expected_if_component_matters: what we predict if the component is important
    - priority: 1 (must-run) to 5 (nice-to-have)

    Also provide:
    - coverage_assessment: what reviewer questions these ablations answer
    - unnecessary_ablations: experiments that seem useful but will not add insight
      (skip these to save compute)
    - suggested_order: run order optimized for maximum early information
    - estimated_compute: total GPU-hours estimate

    Rules:
    - Every ablation must have a clear what_it_tests and expected outcome.
      No "just try it" experiments.
    - Config-only ablations take priority over those needing code changes
      (faster, less error-prone).
    - Component ablations (remove/replace) take priority over hyperparameter sweeps.
    - Do not generate ablations for components identical to the baseline
      (no-op ablations).
    - Record all ablation results including negative results
      (component removal had no effect = important finding).

    Output: Structured ablation plan in markdown table format with coverage
    assessment, unnecessary ablations list, run order, and compute estimate.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Method:\n{method_description}\n\n"
            f"Results:\n{results}\n\n"
            f"Claims:\n{claims}"
        )},
    ])
