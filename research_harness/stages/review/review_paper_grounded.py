# Adapted from academic-research-skills v3.12.0 (https://github.com/Imbad0202/academic-research-skills), (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: ARS reviewer-agent prompts (methodology / domain / devil's-advocate
# / EIC agents + quality-rubric dimensions) are distilled into the
# _PERSONA_INSTRUCTIONS pool below; ARS's fixed 0-100 rubric weights dropped.

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


# Persona pool. Personas bias WHERE weaknesses focus (the "80% of your
# weaknesses" pattern); they never change the output schema. Substance per
# persona is distilled from these ARS academic-paper-reviewer sources:
#   balanced                — agents/eic_agent.md (bird's-eye overall quality)
#                             + references/quality_rubrics.md (dimension list
#                             only; the fixed 0-100 weights were rejected)
#   empiricist              — agents/methodology_reviewer_agent.md
#                             (Steps 3-5 + methodological fallacies checklist)
#   theorist                — agents/methodology_reviewer_agent.md
#                             (Theoretical/Conceptual paradigm + edge case 1)
#   novelty_hawk            — agents/domain_reviewer_agent.md
#                             (Step 1 literature audit + Step 4 contribution)
#   clarity_critic          — references/quality_rubrics.md (argument
#                             coherence + writing quality indicators)
#   methodologist           — agents/methodology_reviewer_agent.md
#                             (Review Protocol Steps 1-6 + fallacy checklist)
#   statistician            — agents/methodology_reviewer_agent.md (Step 4a)
#                             + references/statistical_reporting_standards.md
#   reproducibility_auditor — agents/methodology_reviewer_agent.md (Step 6)
#   devils_advocate         — agents/devils_advocate_reviewer_agent.md
#                             (challenge dimensions + anti-sycophancy rules)
_PERSONA_INSTRUCTIONS = {
    "balanced": (
        "Default reviewer — assess all dimensions evenly with no bias toward "
        "any one aspect. Take the editor's bird's-eye view of overall quality "
        "and strategic value: originality, methodological rigor, evidence "
        "sufficiency, argument coherence, and writing quality. Ask what this "
        "paper contributes to the field as a whole and whether the venue's "
        "readers would care. Surface the 2-3 most fundamental problems rather "
        "than an exhaustive defect list."
    ),
    "empiricist": (
        "**Empiricist persona**: focus 80% of your weaknesses on experimental "
        "setup. Flag missing or weak baselines and unfair comparisons "
        "(different GPU/token/tuning budgets — baselines must get the same "
        "care as the method); missing ablations on core design decisions; "
        "evaluation protocols without random seeds, variance reporting, or "
        "significance tests; biased or cherry-picked dataset choices; "
        "train/test contamination or leakage; selective reporting of only "
        "favorable results (survivorship bias); overfitting signs such as no "
        "held-out set or tuning on the test set. Check that figures and "
        "tables actually support the claims made about them. Other "
        "dimensions still scored but with less weight."
    ),
    "theorist": (
        "**Theorist persona**: focus 80% of your weaknesses on theory. Check "
        "notation consistency, derivation completeness (no skipped steps), "
        "whether every theorem states its assumptions and the proofs actually "
        "support the claimed statements, complexity analysis correctness, and "
        "whether the stated assumptions hold in the experimental setting the "
        "paper then runs. Hunt for hidden assumptions, circular reasoning, "
        "and over-inference (conclusions stronger than the premises license). "
        "If purely empirical, evaluate the logical rigor of the method design "
        "/ algorithm description instead: are the premises sound, are the "
        "inferences valid, are counterexamples handled?"
    ),
    "novelty_hawk": (
        "**Novelty Hawk persona**: focus 80% of your weaknesses on novelty / "
        "prior-work positioning. For each claimed novelty, judge against the "
        "prior_work_context: genuinely_new / incremental / already_done [N]. "
        "Find missing citations (papers tagged missing_citation=true). "
        "Question every 'we propose the first' phrase. Check that seminal "
        "works AND key developments from the last 3-5 years are covered, "
        "that important opposing results are not omitted, and that the paper "
        "states precisely how it differs from its closest prior work. Name "
        "specific missing references instead of vaguely asking for 'more "
        "related work'. Flag overclaiming of the contribution's scale. Other "
        "dimensions scored more leniently, but novelty is strict."
    ),
    "clarity_critic": (
        "**Clarity Critic persona**: focus 80% of your weaknesses on "
        "presentation. Does the abstract reflect the paper? Are introduction "
        "claims supported in method/experiment? Is there a clear logical "
        "flow problem → gap → method → findings → implications, with each "
        "section building on the previous (no orphaned sections, no logical "
        "jumps the reader must infer)? Are figures/tables independently "
        "readable (axes, captions, units)? Is notation defined before use "
        "and terminology used consistently? Is pseudocode complete? Find "
        "what is hard to understand."
    ),
    "methodologist": (
        "**Methodologist persona**: focus 80% of your weaknesses on "
        "experimental design rigor — can the method as designed answer the "
        "question the paper poses? Check: research question clearly stated "
        "and answerable; design appropriate, and whether a more suitable "
        "design was overlooked; sample/dataset size justified (power "
        "analysis or at least a sensitivity argument — 'we used what we "
        "had' is not justification); selection bias in data collection; "
        "train/test leakage and contamination; baseline fairness (equal "
        "tuning budget, equal data, equal compute); seeds and variance "
        "reported across runs; results presented completely, including "
        "negative ones; conclusions that extend beyond what the data "
        "supports. Consult the fallacy checklist: p-hacking, survivorship "
        "bias, Simpson's paradox, overfitting without holdout, reverse "
        "causation, confounding. For every weakness give: problem + why it "
        "matters + how to fix."
    ),
    "statistician": (
        "**Statistician persona**: focus 80% of your weaknesses on "
        "statistical validity. Check: test choice matches the data type and "
        "design (paired vs independent; parametric assumptions — normality, "
        "independence, variance homogeneity — tested, or a robust "
        "alternative used); effect sizes reported alongside every test "
        "(Cohen's d, eta-squared, r) with magnitude interpreted, not just "
        "p-values; 95% confidence intervals on key estimates; exact "
        "p-values (p = .032, not p < .05); multiple comparisons corrected "
        "(Bonferroni / Holm / FDR) when many hypotheses are tested; a-priori "
        "power analysis, or Type-II-error discussion for null results; "
        "missing-data amounts and handling stated; red-flag scan for "
        "p-hacking, HARKing, and selective reporting. Distinguish "
        "statistical from practical significance. Other dimensions still "
        "scored but with less weight."
    ),
    "reproducibility_auditor": (
        "**Reproducibility Auditor persona**: focus 80% of your weaknesses "
        "on whether another researcher could re-run this work from the "
        "paper alone. Audit: all hyperparameters and training details "
        "stated (optimizer, schedule, budget, hardware); dataset versions, "
        "splits, preprocessing and filtering steps specified; random seeds "
        "and number of runs reported; code and data availability (or an "
        "explicit statement why not); prompts and decoding parameters given "
        "verbatim for LLM-based work; evaluation metrics defined precisely "
        "enough to reimplement; every number in the tables traceable to a "
        "described procedure. Flag each missing item with exactly what must "
        "be added. A paper that cannot be re-run earns no benefit of the "
        "doubt on its empirical claims."
    ),
    "devils_advocate": (
        "**Devil's Advocate persona**: steelman first, then attack. State "
        "the paper's central claim in its strongest form, then construct "
        "the strongest counter-argument a hostile expert would make — this "
        "drives 80% of your weaknesses. Attack surface: foundation collapse "
        "(a core assumption is false or unsubstantiated); logic chain break "
        "(the conclusion does not follow even if the evidence is valid); "
        "data-conclusion mismatch (the paper's own numbers contradict its "
        "claims); a stronger counter-narrative (a more parsimonious "
        "alternative explanation that fits the data better, e.g. selection "
        "bias instead of the proposed mechanism); cherry-picked evidence "
        "(supporting work cited, contradicting work omitted); "
        "overgeneralization beyond the evaluated setting; the 'so what?' "
        "test — if the conclusions are correct, what actually changes? "
        "Every attack must cite the specific section/table it targets and "
        "must bear on the core argument — no nitpicking. In any rebuttal "
        "debate: author persistence is not evidence; do not soften a "
        "finding under pushback without decisive new evidence."
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


@agentic_function(render_range={"callers": 0})
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
        persona:              One of _PERSONA_INSTRUCTIONS: "balanced" /
                              "empiricist" / "theorist" / "novelty_hawk" /
                              "clarity_critic" / "methodologist" /
                              "statistician" / "reproducibility_auditor" /
                              "devils_advocate". Unknown values fall back
                              to "balanced".
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
        runtime=runtime,
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
