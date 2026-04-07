from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


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
    """
    return runtime.exec(content=[
        {"type": "text", "text": survey},
    ])
