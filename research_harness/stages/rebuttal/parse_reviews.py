from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def parse_reviews(reviews_text: str, runtime: Runtime) -> str:
    """Parse reviewer comments into structured, actionable issues.

    For each reviewer, extract:
    1. Reviewer ID
    2. Overall score and recommendation
    3. Strengths mentioned
    4. Each specific concern/weakness as a separate item:
       - The exact concern
       - Severity: fatal / major / minor
       - Category: methodology / experiments / writing / novelty / other
       - Whether it requires new experiments, rewriting, or clarification

    Output JSON: {"reviewers": [{"id": "R1", "score": 5,
    "concerns": [{"issue": "...", "severity": "major",
    "category": "experiments", "action": "new experiment"}]}]}
    """
    return runtime.exec(content=[
        {"type": "text", "text": reviews_text},
    ])
