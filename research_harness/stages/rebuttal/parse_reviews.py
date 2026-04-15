from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def parse_reviews(reviews_text: str, runtime: Runtime) -> str:
    """Validate and normalize reviewer text into structured, actionable issues.

    This is Phase 1-2 of the rebuttal pipeline. Parse raw reviewer comments and
    atomize each concern into a structured issue card.

    For each reviewer, extract and normalize:
    1. Reviewer ID, overall score, recommendation, and stance (positive/swing/negative)
    2. Strengths mentioned (preserve verbatim)
    3. Each specific concern as a separate atomic issue with:
       - issue_id: e.g., R1-C1, R1-C2
       - raw_anchor: short verbatim quote from the review
       - issue_type: one of assumptions / theorem_rigor / novelty / empirical_support /
         baseline_comparison / complexity / practical_significance / clarity /
         reproducibility / other
       - severity: critical / major / minor
       - reviewer_stance: positive / swing / negative / unknown
       - response_mode: direct_clarification / grounded_evidence / nearest_work_delta /
         assumption_hierarchy / narrow_concession / future_work_boundary
       - status: open / answered / deferred / needs_user_input
       - action_required: new_experiment / rewrite / clarification / acknowledge

    Safety rules:
    - Preserve all reviewer text verbatim in raw_anchor fields
    - Do NOT merge distinct concerns into one issue (atomize fully)
    - If a reviewer raises the same concern as another, note the overlap but keep separate entries
    - If venue rules or limits are missing, flag as needs_user_input

    Output JSON:
    {{"reviewers": [{{"id": "R1", "score": 5, "stance": "swing",
      "strengths": ["..."],
      "concerns": [{{"issue_id": "R1-C1", "raw_anchor": "...",
        "issue_type": "empirical_support", "severity": "major",
        "response_mode": "grounded_evidence", "status": "open",
        "action": "new experiment"}}]}}]}}
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": reviews_text},
    ])
