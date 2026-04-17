from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def identify_gaps(survey: str, runtime: Runtime) -> str:
    """Identify research gaps from a literature survey.

    Analyze the survey and identify:
    1. What problems remain unsolved or underexplored?
    2. What assumptions in existing work are questionable?
    3. Where do methods fail or underperform?
    4. What combinations of approaches haven't been tried?

    Be specific: don't say "more research needed", say exactly what's missing.

    Output: Numbered list of specific, actionable research gaps.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": survey},
    ])
