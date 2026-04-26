"""Stage: rebuttal"""

from research_harness.stages.rebuttal.anti_sycophancy_guard import anti_sycophancy_guard
from research_harness.stages.rebuttal.build_rebuttal_strategy import build_rebuttal_strategy
from research_harness.stages.rebuttal.draft_rebuttal import draft_rebuttal
from research_harness.stages.rebuttal.parse_reviews import parse_reviews

import os
from typing import Optional
from openprogram.agentic_programming.runtime import Runtime


def run_rebuttal(
    reviews_text: str,
    paper_dir: str,
    venue: str = "ICML",
    char_limit: int = 5000,
    runtime: Runtime = None,
    with_anti_sycophancy: bool = True,
) -> dict:
    """Run the full rebuttal pipeline.

    Args:
        reviews_text:         Raw reviewer comments.
        paper_dir:            Path to paper. Accepts any format supported by
                              load_paper (dir of .tex, .pdf, .docx, .md, ...).
        venue:                Target venue.
        char_limit:           Character limit for rebuttal.
        runtime:              LLM runtime.
        with_anti_sycophancy: If True (default), run anti_sycophancy_guard
                              over the rebuttal draft to catch unwarranted
                              concessions, evidence-missing claims, and
                              improper deferrals.

    Returns:
        dict with parsed reviews, strategy, draft rebuttal, and (optionally)
        anti_sycophancy audit.
    """
    if runtime is None:
        raise ValueError("runtime is required")

    paper_dir = os.path.expanduser(paper_dir)

    # Use the unified loader (supports .pdf/.docx/.md/.tex/dir).
    from research_harness.stages.review.load_paper import load_paper
    try:
        paper_summary = load_paper(paper_dir, runtime)
    except Exception:
        # Fallback to legacy .tex-only behavior.
        paper_parts = []
        for f in sorted(os.listdir(paper_dir)):
            if f.endswith(".tex"):
                with open(os.path.join(paper_dir, f), "r") as fh:
                    paper_parts.append(fh.read())
        paper_summary = "\n".join(paper_parts)
    paper_summary = paper_summary[:10000]

    parsed = parse_reviews(reviews_text=reviews_text, runtime=runtime)
    strategy = build_rebuttal_strategy(
        parsed_reviews=parsed, paper_summary=paper_summary, runtime=runtime,
    )
    draft = draft_rebuttal(
        strategy=strategy, venue=venue, char_limit=char_limit, runtime=runtime,
    )

    audit = None
    if with_anti_sycophancy:
        audit = anti_sycophancy_guard(
            rebuttal_draft=draft,
            original_reviews=reviews_text,
            paper_content=paper_summary,
            venue=venue,
            runtime=runtime,
        )

    # Save outputs
    if os.path.isdir(paper_dir):
        project_dir = os.path.dirname(paper_dir.rstrip("/")) or paper_dir
    else:
        project_dir = os.path.dirname(paper_dir)
    rebuttal_dir = os.path.join(project_dir, "rebuttal")
    os.makedirs(rebuttal_dir, exist_ok=True)

    with open(os.path.join(rebuttal_dir, "REBUTTAL_DRAFT.md"), "w") as f:
        f.write(f"# Rebuttal — {venue}\n\n{draft}")
    with open(os.path.join(rebuttal_dir, "STRATEGY.md"), "w") as f:
        f.write(f"# Rebuttal Strategy\n\n{strategy}")
    if audit is not None:
        with open(os.path.join(rebuttal_dir, "ANTI_SYCOPHANCY_AUDIT.md"), "w") as f:
            f.write(f"# Anti-Sycophancy Audit\n\n{audit}")

    return {
        "parsed_reviews": parsed,
        "strategy": strategy,
        "draft": draft,
        "anti_sycophancy_audit": audit,
    }


__all__ = ['anti_sycophancy_guard', 'build_rebuttal_strategy',
           'draft_rebuttal', 'parse_reviews', 'run_rebuttal']
