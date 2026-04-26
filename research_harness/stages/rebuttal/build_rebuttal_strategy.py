from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def build_rebuttal_strategy(parsed_reviews: str, paper_summary: str,
                            runtime: Runtime) -> str:
    """Build a venue-compliant rebuttal strategy from parsed reviewer concerns.

    This is Phase 3 of the rebuttal pipeline. For each atomized concern, determine
    the response approach and build a character-budgeted strategy plan.

    Strategy construction:
    1. Identify 2-4 global themes that resolve shared concerns across reviewers
    2. Choose response_mode per issue:
       - direct_clarification: reviewer misunderstood; point to existing text
       - grounded_evidence: cite existing results or user-confirmed new results
       - nearest_work_delta: for novelty disputes, name closest prior work + exact delta
       - assumption_hierarchy: for theory concerns, separate core vs technical assumptions
       - narrow_concession: reviewer is right; concede narrowly and specifically
       - future_work_boundary: cannot address now; frame as future work honestly
    3. Build character budget: 10-15%% opener, 75-80%% per-reviewer responses, 5-10%% closing
    4. Identify blocked claims (ungrounded or unapproved) and flag them

    Safety model (three hard gates):
    1. Provenance gate: every factual statement maps to paper / review /
       user_confirmed_result / user_confirmed_derivation / future_work
    2. Commitment gate: every promise maps to already_done / approved_for_rebuttal /
       future_work_only
    3. Coverage gate: every reviewer concern ends in answered / deferred_intentionally /
       needs_user_input. No issue disappears.

    Strategy principles:
    - NEVER fabricate results or promise what user has not approved
    - Evidence > assertion
    - Global narrative first, per-reviewer detail second
    - Concrete numbers for counter-intuitive points
    - Concede narrowly when reviewer is right
    - Answer friendly reviewers too (they influence meta-reviewer)
    - If no strong evidence exists, say less not more

    Output: Structured strategy document with:
    - Global themes and narrative arc
    - Per-issue response plan with response_mode and evidence source
    - Character budget allocation
    - Blocked claims requiring user input
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Parsed reviews:\n{parsed_reviews}\n\n"
            f"Paper summary:\n{paper_summary}"
        )},
    ])
