from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, build_review_schema,
)
from research_harness.utils import call_with_schema


@agentic_function(render_range={"depth": 0, "siblings": 0})
def review_paper(paper_content: str, venue: str, venue_criteria: str,
                 runtime: Runtime) -> str:
    """Venue-aware reviewer (no grounding) using tool-use to force structured output.

    Returns a JSON string matching the venue's review schema. Same as
    review_paper_grounded but without prior_work_context. Use when grounding
    is disabled or for legacy callers.

    The LLM is forced via tool-use to call submit_review, so:
      - score is always within the venue's valid range
      - sub_scores follow the venue's exact dimensions
      - verdict uses the venue's vocabulary
    """
    spec = get_venue_spec(venue)
    schema = build_review_schema(spec)

    instructions = (
        f"You are a senior reviewer for {spec.name}. Read the paper carefully, "
        f"then call the submit_review tool with your assessment.\n\n"
        f"## Required scoring scale\n"
        f"Use {spec.name}'s exact scoring scales. Do NOT use vocabulary from "
        f"other venues (e.g. don't use NeurIPS-style 'Weak Reject' on an ARR "
        f"paper). The schema constrains scores to the valid range — invalid "
        f"values will be rejected.\n\n"
        f"## Venue criteria (verbatim from official guidelines)\n"
        f"{venue_criteria}\n\n"
        f"## Paper under review\n{paper_content}\n\n"
        f"Now call submit_review. Do NOT respond with free text — the tool "
        f"call IS your review."
    )

    result = call_with_schema(
        runtime=runtime,
        instructions=instructions,
        schema_name="submit_review",
        schema_description=(
            f"Submit a complete reviewer assessment for {spec.name}, "
            f"following the venue's exact scoring scale and vocabulary."
        ),
        parameters=schema,
    )
    result["venue"] = spec.name
    return json.dumps(result, ensure_ascii=False, indent=2)
