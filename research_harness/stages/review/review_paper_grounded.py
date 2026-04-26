from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, build_review_schema,
)
from research_harness.utils import call_with_schema


_PERSONA_INSTRUCTIONS = {
    "balanced": (
        "Default reviewer — assess all dimensions evenly with no bias toward "
        "any one aspect."
    ),
    "empiricist": (
        "**Empiricist persona**: focus 80% of your weaknesses on experimental "
        "setup. Flag missing baselines, unfair comparisons (different GPU/token "
        "budgets), missing ablations on core design decisions, weak evaluation "
        "protocols (no random seeds, no significance tests), biased dataset "
        "choices. Other dimensions still scored but with less weight."
    ),
    "theorist": (
        "**Theorist persona**: focus 80% of your weaknesses on theory. Check "
        "notation consistency, derivation completeness (no skipped steps), "
        "theorem assumptions, whether proofs actually support claims, complexity "
        "analysis correctness. If purely empirical, evaluate logical rigor of "
        "the method design / algorithm description."
    ),
    "novelty_hawk": (
        "**Novelty Hawk persona**: focus 80% of your weaknesses on novelty / "
        "prior-work positioning. For each claimed novelty, judge against the "
        "prior_work_context: genuinely_new / incremental / already_done [N]. "
        "Find missing citations (papers tagged missing_citation=true). "
        "Question every 'we propose the first' phrase. Other dimensions scored "
        "more leniently, but novelty is strict."
    ),
    "clarity_critic": (
        "**Clarity Critic persona**: focus 80% of your weaknesses on "
        "presentation. Does the abstract reflect the paper? Are introduction "
        "claims supported in method/experiment? Are figures/tables independently "
        "readable? Is notation defined before use? Are sections coherent? Is "
        "pseudocode complete? Find what is hard to understand."
    ),
}


@agentic_function(render_range={"depth": 0, "siblings": 0})
def review_paper_grounded(paper_content: str, venue: str,
                          venue_criteria: str, prior_work_context: str,
                          persona: str,
                          runtime: Runtime) -> str:
    """Venue-aware grounded review using tool-use to force structured output.

    Returns a JSON string matching the venue's review schema. Score field
    uses the venue's exact scale (e.g. ARR 1-5, NeurIPS 1-6, ICLR 0-10).

    The LLM is forced via tool-use to call the submit_review tool, so:
      - score is always within the venue's valid range
      - sub_scores follow the venue's exact dimensions (Soundness/Excitement
        for ARR; Quality/Clarity/Significance/Originality for NeurIPS; etc.)
      - verdict uses the venue's vocabulary (no more "Weak Reject" on ARR papers)

    Args:
        paper_content:        Full paper text.
        venue:                Target venue (case-insensitive, aliases handled).
        venue_criteria:       Pre-rendered criteria text (for visibility in
                              prompt; also used as fallback if spec lookup fails).
        prior_work_context:   Markdown blob from adaptive_summarize_priors,
                              with [N] citations for the reviewer to use.
        persona:              "balanced" / "empiricist" / "theorist" /
                              "novelty_hawk" / "clarity_critic".
    """
    spec = get_venue_spec(venue)
    schema = build_review_schema(spec)

    persona_instr = _PERSONA_INSTRUCTIONS.get(
        persona, _PERSONA_INSTRUCTIONS["balanced"]
    )

    grounding_section = ""
    if prior_work_context.strip():
        grounding_section = (
            f"\n=== PRIOR WORK CONTEXT (auto-retrieved from arXiv) ===\n"
            f"{prior_work_context}\n"
            f"=== END PRIOR WORK CONTEXT ===\n\n"
            f"WHEN judging novelty / contextualization, you MUST cite specific "
            f"prior work entries by [N] notation. Do NOT rely on your training "
            f"knowledge of 'what's been done' — use the retrieved list above.\n"
        )

    instructions = (
        f"You are a senior reviewer for {spec.name}. Read the paper carefully, "
        f"then call the submit_review tool with your assessment.\n\n"
        f"## Persona\n{persona_instr}\n\n"
        f"## Required scoring scale\n"
        f"You MUST use {spec.name}'s exact scoring scales. Do NOT use "
        f"vocabulary from other venues (e.g. don't say 'Weak Reject' on an ARR "
        f"paper — ARR uses 'Resubmit' / 'Findings' / 'Conference acceptance').\n\n"
        f"## Venue criteria (verbatim from official guidelines)\n"
        f"{venue_criteria}\n\n"
        f"{grounding_section}"
        f"## Paper under review\n{paper_content}\n\n"
        f"Now call the submit_review tool. Do NOT respond with free text — "
        f"the tool call IS your review."
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

    # Tag with venue + persona for downstream traceability
    result["venue"] = spec.name
    result["persona"] = persona or "balanced"
    return json.dumps(result, ensure_ascii=False, indent=2)
