from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def draft_rebuttal(strategy: str, venue: str, char_limit: int,
                   runtime: Runtime) -> str:
    """Draft a venue-compliant, safety-validated rebuttal response.

    This is Phase 4-5 of the rebuttal pipeline. Takes the strategy plan and produces
    a paste-ready rebuttal within the character limit.

    Structure:
    1. Short opener: thank reviewers + 2-4 global theme resolutions
    2. Per-reviewer numbered responses: answer -> evidence -> implication
    3. Short closing: resolved / remaining / acceptance case

    Default reply pattern per issue:
    - Sentence 1: direct answer
    - Sentences 2-4: grounded evidence (numbers, citations, existing results)
    - Last sentence: implication for the paper

    Heuristics from successful rebuttals:
    - Evidence > assertion
    - Global narrative first, per-reviewer detail second
    - Concrete numbers for counter-intuitive points
    - Name closest prior work + exact delta for novelty disputes
    - Concede narrowly when reviewer is right
    - For theory: separate core vs technical assumptions
    - Answer friendly reviewers too

    Hard rules:
    - NEVER invent experiments, numbers, derivations, citations, or links
    - NEVER promise what user has not approved
    - If no strong evidence exists, say less not more
    - Stay within character limit (count carefully)
    - Address ALL concerns: reviewers check if you ignored anything

    Safety validation before output (all must pass):
    1. Coverage: every issue from the strategy maps to a draft anchor
    2. Provenance: every factual sentence has a source (paper/review/user_confirmed)
    3. Commitment: promises are approved (already_done/approved_for_rebuttal/future_work_only)
    4. Tone: flag aggressive/submissive/evasive phrases
    5. Consistency: no contradictions across reviewer replies
    6. Limit: exact character count; if over, compress by removing redundancy -> friendly
       filler -> opener padding -> wording; never drop critical answers

    Output: Plain text rebuttal ready to paste into submission system,
    with exact character count reported.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n"
            f"Character limit: {char_limit}\n\n"
            f"Response strategy:\n{strategy}"
        )},
    ])
