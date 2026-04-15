"""Stage: review — cross-model adversarial review with 3 difficulty levels."""

from research_harness.stages.review.fix_paper import fix_paper
from research_harness.stages.review.lookup_venue_criteria import lookup_venue_criteria
from research_harness.stages.review.review_paper import review_paper

import os
from datetime import datetime, timezone
from typing import Optional

from agentic.runtime import Runtime
from research_harness.utils import parse_json


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_paper(paper_dir: str) -> str:
    """Concatenate all .tex files in paper_dir into a single string."""
    tex_files = sorted(
        f for f in os.listdir(paper_dir)
        if f.endswith(".tex") and not f.startswith(".")
    )
    parts = []
    for fname in tex_files:
        with open(os.path.join(paper_dir, fname), "r") as f:
            parts.append(f"% === {fname} ===\n{f.read()}")
    return "\n\n".join(parts)


def _save_review_log(log_path: str, reviews: list[dict]):
    """Write the cumulative review log to AUTO_REVIEW.md."""
    lines = ["# Auto Review Log\n"]
    for r in reviews:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f"## Round {r['round']} ({ts})\n")
        lines.append(f"- **Score**: {r.get('score', '?')}/10")
        lines.append(f"- **Verdict**: {r.get('verdict', 'unknown')}")
        lines.append(f"- **Difficulty**: {r.get('difficulty', 'medium')}")
        if r.get("weaknesses"):
            lines.append("\n### Weaknesses")
            for w in r["weaknesses"]:
                lines.append(f"- {w}")
        if r.get("strengths"):
            lines.append("\n### Strengths")
            for s in r["strengths"]:
                lines.append(f"- {s}")
        if r.get("debate_transcript"):
            lines.append(f"\n### Debate Transcript\n{r['debate_transcript']}")
        lines.append("")
    with open(log_path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Review: 3 difficulty levels
# ---------------------------------------------------------------------------

def _review_medium(paper_content: str, venue: str, venue_criteria: str,
                   round_num: int, review_runtime: Runtime) -> str:
    """Medium: standard review — reviewer sees curated context."""
    return review_paper(
        paper_content=paper_content[:15000],
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
    )


def _review_hard(paper_content: str, venue: str, venue_criteria: str,
                 round_num: int, reviewer_memory: str,
                 review_runtime: Runtime) -> str:
    """Hard: reviewer gets persistent memory across rounds."""
    memory_block = ""
    if reviewer_memory.strip():
        memory_block = (
            "\n## Your Reviewer Memory (persistent across rounds)\n"
            f"{reviewer_memory}\n\n"
            "IMPORTANT: You have memory from prior rounds. Check whether "
            "your previous suspicions were genuinely addressed or merely "
            "sidestepped. Be skeptical of convenient omissions.\n\n"
        )

    augmented_content = (
        f"[Round {round_num} of autonomous review loop]\n"
        f"{memory_block}"
        f"{paper_content[:14000]}\n\n"
        "After your review, include a **Memory update** section listing "
        "any new suspicions, unresolved concerns, or patterns to track."
    )

    return review_paper(
        paper_content=augmented_content,
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
    )


def _review_nightmare(paper_content: str, venue: str, venue_criteria: str,
                      round_num: int, reviewer_memory: str,
                      review_runtime: Runtime) -> str:
    """Nightmare: reviewer gets memory + adversarial verification instructions."""
    memory_block = ""
    if reviewer_memory.strip():
        memory_block = (
            "\n## Your Reviewer Memory (persistent across rounds)\n"
            f"{reviewer_memory}\n\n"
        )

    augmented_content = (
        f"[Round {round_num} — NIGHTMARE MODE review]\n"
        f"{memory_block}"
        f"{paper_content[:13000]}\n\n"
        "## Adversarial Verification Instructions\n"
        "You have full access to all content. The author does NOT control "
        "what you see. Your job is to find problems that might be hidden.\n\n"
        "1. Verify that reported numbers are internally consistent\n"
        "2. Check if claims in the introduction match the actual evidence\n"
        "3. Look for cherry-picked results or missing ablations\n"
        "4. Check notation consistency across sections\n"
        "5. Verify each claim has sufficient evidence\n\n"
        "After your review, include:\n"
        "- **Verified claims**: which claims you confirmed\n"
        "- **Unverified claims**: which claims lack evidence\n"
        "- **Memory update**: suspicions and patterns to track\n\n"
        "Be adversarial. Trust nothing — verify everything."
    )

    return review_paper(
        paper_content=augmented_content,
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
    )


# ---------------------------------------------------------------------------
# Debate protocol (hard + nightmare)
# ---------------------------------------------------------------------------

def _run_debate(weaknesses: list, paper_content: str,
                exec_runtime: Runtime, review_runtime: Runtime) -> str:
    """Claude rebuts up to 3 weaknesses, reviewer rules on each."""
    from agentic.function import agentic_function

    @agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
    def _generate_rebuttal(weaknesses_text: str, paper_context: str,
                           runtime: Runtime) -> str:
        """You are the paper author. The reviewer identified these weaknesses.
        For each (up to 3), write a structured rebuttal:

        ### Rebuttal to Weakness #N
        - **Accept / Partially Accept / Reject**
        - **Argument**: why invalid, already addressed, or misunderstanding
        - **Evidence**: specific section, result, or code reference

        Rules:
        - Be honest — do NOT fabricate evidence
        - Can point out factual errors in the review
        - Can argue out of scope or unreasonable effort
        - Maximum 3 rebuttals (pick most impactful)
        """
        return runtime.exec(content=[
            {"type": "text", "text": f"Weaknesses:\n{weaknesses_text}\n\nPaper:\n{paper_context[:5000]}"},
        ])

    @agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
    def _rule_on_rebuttal(rebuttal_text: str, runtime: Runtime) -> str:
        """You are the reviewer. The author rebuts your review.
        For each rebuttal, rule:
        - SUSTAINED (valid, withdraw weakness)
        - OVERRULED (criticism stands, explain why)
        - PARTIALLY SUSTAINED (revise to narrower scope)

        Then update your overall assessment if any weaknesses were withdrawn.
        """
        return runtime.exec(content=[
            {"type": "text", "text": rebuttal_text},
        ])

    weaknesses_text = "\n".join(f"- {w}" for w in weaknesses[:5])

    rebuttal = _generate_rebuttal(
        weaknesses_text=weaknesses_text,
        paper_context=paper_content[:5000],
        runtime=exec_runtime,
    )

    ruling = _rule_on_rebuttal(
        rebuttal_text=f"Author's rebuttal:\n{rebuttal}",
        runtime=review_runtime,
    )

    return f"**Author's Rebuttal:**\n{rebuttal}\n\n**Reviewer's Ruling:**\n{ruling}"


# ---------------------------------------------------------------------------
# Public: paper_improvement_loop (writing quality, 2 rounds)
# ---------------------------------------------------------------------------

def paper_improvement_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    max_rounds: int = 2,
    callback: Optional[callable] = None,
) -> dict:
    """Improve paper writing quality via external review (2 rounds).

    Unlike review_loop (research-level: experiments, data, narrative),
    this iterates on WRITING QUALITY — fixing inconsistencies, softening
    overclaims, improving presentation.

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

    venue_criteria = lookup_venue_criteria(venue=venue, runtime=review_runtime)

    for round_num in range(1, max_rounds + 1):
        paper_content = _read_paper(paper_dir)

        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

        reply = review_paper(
            paper_content=paper_content[:15000],
            venue=venue,
            venue_criteria=venue_criteria,
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

        if hasattr(exec_runtime, 'reset'):
            exec_runtime.reset()

        fix_paper(
            paper_content=paper_content[:15000],
            review_feedback=reply[:5000],
            round_num=round_num,
            runtime=exec_runtime,
        )

        compile_paper(paper_dir=paper_dir, runtime=exec_runtime)

        if callback:
            callback({"type": "fix_and_compile", "round": round_num})

    with open(log_path, "w") as f:
        f.write("# Paper Improvement Log\n\n")
        for r in rounds_log:
            f.write(f"## Round {r['round']}\n")
            f.write(f"- Score: {r.get('score', '?')}/10\n\n")

    return {"rounds": rounds_log}


# ---------------------------------------------------------------------------
# Public: review_loop with 3 difficulty levels + debate
# ---------------------------------------------------------------------------

def review_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    max_rounds: int = 4,
    pass_threshold: int = 7,
    difficulty: str = "medium",
    callback: Optional[callable] = None,
) -> dict:
    """Cross-model review loop with 3 difficulty levels.

    Difficulty levels:
        medium:    Standard review — reviewer sees curated context.
        hard:      + Reviewer Memory (persistent suspicions across rounds)
                   + Debate Protocol (author rebuts, reviewer rules).
        nightmare: + Adversarial verification (reviewer checks claims
                   against actual content, looks for hidden problems).

    Args:
        paper_dir:       Path to paper/ directory with .tex files.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing (executor).
        review_runtime:  Runtime for reviewing (different model recommended).
        max_rounds:      Max review-fix cycles.
        pass_threshold:  Min score to pass (default: 7/10).
        difficulty:      "medium" | "hard" | "nightmare".
        callback:        Called after each round.

    Returns:
        dict with: passed, rounds, final_score, reviews, difficulty
    """
    if exec_runtime is None:
        raise ValueError("exec_runtime is required")
    if review_runtime is None:
        review_runtime = exec_runtime
    if difficulty not in ("medium", "hard", "nightmare"):
        raise ValueError(f"Invalid difficulty: {difficulty}")

    paper_dir = os.path.expanduser(paper_dir)
    project_dir = os.path.dirname(paper_dir)
    log_path = os.path.join(project_dir, "AUTO_REVIEW.md")
    reviews = []
    reviewer_memory = ""  # in-memory, accumulates across rounds

    venue_criteria = lookup_venue_criteria(venue=venue, runtime=review_runtime)

    for round_num in range(1, max_rounds + 1):
        paper_content = _read_paper(paper_dir)

        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

        # Phase A: Review (route by difficulty)
        if difficulty == "medium":
            reply = _review_medium(
                paper_content, venue, venue_criteria,
                round_num, review_runtime,
            )
        elif difficulty == "hard":
            reply = _review_hard(
                paper_content, venue, venue_criteria,
                round_num, reviewer_memory, review_runtime,
            )
        else:  # nightmare
            reply = _review_nightmare(
                paper_content, venue, venue_criteria,
                round_num, reviewer_memory, review_runtime,
            )

        # Phase B: Parse assessment
        try:
            review = parse_json(reply)
        except ValueError:
            review = {"score": 0, "passed": False, "weaknesses": [], "strengths": []}
        review["round"] = round_num
        review["full_review"] = reply
        review["difficulty"] = difficulty

        # Accumulate reviewer memory in-memory (hard/nightmare)
        if difficulty in ("hard", "nightmare"):
            reviewer_memory += (
                f"\n## Round {round_num} — Score: {review.get('score', 0)}/10\n"
                f"- {reply[:500]}\n"
            )

        # Debate Protocol (hard/nightmare, if weaknesses exist)
        if difficulty in ("hard", "nightmare") and review.get("weaknesses"):
            debate_transcript = _run_debate(
                review["weaknesses"], paper_content,
                exec_runtime, review_runtime,
            )
            review["debate_transcript"] = debate_transcript

        reviews.append(review)
        _save_review_log(log_path, reviews)

        if callback and callback({"type": "review", **review}) is False:
            break

        # Check stop condition
        score = review.get("score", 0)
        if score >= pass_threshold:
            return {"passed": True, "rounds": round_num,
                    "final_score": score, "reviews": reviews,
                    "difficulty": difficulty}

        # Phase C: Fix
        if hasattr(exec_runtime, 'reset'):
            exec_runtime.reset()

        fix_paper(
            paper_content=paper_content[:15000],
            review_feedback=reply[:5000],
            round_num=round_num,
            runtime=exec_runtime,
        )

        if callback:
            callback({"type": "fix", "round": round_num})

    final_score = reviews[-1].get("score", 0) if reviews else 0
    return {
        "passed": False, "rounds": max_rounds,
        "final_score": final_score, "reviews": reviews,
        "difficulty": difficulty,
    }


__all__ = [
    'fix_paper', 'lookup_venue_criteria', 'review_paper',
    'paper_improvement_loop', 'review_loop',
]
