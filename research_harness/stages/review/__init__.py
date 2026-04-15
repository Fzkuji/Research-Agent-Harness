"""Stage: review — cross-model adversarial review following ARIS design.

ARIS design: reviewer (GPT) and author (Claude) are different models.
The reviewer audits the paper, the author rebuts and fixes.
3 difficulty levels control information asymmetry between author and reviewer.

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
# Helpers
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
    """Write cumulative review log to AUTO_REVIEW.md."""
    lines = ["# Auto Review Log\n"]
    for r in reviews:
        ts = r.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        lines.append(f"## Round {r['round']} ({ts})\n")
        lines.append(f"### Assessment")
        lines.append(f"- **Score**: {r.get('score', '?')}/10")
        lines.append(f"- **Verdict**: {r.get('verdict', 'unknown')}")
        lines.append(f"- **Difficulty**: {r.get('difficulty', 'medium')}")
        if r.get("weaknesses"):
            lines.append("\n### Weaknesses")
            for i, w in enumerate(r["weaknesses"], 1):
                lines.append(f"{i}. {w}")
        if r.get("strengths"):
            lines.append("\n### Strengths")
            for s in r["strengths"]:
                lines.append(f"- {s}")
        if r.get("full_review"):
            lines.append("\n### Full Review")
            lines.append("\n<details>")
            lines.append("<summary>Click to expand</summary>\n")
            lines.append(r["full_review"])
            lines.append("\n</details>")
        if r.get("debate_transcript"):
            lines.append("\n### Debate")
            lines.append("\n<details>")
            lines.append("<summary>Click to expand</summary>\n")
            lines.append(r["debate_transcript"])
            lines.append("\n</details>")
        lines.append("")
    with open(log_path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Review by difficulty (Step 2 of review_loop)
#
# Difficulty = who controls information:
#   medium:    author curates content for reviewer
#   hard:      author curates content, but reviewer has memory + debate
#   nightmare: reviewer reads files independently, author has zero control
# ---------------------------------------------------------------------------

def _review_medium(paper_content: str, venue: str, venue_criteria: str,
                   round_num: int, max_rounds: int,
                   review_runtime: Runtime) -> str:
    """Medium: reviewer sees author-curated content (15k tokens)."""
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
    """Hard: reviewer sees author-curated content + has persistent memory."""
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


def _review_nightmare(paper_dir: str, venue: str, venue_criteria: str,
                      round_num: int, max_rounds: int,
                      reviewer_memory: str,
                      review_runtime: Runtime) -> str:
    """Nightmare: reviewer reads files independently, author has zero info control.

    - CLI runtimes (Codex/ClaudeCode): reviewer reads .tex files via tools
    - API runtimes: fallback to passing full content (no file access)
    """
    memory_block = ""
    if reviewer_memory.strip():
        memory_block = (
            "\n## Your Reviewer Memory (persistent across rounds)\n"
            f"{reviewer_memory}\n\n"
        )

    adversarial_instructions = (
        "## Adversarial Verification Instructions\n"
        "1. Verify that reported numbers are internally consistent\n"
        "2. Check if claims in the introduction match the actual evidence\n"
        "3. Look for cherry-picked results or missing ablations\n"
        "4. Check notation consistency across sections\n"
        "5. Verify each claim has sufficient evidence\n"
        "6. Check if referenced figures/tables actually exist and match descriptions\n\n"
        "After your review, include:\n"
        "- **Verified claims**: which claims you confirmed\n"
        "- **Unverified claims**: which claims lack evidence\n"
        "- **Memory update**: suspicions and patterns to track\n\n"
        "Be adversarial. Trust nothing — verify everything."
    )

    runtime_has_file_access = hasattr(review_runtime, 'cli_path')

    if runtime_has_file_access:
        return review_paper(
            paper_content=(
                f"[Round {round_num}/{max_rounds} — NIGHTMARE MODE]\n"
                f"{memory_block}"
                f"## Independent Verification Mode\n"
                f"The paper files are at: {paper_dir}\n"
                f"You MUST read the .tex files yourself. Do NOT rely on any "
                f"author-provided summary. The author does NOT control what "
                f"you see — explore freely.\n\n"
                f"Read ALL .tex files in the directory. Check code, data, "
                f"results files if they exist.\n\n"
                f"{adversarial_instructions}"
            ),
            venue=venue,
            venue_criteria=venue_criteria,
            runtime=review_runtime,
        )
    else:
        paper_content = _read_paper(paper_dir)
        return review_paper(
            paper_content=(
                f"[Round {round_num}/{max_rounds} — NIGHTMARE MODE]\n"
                f"(API mode: no file access, full content below.)\n"
                f"{memory_block}"
                f"{paper_content}\n\n"
                f"{adversarial_instructions}"
            ),
            venue=venue,
            venue_criteria=venue_criteria,
            runtime=review_runtime,
        )


# ---------------------------------------------------------------------------
# Debate protocol (Step 4 of review_loop, hard + nightmare only)
# ---------------------------------------------------------------------------

def _run_debate(weaknesses: list, paper_content: str,
                exec_runtime: Runtime, review_runtime: Runtime) -> str:
    """Author (Claude) rebuts weaknesses, reviewer (GPT) rules on each.

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

    rebuttal = _generate_rebuttal(
        weaknesses_text=weaknesses_text,
        paper_context=paper_content[:5000],
        runtime=exec_runtime,
    )

    ruling = _rule_on_rebuttal(
        rebuttal_text=f"Author's rebuttal:\n{rebuttal}",
        runtime=review_runtime,
    )

    return (
        f"**Author's Rebuttal:**\n{rebuttal}\n\n"
        f"**Reviewer's Ruling:**\n{ruling}"
    )


