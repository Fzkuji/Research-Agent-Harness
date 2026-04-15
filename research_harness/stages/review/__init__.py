"""Stage: review — cross-model adversarial review following ARIS design.

ARIS design: reviewer (GPT) and author (Claude) are different models.
The reviewer audits the paper, the author rebuts and fixes.
3 difficulty levels control how adversarial the reviewer is.

Reference: https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
"""

from research_harness.stages.review.fix_paper import fix_paper
from research_harness.stages.review.lookup_venue_criteria import lookup_venue_criteria
from research_harness.stages.review.review_paper import review_paper

import os
from datetime import datetime, timezone
from typing import Optional

from agentic.function import agentic_function
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
    """Write cumulative review log to AUTO_REVIEW.md (ARIS Phase E)."""
    lines = ["# Auto Review Log\n"]
    for r in reviews:
        ts = r.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        lines.append(f"## Round {r['round']} ({ts})\n")
        lines.append(f"### Assessment (Summary)")
        lines.append(f"- **Score**: {r.get('score', '?')}/10")
        lines.append(f"- **Verdict**: {r.get('verdict', 'unknown')}")
        lines.append(f"- **Difficulty**: {r.get('difficulty', 'medium')}")
        if r.get("weaknesses"):
            lines.append("\n### Weaknesses (ranked)")
            for i, w in enumerate(r["weaknesses"], 1):
                lines.append(f"{i}. {w}")
        if r.get("strengths"):
            lines.append("\n### Strengths")
            for s in r["strengths"]:
                lines.append(f"- {s}")
        if r.get("full_review"):
            lines.append("\n### Reviewer Raw Response")
            lines.append("\n<details>")
            lines.append("<summary>Click to expand full reviewer response</summary>\n")
            lines.append(r["full_review"])
            lines.append("\n</details>")
        if r.get("debate_transcript"):
            lines.append("\n### Debate Transcript")
            lines.append("\n<details>")
            lines.append("<summary>Click to expand debate</summary>\n")
            lines.append(r["debate_transcript"])
            lines.append("\n</details>")
        if r.get("actions_taken"):
            lines.append(f"\n### Actions Taken\n{r['actions_taken']}")
        lines.append("")
    with open(log_path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Phase A: Review — 3 difficulty levels
# ---------------------------------------------------------------------------

def _review_medium(paper_content: str, venue: str, venue_criteria: str,
                   round_num: int, max_rounds: int,
                   review_runtime: Runtime) -> str:
    """Medium: standard review — reviewer sees curated context (15k tokens)."""
    return review_paper(
        paper_content=(
            f"[Round {round_num}/{max_rounds} of autonomous review loop]\n\n"
            f"{paper_content[:15000]}"
        ),
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
    )


def _review_hard(paper_content: str, venue: str, venue_criteria: str,
                 round_num: int, max_rounds: int,
                 reviewer_memory: str,
                 review_runtime: Runtime) -> str:
    """Hard: reviewer gets persistent memory across rounds.

    Reviewer can track suspicions and check if previous concerns were
    genuinely addressed or merely sidestepped.
    """
    memory_block = ""
    if reviewer_memory.strip():
        memory_block = (
            "\n## Your Reviewer Memory (persistent across rounds)\n"
            f"{reviewer_memory}\n\n"
            "IMPORTANT: You have memory from prior rounds. Check whether "
            "your previous suspicions were genuinely addressed or merely "
            "sidestepped. The author controls what context you see — be "
            "skeptical of convenient omissions.\n\n"
        )

    return review_paper(
        paper_content=(
            f"[Round {round_num}/{max_rounds} of autonomous review loop]\n"
            f"{memory_block}"
            f"{paper_content[:14000]}\n\n"
            "After your review, include a **Memory update** section listing "
            "any new suspicions, unresolved concerns, or patterns to track."
        ),
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
    )


def _review_nightmare(paper_content: str, venue: str, venue_criteria: str,
                      round_num: int, max_rounds: int,
                      reviewer_memory: str,
                      review_runtime: Runtime) -> str:
    """Nightmare: reviewer gets memory + adversarial verification + full content.

    Key difference from hard: NO content truncation. The reviewer sees
    everything and is instructed to verify claims independently.
    In ARIS, this maps to GPT reading the repo directly via codex exec.
    """
    memory_block = ""
    if reviewer_memory.strip():
        memory_block = (
            "\n## Your Reviewer Memory (persistent across rounds)\n"
            f"{reviewer_memory}\n\n"
        )

    return review_paper(
        paper_content=(
            f"[Round {round_num}/{max_rounds} — NIGHTMARE MODE review]\n"
            f"{memory_block}"
            f"{paper_content}\n\n"  # NO truncation — reviewer sees everything
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
        ),
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
    )


# ---------------------------------------------------------------------------
# Phase B.6: Debate protocol (hard + nightmare)
# ---------------------------------------------------------------------------

def _run_debate(weaknesses: list, paper_content: str,
                exec_runtime: Runtime, review_runtime: Runtime) -> str:
    """Author (exec_runtime) rebuts up to 3 weaknesses, reviewer (review_runtime) rules.

    ARIS design: Claude writes rebuttal, GPT judges.
    - SUSTAINED: valid rebuttal, withdraw weakness
    - OVERRULED: criticism stands
    - PARTIALLY SUSTAINED: narrow the scope
    """

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

    # Author (Claude/exec) writes rebuttal
    rebuttal = _generate_rebuttal(
        weaknesses_text=weaknesses_text,
        paper_context=paper_content[:5000],
        runtime=exec_runtime,
    )

    # Reviewer (GPT/review) rules on rebuttal
    ruling = _rule_on_rebuttal(
        rebuttal_text=f"Author's rebuttal:\n{rebuttal}",
        runtime=review_runtime,
    )

    return (
        f"**Author's Rebuttal:**\n{rebuttal}\n\n"
        f"**Reviewer's Ruling:**\n{ruling}"
    )


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
    """Improve paper writing quality via cross-model review (2 rounds).

    Unlike review_loop (research-level critique), this iterates on
    WRITING QUALITY — fixing inconsistencies, softening overclaims,
    improving presentation.

    Args:
        paper_dir:       Path to paper/ directory.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing (author model).
        review_runtime:  Runtime for reviewing (reviewer model, different recommended).
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
# Public: review_loop — ARIS-style cross-model review with 3 difficulty levels
# ---------------------------------------------------------------------------

POSITIVE_THRESHOLD = 6  # ARIS: score >= 6/10 or verdict contains "accept"/"ready"

def review_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    max_rounds: int = 4,
    pass_threshold: int = POSITIVE_THRESHOLD,
    difficulty: str = "medium",
    callback: Optional[callable] = None,
) -> dict:
    """Cross-model review loop following ARIS design.

    The reviewer (review_runtime, e.g. GPT) and the author (exec_runtime,
    e.g. Claude) are different models. The reviewer audits the paper,
    the author rebuts (hard/nightmare) and fixes.

    Workflow per round (ARIS phases):
      Phase A: Review (routed by difficulty)
      Phase B: Parse assessment (extract score, verdict, weaknesses)
      Phase B.5: Update reviewer memory (hard/nightmare)
      Phase B.6: Debate protocol — author rebuts, reviewer rules (hard/nightmare)
      Phase C: Fix paper based on review feedback
      Phase E: Document round to AUTO_REVIEW.md

    Difficulty levels:
        medium:    Standard review — reviewer sees curated context (15k tokens).
        hard:      + Reviewer Memory (persistent suspicions across rounds)
                   + Debate Protocol (author rebuts, reviewer rules).
        nightmare: + Adversarial verification + NO content truncation
                   (reviewer sees everything, verifies claims independently).

    Args:
        paper_dir:       Path to paper/ directory with .tex files.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing (author model, e.g. Claude).
        review_runtime:  Runtime for reviewing (reviewer model, e.g. GPT).
        max_rounds:      Max review-fix cycles (default: 4).
        pass_threshold:  Min score to pass (default: 6/10, ARIS standard).
        difficulty:      "medium" | "hard" | "nightmare".
        callback:        Called after each phase. Return False to break.

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

    # ── Initialization ──
    venue_criteria = lookup_venue_criteria(venue=venue, runtime=review_runtime)

    for round_num in range(1, max_rounds + 1):
        paper_content = _read_paper(paper_dir)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

        # ── Phase A: Review (route by difficulty) ──
        if difficulty == "medium":
            reply = _review_medium(
                paper_content, venue, venue_criteria,
                round_num, max_rounds, review_runtime,
            )
        elif difficulty == "hard":
            reply = _review_hard(
                paper_content, venue, venue_criteria,
                round_num, max_rounds, reviewer_memory, review_runtime,
            )
        else:  # nightmare
            reply = _review_nightmare(
                paper_content, venue, venue_criteria,
                round_num, max_rounds, reviewer_memory, review_runtime,
            )

        # ── Phase B: Parse assessment ──
        try:
            review = parse_json(reply)
        except ValueError:
            review = {"score": 0, "passed": False, "weaknesses": [], "strengths": []}
        review["round"] = round_num
        review["full_review"] = reply
        review["difficulty"] = difficulty
        review["timestamp"] = ts

        # ── Phase B.5: Reviewer Memory (hard/nightmare) ──
        if difficulty in ("hard", "nightmare"):
            reviewer_memory += (
                f"\n## Round {round_num} — Score: {review.get('score', 0)}/10\n"
                f"- **Suspicions**: {reply[:500]}\n"
            )

        # ── Phase B.6: Debate Protocol (hard/nightmare) ──
        if difficulty in ("hard", "nightmare") and review.get("weaknesses"):
            debate_transcript = _run_debate(
                review["weaknesses"], paper_content,
                exec_runtime, review_runtime,
            )
            review["debate_transcript"] = debate_transcript

        # ── Phase E: Document round ──
        reviews.append(review)
        _save_review_log(log_path, reviews)

        if callback and callback({"type": "review", **review}) is False:
            break

        # ── Stop condition (ARIS: score >= 6 or verdict contains "ready") ──
        score = review.get("score", 0)
        verdict = str(review.get("verdict", "")).lower()
        is_positive = (
            score >= pass_threshold
            or "accept" in verdict
            or "ready" in verdict
        )
        if is_positive:
            return {"passed": True, "rounds": round_num,
                    "final_score": score, "reviews": reviews,
                    "difficulty": difficulty}

        # ── Phase C: Fix paper ──
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

    # ── Termination: max rounds reached without passing ──
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
