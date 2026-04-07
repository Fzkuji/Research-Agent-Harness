"""
rebuttal — handle reviewer rebuttals after submission.

Parses reviews, builds response strategy, drafts venue-compliant
rebuttals with safety checks (no fabrication, no overpromise).
"""

from __future__ import annotations

import os
from typing import Optional

from agentic.function import agentic_function
from agentic.runtime import Runtime
from research_harness.utils import parse_json


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


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def build_rebuttal_strategy(parsed_reviews: str, paper_summary: str,
                            runtime: Runtime) -> str:
    """Build a response strategy for each reviewer concern.

    For each concern:
    1. Can we address it? (yes with evidence / yes with clarification / no)
    2. What evidence do we have? (existing results, new experiments needed)
    3. Priority: address fatal/major issues first
    4. Shared concerns across reviewers (address once, reference in others)

    Strategy principles:
    - NEVER fabricate results or promise things you can't deliver
    - Acknowledge valid criticisms honestly
    - Point to existing evidence when possible
    - For experiments we can't run: explain constraints, offer alternatives

    Output: Structured strategy document with response plan per concern.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Parsed reviews:\n{parsed_reviews}\n\n"
            f"Paper summary:\n{paper_summary}"
        )},
    ])


@agentic_function(compress=True, summarize={"siblings": -1})
def draft_rebuttal(strategy: str, venue: str, char_limit: int,
                   runtime: Runtime) -> str:
    """Draft a venue-compliant rebuttal response.

    Rules:
    - Stay within character limit (count carefully).
    - Address ALL concerns — reviewers check if you ignored anything.
    - Lead with strongest responses to most damaging concerns.
    - Be respectful but confident. Don't grovel.
    - Every claim in the rebuttal must be backed by evidence from the paper
      or user-confirmed new results. NO fabrication.
    - Use "We clarify that..." / "We have added..." / "We respectfully note..."
    - If a concern is valid and cannot be fully addressed: acknowledge it,
      explain what you've done to mitigate, and describe future plans.

    Safety checks before output:
    1. Every claim maps to paper/review/user-confirmed result?
    2. No overpromises?
    3. Every reviewer concern addressed?

    Output: Plain text rebuttal ready to paste into submission system.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n"
            f"Character limit: {char_limit}\n\n"
            f"Response strategy:\n{strategy}"
        )},
    ])


def run_rebuttal(
    reviews_text: str,
    paper_dir: str,
    venue: str = "ICML",
    char_limit: int = 5000,
    runtime: Runtime = None,
) -> dict:
    """Run the full rebuttal pipeline.

    Args:
        reviews_text:  Raw reviewer comments.
        paper_dir:     Path to paper directory.
        venue:         Target venue.
        char_limit:    Character limit for rebuttal.
        runtime:       LLM runtime.

    Returns:
        dict with parsed reviews, strategy, and draft rebuttal.
    """
    if runtime is None:
        raise ValueError("runtime is required")

    paper_dir = os.path.expanduser(paper_dir)

    # Read paper for context
    paper_parts = []
    for f in sorted(os.listdir(paper_dir)):
        if f.endswith(".tex"):
            with open(os.path.join(paper_dir, f), "r") as fh:
                paper_parts.append(fh.read())
    paper_summary = "\n".join(paper_parts)[:10000]

    parsed = parse_reviews(reviews_text=reviews_text, runtime=runtime)
    strategy = build_rebuttal_strategy(
        parsed_reviews=parsed, paper_summary=paper_summary, runtime=runtime,
    )
    draft = draft_rebuttal(
        strategy=strategy, venue=venue, char_limit=char_limit, runtime=runtime,
    )

    # Save
    project_dir = os.path.dirname(paper_dir)
    rebuttal_dir = os.path.join(project_dir, "rebuttal")
    os.makedirs(rebuttal_dir, exist_ok=True)

    with open(os.path.join(rebuttal_dir, "REBUTTAL_DRAFT.md"), "w") as f:
        f.write(f"# Rebuttal — {venue}\n\n{draft}")
    with open(os.path.join(rebuttal_dir, "STRATEGY.md"), "w") as f:
        f.write(f"# Rebuttal Strategy\n\n{strategy}")

    return {"parsed_reviews": parsed, "strategy": strategy, "draft": draft}