# ---------------------------------------------------------------------------
# paper_improvement_loop (writing quality, 2 rounds)
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
        review_runtime:  Runtime for reviewing (reviewer model).
        max_rounds:      Max improvement rounds (default: 2).
        callback:        Progress callback.
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
# review_loop — ARIS-style cross-model review
#
# Each round:
#   1. Read paper
#   2. Review (by difficulty)
#   3. Parse score/verdict/weaknesses
#   4. Debate: author rebuts, reviewer rules (hard/nightmare)
#   5. Log to AUTO_REVIEW.md
#   6. Stop if score >= threshold
#   7. Fix paper
# ---------------------------------------------------------------------------

POSITIVE_THRESHOLD = 6

def review_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    max_rounds: int = 4,
    pass_threshold: int = POSITIVE_THRESHOLD,
    difficulty: str = "medium",
    auto_fix: bool = False,
    callback: Optional[callable] = None,
) -> dict:
    """Cross-model review loop following ARIS design.

    The reviewer (review_runtime, e.g. GPT) and the author (exec_runtime,
    e.g. Claude) are different models.

    Each round: review → parse → debate → log → check stop → (fix if auto_fix).

    Difficulty controls information asymmetry:
        medium:    Author curates content for reviewer (15k tokens).
        hard:      + Reviewer memory across rounds + debate protocol.
        nightmare: Reviewer reads files independently, author has zero control.

    Args:
        paper_dir:       Path to paper/ directory with .tex files.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing (author, e.g. Claude).
        review_runtime:  Runtime for reviewing (reviewer, e.g. GPT).
        max_rounds:      Max review-fix cycles (default: 4).
        pass_threshold:  Min score to pass (default: 6/10).
        difficulty:      "medium" | "hard" | "nightmare".
        auto_fix:        If True, author auto-fixes paper after each round (default: False).
        callback:        Called after review and fix. Return False to break.

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
    reviewer_memory = ""

    venue_criteria = lookup_venue_criteria(venue=venue, runtime=review_runtime)

    for round_num in range(1, max_rounds + 1):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ── 1. Read paper ──
        paper_content = _read_paper(paper_dir)

        # ── 2. Review (new session each round) ──
        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

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
                paper_dir, venue, venue_criteria,
                round_num, max_rounds, reviewer_memory, review_runtime,
            )

        # ── 3. Parse score / verdict / weaknesses ──
        try:
            review = parse_json(reply)
        except ValueError:
            review = {"score": 0, "passed": False, "weaknesses": [], "strengths": []}
        review["round"] = round_num
        review["full_review"] = reply
        review["difficulty"] = difficulty
        review["timestamp"] = ts

        # Accumulate reviewer memory (hard/nightmare)
        if difficulty in ("hard", "nightmare"):
            reviewer_memory += (
                f"\n## Round {round_num} — Score: {review.get('score', 0)}/10\n"
                f"- **Suspicions**: {reply[:500]}\n"
            )

        # ── 4. Debate: author rebuts, reviewer rules (hard/nightmare) ──
        if difficulty in ("hard", "nightmare") and review.get("weaknesses"):
            review["debate_transcript"] = _run_debate(
                review["weaknesses"], paper_content,
                exec_runtime, review_runtime,
            )

        # ── 5. Log to AUTO_REVIEW.md ──
        reviews.append(review)
        _save_review_log(log_path, reviews)

        if callback and callback({"type": "review", **review}) is False:
            break

        # ── 6. Stop if passed ──
        score = review.get("score", 0)
        verdict = str(review.get("verdict", "")).lower()
        passed_by_score = score >= pass_threshold
        passed_by_verdict = (
            ("accept" in verdict and "reject" not in verdict)
            or ("ready" in verdict and "not ready" not in verdict)
        )
        if passed_by_score or passed_by_verdict:
            return {"passed": True, "rounds": round_num,
                    "final_score": score, "reviews": reviews,
                    "difficulty": difficulty}

        # ── 7. Fix paper (only if auto_fix enabled) ──
        if not auto_fix:
            break

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
