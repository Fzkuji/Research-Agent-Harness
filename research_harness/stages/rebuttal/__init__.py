"""Stage: rebuttal"""

from research_harness.stages.rebuttal.build_rebuttal_strategy import build_rebuttal_strategy
from research_harness.stages.rebuttal.draft_rebuttal import draft_rebuttal
from research_harness.stages.rebuttal.parse_reviews import parse_reviews

import os
from typing import Optional
from agentic.runtime import Runtime


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


__all__ = ['build_rebuttal_strategy', 'draft_rebuttal', 'parse_reviews', 'run_rebuttal']
