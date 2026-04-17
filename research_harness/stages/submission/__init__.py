"""Stage: submission"""

from research_harness.stages.submission.check_submission import check_submission

import os
from typing import Optional
from openprogram.agentic_programming.runtime import Runtime


def run_submission_check(
    project_dir: str,
    venue: str,
    runtime: Runtime,
) -> dict:
    """Run pre-submission checks.

    Args:
        project_dir:  Project directory.
        venue:        Target venue.
        runtime:      LLM runtime.

    Returns:
        dict with checklist results.
    """
    project_dir = os.path.expanduser(project_dir)
    paper_dir = os.path.join(project_dir, "paper")

    # Read paper
    parts = []
    for fname in sorted(os.listdir(paper_dir)):
        if fname.endswith(".tex"):
            with open(os.path.join(paper_dir, fname), "r") as f:
                parts.append(f.read())
    paper_content = "\n\n".join(parts)

    result = check_submission(
        paper_content=paper_content[:15000],
        venue=venue,
        runtime=runtime,
    )

    # Save report
    with open(os.path.join(project_dir, "SUBMISSION_CHECKLIST.md"), "w") as f:
        f.write(f"# Submission Checklist — {venue}\n\n{result}")

    return {"checklist": result}


__all__ = ['check_submission', 'run_submission_check']
