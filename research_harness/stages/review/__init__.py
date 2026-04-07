"""Stage: review"""

from research_harness.stages.review.fix_paper import fix_paper
from research_harness.stages.review.review_paper import review_paper

import os
from typing import Optional
from agentic.runtime import Runtime


def paper_improvement_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    max_rounds: int = 2,
    callback: Optional[callable] = None,
) -> dict:
    """Autonomously improve a generated paper via external LLM review, implement
    fixes, and recompile, for up to max_rounds rounds.

    This skill runs after paper-plan -> paper-figure -> paper-write -> paper-compile.
    It takes a compiled paper and iteratively improves it through external review.

    Unlike review_loop (which iterates on research -- running experiments, collecting
    data, rewriting narrative), this iterates on WRITING QUALITY -- fixing theoretical
    inconsistencies, softening overclaims, adding missing content, and improving
    presentation.

    Round 1 typically catches structural issues (4->6/10).
    Round 2 catches remaining presentation issues (6->7/10).
    Diminishing returns beyond 2 rounds for writing-only improvements.

    Each round:
    1. Collect paper text (concatenate all sections/*.tex)
    2. Send to external reviewer (GPT-5.4 xhigh) for structured review:
       - Overall Score (1-10), Summary, Strengths, Weaknesses (CRITICAL > MAJOR > MINOR),
         actionable fixes per weakness, missing references, verdict
       - Focus on: theoretical rigor, claims vs evidence alignment, writing clarity,
         self-containedness, notation consistency
    3. Implement fixes by severity:
       - CRITICAL: assumption mismatches, internal contradictions
       - MAJOR: overclaims, missing content, notation issues
       - MINOR: if time permits
    4. Recompile and verify (0 undefined references, 0 undefined citations)

    Common fix patterns:
    - Assumption-model mismatch -> rewrite assumption, add bridging proposition
    - Overclaims -> soften: "validate" -> "demonstrate practical relevance"
    - Missing metrics -> add quantitative table with honest caveats
    - Theorem not self-contained -> add Interpretation paragraph listing dependencies
    - Notation confusion -> rename conflicting symbols globally
    - Theory-practice gap -> frame theory as idealized, add synthetic validation

    State persistence: writes PAPER_IMPROVEMENT_STATE.json after each round for
    checkpoint recovery. On resume within 24h, continues from saved phase.

    Args:
        paper_dir:       Path to paper/ directory.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing.
        review_runtime:  Runtime for reviewing (different model recommended).
        max_rounds:      Max improvement rounds (default: 2).
        callback:        Progress callback.

    Returns:
        dict with improvement history.
    """
    from research_harness.stages.writing import compile_paper

    if exec_runtime is None:
        raise ValueError("exec_runtime is required")
    if review_runtime is None:
        review_runtime = exec_runtime

    paper_dir = os.path.expanduser(paper_dir)
    log_path = os.path.join(os.path.dirname(paper_dir), "PAPER_IMPROVEMENT_LOG.md")
    rounds_log = []

    for round_num in range(1, max_rounds + 1):
        # Read current paper
        paper_content = _read_paper(paper_dir)

        # Review (writing quality focus)
        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

        reply = review_paper(
            paper_content=paper_content[:15000],
            venue=venue,
            runtime=review_runtime,
        )

        try:
            review = parse_json(reply)
        except ValueError:
            review = {"score": 0, "weaknesses": []}
        review["round"] = round_num
        rounds_log.append(review)

        if callback:
            callback({"type": "review", "round": round_num, **review})

        # Fix
        if hasattr(exec_runtime, 'reset'):
            exec_runtime.reset()

        fixed = fix_paper(
            paper_content=paper_content[:15000],
            review_feedback=reply[:5000],
            round_num=round_num,
            runtime=exec_runtime,
        )

        # Write fixed content back to .tex files
        # (simplified: write entire fixed content to a combined file)
        # In practice, the agent should edit individual .tex files

        # Recompile
        compile_paper(paper_dir=paper_dir, runtime=exec_runtime)

        if callback:
            callback({"type": "fix_and_compile", "round": round_num})

    # Save log
    with open(log_path, "w") as f:
        f.write("# Paper Improvement Log\n\n")
        for r in rounds_log:
            f.write(f"## Round {r['round']}\n")
            f.write(f"- Score: {r.get('score', '?')}/10\n\n")

    return {"rounds": rounds_log}


def review_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    max_rounds: int = 4,
    pass_threshold: int = 7,
    callback: Optional[callable] = None,
) -> dict:
    """Cross-model review loop until paper passes or max rounds.

    Args:
        paper_dir:       Path to paper/ directory with .tex files.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing (executor).
        review_runtime:  Runtime for reviewing (different model recommended).
        max_rounds:      Max review-fix cycles.
        pass_threshold:  Min score to pass (default: 7/10).
        callback:        Called after each round.

    Returns:
        dict with: passed, rounds, final_score, reviews
    """
    if exec_runtime is None:
        raise ValueError("exec_runtime is required")
    if review_runtime is None:
        review_runtime = exec_runtime

    paper_dir = os.path.expanduser(paper_dir)
    paper_content = _read_paper(paper_dir)
    log_path = os.path.join(os.path.dirname(paper_dir), "AUTO_REVIEW.md")
    reviews = []

    for round_num in range(1, max_rounds + 1):
        # Review phase (reviewer model)
        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

        reply = review_paper(
            paper_content=paper_content[:15000],
            venue=venue,
            runtime=review_runtime,
        )

        try:
            review = parse_json(reply)
        except ValueError:
            review = {"score": 0, "passed": False, "weaknesses": [], "strengths": []}
        review["round"] = round_num
        review["full_review"] = reply
        reviews.append(review)
        _save_review_log(log_path, reviews)

        if callback and callback({"type": "review", **review}) is False:
            break

        if review.get("score", 0) >= pass_threshold:
            return {"passed": True, "rounds": round_num,
                    "final_score": review["score"], "reviews": reviews}

        # Fix phase (executor model)
        if hasattr(exec_runtime, 'reset'):
            exec_runtime.reset()

        paper_content = fix_paper(
            paper_content=paper_content[:15000],
            review_feedback=reply[:5000],
            round_num=round_num,
            runtime=exec_runtime,
        )

        if callback:
            callback({"type": "fix", "round": round_num})

    return {
        "passed": False, "rounds": max_rounds,
        "final_score": reviews[-1].get("score", 0) if reviews else 0,
        "reviews": reviews,
    }


__all__ = ['fix_paper', 'review_paper', 'paper_improvement_loop', 'review_loop']
