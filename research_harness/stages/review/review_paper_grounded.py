from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, build_review_schema,
)
from research_harness.utils import call_with_schema

from research_harness.stages.review._review_prose_codex import (
    generate_review_text,
)


def _format_review_text_for_prompt(review_text: dict) -> str:
    """Render dynamic stage-1 dict (per-venue field names) for stage-2."""
    out: list[str] = []
    for fname, content in review_text.items():
        if isinstance(content, list):
            body = "\n".join(f"- {c}" for c in content)
        else:
            body = str(content or "").strip()
        if body:
            out.append(f"## Already-written `{fname}`\n{body}")
    return "\n\n".join(out)


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


def _build_structured_instructions(*, venue_name: str, venue_criteria: str,
                                   paper_content: str,
                                   review_text: dict[str, object],
                                   persona_block: str,
                                   grounding_section: str) -> str:
    """Stage-2 prompt: numeric / enum / boolean fields only.

    All free-text fields have already been written under v6 constraint;
    they are shown for context so the score/verdict line up. Stage 2 must
    NOT regenerate them.
    """
    return (
        f"You are a senior reviewer for {venue_name}. The full free-text "
        f"portion of the review has already been written (shown below). "
        f"Your task now is to call the `submit_review` tool to produce ONLY "
        f"the numeric / enum / boolean fields: `score`, `verdict`, "
        f"`sub_scores` (using {venue_name}'s exact dimension names — do NOT "
        f"substitute names from other venues), `confidence`, "
        f"`best_paper_candidate` (if applicable). Free-text fields will be "
        f"merged in automatically — do NOT regenerate them.\n\n"
        f"{persona_block}"
        f"## Venue criteria\n{venue_criteria}\n\n"
        f"{grounding_section}"
        f"{_format_review_text_for_prompt(review_text)}\n\n"
        f"## Paper under review (for reference)\n{paper_content}\n\n"
        f"Now call `submit_review`. Use {venue_name}'s exact `sub_scores` "
        f"dimension names. Do NOT respond with free text — the tool call "
        f"IS your submission."
    )


@agentic_function(render_range={"depth": 0, "siblings": 0})
def review_paper_grounded(paper_content: str, venue: str,
                          venue_criteria: str, prior_work_context: str,
                          persona: str,
                          runtime: Runtime) -> str:
    """Venue-aware grounded reviewer using a two-stage pipeline.

    Stage 1: free-form codex CLI generates the long-prose `review` field
    using the v6 sentence-template constraint (review_corpus/). Persona
    and prior-work grounding are injected into the venue_criteria string
    that the prose generator sees.

    Stage 2: tool-use call_with_schema fills the structured summary
    fields. The `review` field is excluded from this schema and patched
    in from Stage 1.

    Args:
        paper_content:        Full paper text.
        venue:                Target venue (case-insensitive, aliases handled).
        venue_criteria:       Pre-rendered criteria text.
        prior_work_context:   Markdown blob from adaptive_summarize_priors,
                              with [N] citations for the reviewer to use.
        persona:              "balanced" / "empiricist" / "theorist" /
                              "novelty_hawk" / "clarity_critic".
    """
    spec = get_venue_spec(venue)

    persona_instr = _PERSONA_INSTRUCTIONS.get(
        persona, _PERSONA_INSTRUCTIONS["balanced"]
    )
    persona_block = f"## Persona\n{persona_instr}\n\n"

    grounding_section = ""
    if prior_work_context.strip():
        grounding_section = (
            f"## Prior work context (auto-retrieved from arXiv)\n"
            f"{prior_work_context}\n\n"
            f"WHEN judging novelty / contextualization, you MUST cite "
            f"specific prior work entries by [N] notation. Do NOT rely on "
            f"your training knowledge of 'what's been done' — use the "
            f"retrieved list above.\n\n"
        )

    # Stage 1: all free-text under v6 template constraint. Persona +
    # grounding ride along inside the venue_criteria string so the prose
    # generator sees them without needing extra placeholders.
    enriched_criteria = persona_block + venue_criteria + "\n\n" + grounding_section
    review_text = generate_review_text(
        paper_content=paper_content,
        venue_name=spec.name,
        venue_criteria=enriched_criteria,
    )

    # Stage 2: structured numeric / enum / boolean fields only. Exclude
    # whatever stage 1 produced (depends on the venue's form).
    stage1_fields = tuple(review_text.keys())
    schema = build_review_schema(spec, exclude_fields=stage1_fields)
    instructions = _build_structured_instructions(
        venue_name=spec.name,
        venue_criteria=venue_criteria,
        paper_content=paper_content,
        review_text=review_text,
        persona_block=persona_block,
        grounding_section=grounding_section,
    )
    result = call_with_schema(
        runtime=runtime,
        instructions=instructions,
        schema_name="submit_review",
        schema_description=(
            f"Submit the structured numeric / enum / boolean fields for a "
            f"{spec.name} review. The free-text fields have been generated "
            f"separately and will be merged in afterwards."
        ),
        parameters=schema,
    )

    # Merge stage-1 text fields back in (whatever the venue's form has).
    for fname, content in review_text.items():
        result[fname] = content
    result["venue"] = spec.name
    result["persona"] = persona or "balanced"
    return json.dumps(result, ensure_ascii=False, indent=2)
