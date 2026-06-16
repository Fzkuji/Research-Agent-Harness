"""Stage: review — cross-model adversarial review following ARIS design.

ARIS design: reviewer (GPT) and author (Claude) are different models.
The reviewer audits the paper, the author rebuts and fixes.
3 difficulty levels control information asymmetry between author and reviewer.

Reference: https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
"""

# Adapted from academic-research-skills v3.12.0 (https://github.com/Imbad0202/academic-research-skills), (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: the ARS devil's-advocate concession threshold, score-trajectory
# regression flags, and re-review commitment ledger (markdown protocols) are
# reimplemented here as deterministic Python helpers + agentic-function
# prompts wired into review_loop.

from research_harness.stages.review.adaptive_summarize_priors import adaptive_summarize_priors
from research_harness.stages.review.build_revision_plan import build_revision_plan
from research_harness.stages.review.calibrate_score import calibrate_score
from research_harness.stages.review.detect_ai_flavor import detect_ai_flavor
from research_harness.stages.review.docx_to_markdown import docx_to_markdown
from research_harness.stages.review.fetch_external_review import fetch_external_review
from research_harness.stages.review.filter_relevant_priors import filter_relevant_priors
from research_harness.stages.review.fix_paper import fix_paper
from research_harness.stages.review.generate_multi_specificity_queries import generate_multi_specificity_queries
from research_harness.stages.review.load_paper import load_paper
from research_harness.stages.review.lookup_venue_criteria import lookup_venue_criteria
from research_harness.stages.review.pdf_to_markdown import pdf_to_markdown
from research_harness.stages.review.review_paper import review_paper
from research_harness.stages.review.review_paper_grounded import review_paper_grounded
from research_harness.stages.external.gptzero_browser import check_ai_score_gptzero

import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime
from research_harness.utils import parse_json, parse_review_or_extract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_paper(paper_dir: str, runtime: Optional[Runtime] = None) -> str:
    """Read paper content from any supported source.

    Thin wrapper over `load_paper` retained for backward compatibility with
    existing call sites. `paper_dir` can be:
      - a directory containing .tex / .md / .pdf / .docx
      - a single .pdf / .docx / .md / .tex / .txt / .html file
    """
    return load_paper(paper_dir, runtime)


def _infer_project_dir(paper_dir: str) -> str:
    """Decide where auto_review/ and auto_improvement/ should be written.

    Rules:
      - File path (e.g. /proj/manuscript.pdf):
          → project_dir = dirname (= /proj)
      - Legacy LaTeX layout (paper_dir is a directory containing .tex files,
        typically /proj/paper):
          → project_dir = parent (= /proj)
      - Otherwise (paper_dir is a directory containing .pdf/.docx/.md without
        .tex, i.e. paper_dir IS the project root):
          → project_dir = paper_dir itself
    """
    paper_dir = paper_dir.rstrip("/")
    if os.path.isfile(paper_dir):
        return os.path.dirname(paper_dir)
    if os.path.isdir(paper_dir):
        files = [f for f in os.listdir(paper_dir) if not f.startswith(".")]
        if any(f.endswith(".tex") for f in files):
            return os.path.dirname(paper_dir)
        return paper_dir
    # Path doesn't exist yet — fall back to the legacy interpretation.
    return os.path.dirname(paper_dir)


def _save(directory: str, filename: str, content: str):
    """Save raw content to file."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)


def _gptzero_sample(paper_content: str, *, max_chars: int = 4500) -> str:
    """Pull a representative slice of the paper for GPTZero scoring.

    GPTZero's free UI silently rejects > ~5k chars and times out on long bodies;
    abstract + intro is also where authors over-polish, so it's the most
    informative slice anyway. Heuristic: abstract + first ~3500 chars of intro.
    """
    text = paper_content.strip()
    if len(text) <= max_chars:
        return text

    # Try to lift abstract block.
    lower = text.lower()
    abs_start = lower.find("abstract")
    abs_end = -1
    if abs_start >= 0:
        # Stop at "1 introduction" / "1. introduction" / "## introduction".
        for marker in ("introduction", "## 1", "# 1 ", "\n1 ", "\n1. "):
            cand = lower.find(marker, abs_start + 8)
            if cand > 0:
                abs_end = cand
                break
    abstract = text[abs_start:abs_end] if 0 < abs_end - abs_start < 2500 else ""

    intro_start = abs_end if abs_end > 0 else 0
    intro_budget = max_chars - len(abstract)
    intro = text[intro_start:intro_start + intro_budget]
    return (abstract + "\n\n" + intro).strip()


# ---------------------------------------------------------------------------
# Review by difficulty (Step 2 of review_loop)
#
# Difficulty = who controls information:
#   medium:    author curates content for reviewer
#   hard:      author curates content, but reviewer has memory + debate
#   nightmare: reviewer reads files independently, author has zero control
# ---------------------------------------------------------------------------

DEFAULT_PERSONAS = ("empiricist", "theorist", "novelty_hawk", "devils_advocate")


def _call_review(paper_content: str, venue: str, venue_criteria: str,
                 prior_work_context: str, persona: str,
                 runtime: Runtime) -> str:
    """Dispatch to grounded or vanilla review based on prior_work_context.

    `persona` is only honored by review_paper_grounded. Vanilla review_paper
    (no grounding) ignores it; the persona-injection path requires the
    grounded prompt template.
    """
    if prior_work_context.strip():
        return review_paper_grounded(
            paper_content=paper_content,
            venue=venue,
            venue_criteria=venue_criteria,
            prior_work_context=prior_work_context,
            persona=persona or "balanced",
            runtime=runtime,
        )
    return review_paper(
        paper_content=paper_content,
        venue=venue,
        venue_criteria=venue_criteria,
        runtime=runtime,
    )


def _review_medium(paper_content: str, venue: str, venue_criteria: str,
                   round_num: int, max_rounds: int,
                   review_runtime: Runtime,
                   prior_work_context: str = "",
                   persona: str = "") -> str:
    """Medium: reviewer sees author-curated full content."""
    return _call_review(
        paper_content=(
            f"[Round {round_num}/{max_rounds} of autonomous review loop]\n\n"
            f"{paper_content}"
        ),
        venue=venue,
        venue_criteria=venue_criteria,
        prior_work_context=prior_work_context,
        persona=persona,
        runtime=review_runtime,
    )


def _review_hard(paper_content: str, venue: str, venue_criteria: str,
                 round_num: int, max_rounds: int,
                 reviewer_memory: str,
                 review_runtime: Runtime,
                 prior_work_context: str = "",
                 persona: str = "") -> str:
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

    return _call_review(
        paper_content=(
            f"[Round {round_num}/{max_rounds} of autonomous review loop]\n"
            f"{memory_block}"
            f"{paper_content}\n\n"
            "After your review, include a **Memory update** section listing "
            "any new suspicions, unresolved concerns, or patterns to track."
        ),
        venue=venue,
        venue_criteria=venue_criteria,
        prior_work_context=prior_work_context,
        persona=persona,
        runtime=review_runtime,
    )


def _review_nightmare(paper_dir: str, venue: str, venue_criteria: str,
                      round_num: int, max_rounds: int,
                      reviewer_memory: str,
                      review_runtime: Runtime,
                      prior_work_context: str = "",
                      persona: str = "") -> str:
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
        return _call_review(
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
            prior_work_context=prior_work_context,
            persona=persona,
            runtime=review_runtime,
        )
    else:
        paper_content = _read_paper(paper_dir, review_runtime)
        return _call_review(
            paper_content=(
                f"[Round {round_num}/{max_rounds} — NIGHTMARE MODE]\n"
                f"(API mode: no file access, full content below.)\n"
                f"{memory_block}"
                f"{paper_content}\n\n"
                f"{adversarial_instructions}"
            ),
            venue=venue,
            venue_criteria=venue_criteria,
            prior_work_context=prior_work_context,
            persona=persona,
            runtime=review_runtime,
        )


# ---------------------------------------------------------------------------
# Debate protocol (Step 4 of review_loop, hard + nightmare only)
#
# Concession threshold (ARS devil's-advocate "Attack Intensity Preservation"
# protocol): the reviewer scores each author rebuttal 1-5 and may only
# withdraw a weakness at 5, downgrade at 4. After any concession, the bar
# for further concessions in the same debate rises to 5-only. The rulings
# are parsed and APPLIED — withdrawn weaknesses are dropped and the score
# is adjusted before the stop-condition check.
# ---------------------------------------------------------------------------

def _parse_debate_rulings(ruling_text: str) -> list[dict]:
    """Parse the JSON rulings block from the reviewer's ruling reply.

    Returns [] when no parseable rulings are found (the debate then has
    no effect on the review — every weakness implicitly SUSTAINED).
    """
    try:
        obj = parse_json(ruling_text)
    except ValueError:
        return []
    rulings = obj.get("rulings", [])
    if not isinstance(rulings, list):
        return []
    out = []
    for r in rulings:
        if not isinstance(r, dict):
            continue
        try:
            idx = int(r.get("weakness_index"))
        except (TypeError, ValueError):
            continue
        try:
            score = int(r.get("rebuttal_score", 1))
        except (TypeError, ValueError):
            score = 1
        out.append({
            "weakness_index": idx,
            "rebuttal_score": max(1, min(5, score)),
            "action": str(r.get("action", "")).strip().upper(),
            "reason": str(r.get("reason", "")),
        })
    return out


def _enforce_concession_policy(rulings: list[dict]) -> list[dict]:
    """Deterministically enforce the concession threshold over LLM rulings.

    - WITHDRAWN requires rebuttal_score == 5.
    - DOWNGRADED requires rebuttal_score >= 4.
    - After ANY concession (withdraw or downgrade), the bar for further
      concessions rises to 5-only: a score-4 concession then becomes
      SUSTAINED ("no consecutive concessions" rule).
    - The policy only demotes concessions the score does not support; it
      never escalates a SUSTAINED ruling into a concession.
    """
    conceded = False
    out = []
    for r in rulings:
        score = r["rebuttal_score"]
        intended = r["action"]
        if intended == "WITHDRAWN" and score >= 5:
            action = "WITHDRAWN"
        elif intended in ("WITHDRAWN", "DOWNGRADED") and (
            score >= 5 or (score == 4 and not conceded)
        ):
            action = "DOWNGRADED"
        else:
            action = "SUSTAINED"
        if action in ("WITHDRAWN", "DOWNGRADED"):
            conceded = True
        out.append({
            **r,
            "action": action,
            "intended_action": intended,
            "enforced": action != intended,
        })
    return out


def _apply_debate_rulings(review: dict, rulings: list[dict],
                          scale_max: float = 10.0) -> dict:
    """Apply enforced debate rulings to a parsed review IN PLACE.

    - WITHDRAWN weaknesses are dropped from review["weaknesses"].
    - DOWNGRADED weaknesses are annotated (kept, lower severity).
    - Score adjustment (documented heuristic): when k of the n recorded
      weaknesses are withdrawn, the score moves proportionally toward the
      venue scale max:  new = old + (scale_max - old) * (k / n).
      Rationale: withdrawing every weakness removes the entire negative
      case, so the score should approach the ceiling; withdrawing a
      fraction closes that fraction of the gap. Downgrades do not move
      the score. The pre-debate score is preserved as
      review["pre_debate_score"].

    Returns a summary dict (also useful for logging).
    """
    weaknesses = list(review.get("weaknesses") or [])
    n = len(weaknesses)
    summary = {"n_weaknesses": n, "withdrawn": 0, "downgraded": 0,
               "sustained": 0, "pre_debate_score": review.get("score"),
               "adjusted_score": review.get("score")}
    if not n or not rulings:
        return summary

    withdrawn_idx, downgraded_idx = set(), set()
    for r in rulings:
        i = r["weakness_index"] - 1  # 1-based in the debate prompt
        if not (0 <= i < n):
            continue
        if r["action"] == "WITHDRAWN":
            withdrawn_idx.add(i)
        elif r["action"] == "DOWNGRADED":
            downgraded_idx.add(i)
    downgraded_idx -= withdrawn_idx

    new_weaknesses = []
    for i, w in enumerate(weaknesses):
        if i in withdrawn_idx:
            continue
        if i in downgraded_idx:
            w = f"[severity downgraded after rebuttal] {w}"
        new_weaknesses.append(w)
    review["weaknesses"] = new_weaknesses

    k = len(withdrawn_idx)
    summary["withdrawn"] = k
    summary["downgraded"] = len(downgraded_idx)
    summary["sustained"] = sum(1 for r in rulings
                               if r["action"] == "SUSTAINED")
    if k:
        old = review.get("score") or 0
        if isinstance(old, (int, float)):
            new = round(old + max(scale_max - old, 0) * (k / n), 2)
            review["pre_debate_score"] = old
            review["score"] = new
            summary["adjusted_score"] = new
    return summary


def _run_debate(weaknesses: list, paper_content: str,
                exec_runtime: Runtime, review_runtime: Runtime,
                return_rulings: bool = False):
    """Author (Claude) rebuts weaknesses, reviewer (GPT) rules on each.

    The reviewer scores each rebuttal 1-5 under the concession-threshold
    protocol (withdraw only at 5, downgrade at 4, otherwise SUSTAINED).
    With return_rulings=True, returns
    {"transcript": str, "rulings": [enforced ruling dicts]} so the caller
    can apply the rulings; default returns the transcript string
    (backward compatible).
    """

    @agentic_function(render_range={"callers": 0})
    def _generate_rebuttal(weaknesses_text: str, paper_context: str,
                           runtime: Runtime) -> str:
        """Write a structured rebuttal (from the author's perspective) to the
        weaknesses the reviewer identified. For each (up to 3):

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

    @agentic_function(render_range={"callers": 0})
    def _rule_on_rebuttal(rebuttal_text: str, runtime: Runtime) -> str:
        """Rule on the author's rebuttals (from the reviewer's perspective),
        under a strict concession-threshold protocol.

        For each rebuttal, first score it 1-5:
        - 5 = decisive NEW evidence or logic that directly dismantles the weakness
        - 4 = substantially weakens the weakness, but the core partially stands
        - 3 = partially addresses, core of the weakness intact
        - 2 = tangential or changes the subject
        - 1 = assertion without evidence

        Then derive the action:
        - WITHDRAWN: ONLY at score 5
        - DOWNGRADED: severity downgraded one level, ONLY at score 4
        - SUSTAINED: any score 3 or below — the weakness stands

        Anti-sycophancy rules:
        - Author persistence is not evidence; pressure does not raise the score.
        - No consecutive concessions: after ANY concession (WITHDRAWN or
          DOWNGRADED) in this debate, the bar for every further concession
          rises to 5-only — a score-4 rebuttal then yields SUSTAINED.
        - Do not soften the wording of sustained weaknesses.

        Write a brief prose ruling per rebuttal, then end your reply with
        ONLY this JSON object (no fence commentary after it):
        {"rulings": [{"weakness_index": <1-based index from the numbered
        weakness list>, "rebuttal_score": <1-5>, "action":
        "WITHDRAWN" | "DOWNGRADED" | "SUSTAINED", "reason": "<one line>"}]}
        """
        return runtime.exec(content=[
            {"type": "text", "text": rebuttal_text},
        ])

    weaknesses_text = "\n".join(f"{i}. {w}"
                                for i, w in enumerate(weaknesses[:5], 1))

    rebuttal = _generate_rebuttal(
        weaknesses_text=weaknesses_text,
        paper_context=paper_content[:5000],
        runtime=exec_runtime,
    )

    ruling = _rule_on_rebuttal(
        rebuttal_text=(
            f"Numbered weaknesses under debate:\n{weaknesses_text}\n\n"
            f"Author's rebuttal:\n{rebuttal}"
        ),
        runtime=review_runtime,
    )

    transcript = (
        f"**Author's Rebuttal:**\n{rebuttal}\n\n"
        f"**Reviewer's Ruling:**\n{ruling}"
    )
    if not return_rulings:
        return transcript
    rulings = _enforce_concession_policy(_parse_debate_rulings(ruling))
    return {"transcript": transcript, "rulings": rulings}


# ---------------------------------------------------------------------------
# Score trajectory (ARS score_trajectory_protocol): per-dimension deltas
# between consecutive rounds, with regression flags so the author model
# learns what its previous fix damaged.
# ---------------------------------------------------------------------------

def _score_trajectory(reviews: list, scale_range=None):
    """Deterministic per-dimension score deltas between the last two rounds.

    Args:
        reviews:     List of parsed review dicts (each with "sub_scores",
                     "score", "round"). Only the last two entries are compared.
        scale_range: Optional (lo, hi) venue scale. Regression threshold is
                     venue-scale-agnostic: a drop >= 25% of the scale range
                     when the range is known, else an absolute drop >= 2.

    Returns:
        None when fewer than 2 reviews, else
        {"round_prev", "round_now", "threshold", "rows": [{"dimension",
         "prev", "now", "delta", "flag"}], "regressions": [dims]}.
        Flags: REGRESSION (drop >= threshold), warn (any smaller drop),
        improved, stable, n/a (dimension missing in one round).
    """
    if len(reviews) < 2:
        return None
    prev, now = reviews[-2], reviews[-1]
    if (scale_range and len(scale_range) == 2
            and scale_range[1] > scale_range[0]):
        threshold = 0.25 * (float(scale_range[1]) - float(scale_range[0]))
    else:
        threshold = 2.0

    prev_subs = prev.get("sub_scores") or {}
    now_subs = now.get("sub_scores") or {}
    dims = list(dict.fromkeys(list(prev_subs) + list(now_subs)))
    pairs = [(d, prev_subs.get(d), now_subs.get(d)) for d in dims]
    pairs.append(("overall", prev.get("score"), now.get("score")))

    rows, regressions = [], []
    for dim, p, n in pairs:
        if isinstance(p, (int, float)) and isinstance(n, (int, float)):
            delta = round(n - p, 2)
            if delta <= -threshold:
                flag = "REGRESSION"
                regressions.append(dim)
            elif delta < 0:
                flag = "warn"
            elif delta > 0:
                flag = "improved"
            else:
                flag = "stable"
        else:
            delta, flag = None, "n/a"
        rows.append({"dimension": dim, "prev": p, "now": n,
                     "delta": delta, "flag": flag})
    return {
        "round_prev": prev.get("round"),
        "round_now": now.get("round"),
        "threshold": threshold,
        "rows": rows,
        "regressions": regressions,
    }


def _trajectory_table(traj: dict) -> str:
    """Render a trajectory dict as a '## Score trajectory' markdown section."""
    lines = [
        f"## Score trajectory (round {traj.get('round_prev', '?')} → "
        f"{traj.get('round_now', '?')})",
        "",
        "| Dimension | Prev | Now | Delta | Flag |",
        "|---|---|---|---|---|",
    ]
    for row in traj.get("rows", []):
        delta = row.get("delta")
        delta_s = f"{delta:+g}" if isinstance(delta, (int, float)) else "—"
        prev = row.get("prev") if row.get("prev") is not None else "—"
        now = row.get("now") if row.get("now") is not None else "—"
        lines.append(f"| {row.get('dimension', '?')} | {prev} | {now} "
                     f"| {delta_s} | {row.get('flag', '')} |")
    if traj.get("regressions"):
        lines.append("")
        lines.append(
            f"**REGRESSION detected** (drop >= {traj.get('threshold', 2):g}): "
            f"{', '.join(traj['regressions'])}"
        )
    return "\n".join(lines) + "\n"


def _regression_warning(traj: dict) -> str:
    """Explicit warning for the next fix prompt about damaged dimensions."""
    if not traj or not traj.get("regressions"):
        return ""
    details = []
    for row in traj.get("rows", []):
        if row.get("dimension") in traj["regressions"]:
            details.append(
                f"- **{row['dimension']}**: {row.get('prev')} → "
                f"{row.get('now')} (delta {row.get('delta'):+g})"
            )
    return (
        "\n\n## REGRESSION WARNING (score trajectory)\n\n"
        "The previous revision DAMAGED these dimensions:\n"
        + "\n".join(details) + "\n\n"
        "While executing this plan you MUST restore quality in the damaged "
        "dimensions and avoid repeating the kind of edits that caused these "
        "drops.\n"
    )


# ---------------------------------------------------------------------------
# Commitment ledger (ARS re_review_mode_protocol, "Commitment Ledger
# Verification"): revision-plan action items persist as structured
# commitments; the next round's reviewer audits each one
# (FULLY_ADDRESSED / PARTIALLY_ADDRESSED / NOT_ADDRESSED / MADE_WORSE)
# and unaddressed items are carried forward verbatim so they cannot
# silently drop.
# ---------------------------------------------------------------------------

_AUDIT_STATUSES = ("FULLY_ADDRESSED", "PARTIALLY_ADDRESSED",
                   "NOT_ADDRESSED", "MADE_WORSE")
# UNVERIFIED (audit reply unparseable / commitment missing from the reply)
# is also carried forward: an unverified commitment must not silently drop.
_CARRY_STATUSES = ("NOT_ADDRESSED", "MADE_WORSE", "UNVERIFIED")
_COMMITMENT_FEED_CAP = 15

_PLAN_ACTION_RE = re.compile(
    r"^###\s*\[([A-Za-z]+-\d+)\]\s*(.+?)\s*$", re.MULTILINE)
_PLAN_FIX_ACTION_RE = re.compile(
    r"^-\s*\*\*Fix action\*\*:\s*(.*)$", re.MULTILINE)
_PLAN_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(.{10,})$", re.MULTILINE)


def _parse_plan_commitments(plan_text: str) -> list[dict]:
    """Deterministically parse revision-plan action items into commitments.

    Primary format: the `### [CRITICAL-1] Title` blocks rendered by
    build_revision_plan (fix action lifted from the `- **Fix action**:`
    line). Fallback for free-form plans: markdown numbered items
    (>= 10 chars, bare action-id lines from the Sequencing list skipped).
    """
    commitments = []
    headers = list(_PLAN_ACTION_RE.finditer(plan_text))
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(plan_text)
        block = plan_text[m.end():end]
        next_sec = re.search(r"^##\s", block, re.MULTILINE)
        if next_sec:
            block = block[:next_sec.start()]
        fix_m = _PLAN_FIX_ACTION_RE.search(block)
        cid = m.group(1).upper()
        commitments.append({
            "id": cid,
            "title": m.group(2).strip(),
            "fix_action": fix_m.group(1).strip() if fix_m else "",
            "severity": cid.split("-")[0].lower(),
        })
    if commitments:
        return commitments

    for n, m in enumerate(_PLAN_NUMBERED_RE.finditer(plan_text), 1):
        text = m.group(1).strip()
        if re.fullmatch(r"[A-Za-z]+-\d+\.?", text):
            continue  # Sequencing list entries are bare action ids
        commitments.append({
            "id": f"ITEM-{n}",
            "title": text,
            "fix_action": text,
            "severity": "unknown",
        })
    return commitments


@agentic_function(render_range={"callers": 0})
def _classify_commitments(commitments_json: str, paper_content: str,
                          runtime: Runtime) -> str:
    """Audit prior-round revision commitments against the CURRENT paper
    (R&R traceability). For EACH commitment in the JSON list, independently
    verify whether the promised fix is actually present in the paper text.
    The author's claim is not evidence — navigate to where the change
    should be and check.

    Classify each commitment as exactly one of:
    - FULLY_ADDRESSED:     the promised change is present and substantively
                           resolves the issue
    - PARTIALLY_ADDRESSED: some change is present but the core issue remains
    - NOT_ADDRESSED:       no corresponding change found in the paper
    - MADE_WORSE:          the revision degraded this aspect of the paper

    Reply with ONLY a JSON object, no other text:
    {"audit": [{"id": "<commitment id>", "status": "<one of the four>",
                "evidence": "<one line: where in the paper you checked>"}]}
    Every commitment id from the input MUST appear exactly once in "audit".
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Commitments from the previous revision round:\n"
            f"{commitments_json}\n\n"
            f"Current paper:\n{paper_content}"
        )},
    ])


def _audit_commitments(commitments: list[dict], paper_content: str,
                       review_runtime: Runtime) -> list[dict]:
    """Audit commitments against the current paper (one reviewer exec).

    Feeds at most the _COMMITMENT_FEED_CAP most recent commitments. The
    reply is JSON-parsed robustly; commitments missing from the reply (or
    an unparseable reply) are marked UNVERIFIED so they carry forward.

    Returns [{"id", "round", "title", "status", "evidence"}, ...] aligned
    with the fed commitments.
    """
    feed = commitments[-_COMMITMENT_FEED_CAP:]
    if not feed:
        return []
    feed_json = json.dumps(
        [{"id": c.get("id"), "round": c.get("round"),
          "title": c.get("title"), "fix_action": c.get("fix_action")}
         for c in feed],
        ensure_ascii=False, indent=1,
    )
    if hasattr(review_runtime, "reset"):
        review_runtime.reset()
    reply = _classify_commitments(
        commitments_json=feed_json,
        paper_content=paper_content[:12000],
        runtime=review_runtime,
    )

    by_id = {}
    try:
        obj = parse_json(reply)
        for entry in obj.get("audit", []):
            if not isinstance(entry, dict):
                continue
            eid = str(entry.get("id", "")).upper()
            status = str(entry.get("status", "")).strip().upper().replace(" ", "_")
            if status not in _AUDIT_STATUSES:
                status = "UNVERIFIED"
            by_id.setdefault(eid, {
                "status": status,
                "evidence": str(entry.get("evidence", "")),
            })
    except ValueError:
        pass

    results = []
    for c in feed:
        cid = str(c.get("id", "")).upper()
        hit = by_id.get(cid, {
            "status": "UNVERIFIED",
            "evidence": "audit reply unparseable or missing this id",
        })
        results.append({
            "id": cid,
            "round": c.get("round"),
            "title": c.get("title", ""),
            "status": hit["status"],
            "evidence": hit["evidence"],
        })
    return results


def _carry_from_audit(audit: list[dict],
                      commitments: list[dict]) -> list[dict]:
    """Select commitments whose audit status requires carrying forward.

    NOT_ADDRESSED / MADE_WORSE (and UNVERIFIED, see _CARRY_STATUSES) items
    are returned with their original title/fix_action so they can be
    appended verbatim to the next revision plan input.
    """
    status_by_id = {a.get("id"): a.get("status") for a in audit
                    if a.get("status") in _CARRY_STATUSES}
    carry = []
    for c in commitments:
        cid = str(c.get("id", "")).upper()
        if cid in status_by_id:
            carry.append({**c, "id": cid, "status": status_by_id[cid]})
    return carry


def _carry_section(carry_items: list[dict]) -> str:
    """Render carried-over commitments as a markdown section (verbatim)."""
    if not carry_items:
        return ""
    lines = [
        "",
        "## Unresolved commitments from previous round "
        "(carried over — MUST be addressed, do not drop)",
        "",
    ]
    for c in carry_items:
        lines.append(
            f"- [{c.get('id', '?')}] ({c.get('status', '?')}) "
            f"{c.get('title', '')} — fix action: {c.get('fix_action', '')}"
        )
    return "\n".join(lines) + "\n"


def _commitment_audit_table(audit: list[dict], round_num) -> str:
    """Render a commitment audit as a markdown summary table."""
    lines = [
        f"## Commitment audit (round {round_num})",
        "",
        "| ID | Commitment | Status |",
        "|---|---|---|",
    ]
    for a in audit:
        title = str(a.get("title", "")).replace("|", "\\|")[:100]
        lines.append(f"| {a.get('id', '?')} | {title} | {a.get('status', '?')} |")
    return "\n".join(lines) + "\n"


def _append_auto_review(base_dir: str, text: str):
    """Append a section to AUTO_REVIEW.md (created if missing)."""
    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, "AUTO_REVIEW.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n\n")


# ---------------------------------------------------------------------------
# build_prior_work_context — orchestrator: paper → grounded prior-work bundle
#
# Three-stage grounded retrieval (Stanford Agentic Reviewer style):
#   1. generate_multi_specificity_queries  (LLM, 1 call)
#   2. _retrieve_arxiv_for_queries          (pure Python urllib, 0 LLM calls)
#   3. filter_relevant_priors               (LLM, 1 call)
#   4. adaptive_summarize_priors            (LLM, 1 call — but it may itself
#                                            invoke shell to fetch fulltext)
#
# Output is a markdown blob suitable for review_paper_grounded's
# `prior_work_context` argument.
# ---------------------------------------------------------------------------

# Public arxiv API rate limit: be polite (1 req / sec)
_ARXIV_API_BASE = "http://export.arxiv.org/api/query"
_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom",
             "arxiv": "http://arxiv.org/schemas/atom"}


def _retrieve_arxiv_for_queries(queries: dict, max_per_query: int = 5,
                                rate_limit_sec: float = 1.0) -> list[dict]:
    """Pure Python retrieval over arXiv API. No LLM calls.

    Args:
        queries:        {"benchmark": [...], "same_problem": [...], "same_technique": [...]}
                        from generate_multi_specificity_queries.
        max_per_query:  Max papers per individual query (default 5).
        rate_limit_sec: Sleep between consecutive requests.

    Returns:
        Deduplicated list of dicts:
        [{"id": "arXiv:xxxx", "title": ..., "authors": [...], "year": ...,
          "abstract": ..., "query_categories": ["benchmark", "same_problem"]}]
    """
    results: dict[str, dict] = {}  # arxiv_id -> dict

    for category, q_list in queries.items():
        for q in q_list:
            url = f"{_ARXIV_API_BASE}?" + urllib.parse.urlencode({
                "search_query": q,
                "start": 0,
                "max_results": max_per_query,
                "sortBy": "relevance",
                "sortOrder": "descending",
            })
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "research-harness-review/1.0"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = resp.read()
            except Exception:
                continue

            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue

            for entry in root.findall("atom:entry", _ARXIV_NS):
                arxiv_url = entry.findtext("atom:id", "", _ARXIV_NS)
                arxiv_id = arxiv_url.rsplit("/", 1)[-1]
                if not arxiv_id:
                    continue
                if arxiv_id in results:
                    if category not in results[arxiv_id]["query_categories"]:
                        results[arxiv_id]["query_categories"].append(category)
                    continue

                title = (entry.findtext("atom:title", "", _ARXIV_NS)
                         or "").strip().replace("\n", " ")
                summary = (entry.findtext("atom:summary", "", _ARXIV_NS)
                           or "").strip().replace("\n", " ")
                published = entry.findtext("atom:published", "", _ARXIV_NS)
                year = published[:4] if published else ""
                authors = [a.findtext("atom:name", "", _ARXIV_NS)
                           for a in entry.findall("atom:author", _ARXIV_NS)]

                results[arxiv_id] = {
                    "id": f"arXiv:{arxiv_id}",
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "abstract": summary,
                    "query_categories": [category],
                }

            time.sleep(rate_limit_sec)

    return list(results.values())


def build_prior_work_context(
    paper_content: str,
    exec_runtime: Runtime,
    review_runtime: Optional[Runtime] = None,
    *,
    top_k: int = 8,
    max_per_query: int = 5,
    max_total_tokens: int = 8000,
    save_to: Optional[str] = None,
    debug_dir: Optional[str] = None,
) -> dict:
    """Build a grounded prior-work context bundle for a paper.

    Args:
        paper_content:    The paper text under review.
        exec_runtime:     Runtime for adaptive_summarize_priors (may invoke
                          shell to fetch fulltext PDFs).
        review_runtime:   Runtime for query generation + filtering (uses
                          reviewer model so the relevance judgments match
                          the reviewer's calibration). Defaults to exec_runtime.
        top_k:            How many priors to surface (default 8).
        max_per_query:    arXiv results per query (default 5).
        max_total_tokens: Token budget for the final markdown bundle (default 8000).
        save_to:          Optional file path to persist the markdown bundle.

    Returns:
        {
          "queries": {"benchmark": [...], "same_problem": [...], "same_technique": [...]},
          "candidates_count": <int>,
          "selected_count": <int>,
          "prior_work_context": "<markdown blob>",
          "saved_to": <path or None>,
        }
    """
    if review_runtime is None:
        review_runtime = exec_runtime

    # ── 1. Generate queries (LLM) ──
    if hasattr(review_runtime, 'reset'):
        review_runtime.reset()
    queries_raw = generate_multi_specificity_queries(
        paper_content=paper_content,
        runtime=review_runtime,
    )
    if debug_dir:
        try:
            with open(os.path.join(debug_dir, "_grounding_queries_raw.md"), "w", encoding="utf-8") as f:
                f.write(queries_raw)
        except OSError:
            pass
    try:
        queries_obj = parse_json(queries_raw)
        queries = queries_obj.get("queries", {})
        # Some models return {"benchmark": [...], ...} at top level, no wrapper.
        if not queries and any(k in queries_obj for k in
                                ("benchmark", "same_problem", "same_technique")):
            queries = {k: queries_obj[k] for k in queries_obj
                       if k in ("benchmark", "same_problem", "same_technique")}
    except ValueError:
        queries = {"benchmark": [], "same_problem": [], "same_technique": []}

    # Sanity check; if completely empty (e.g. parse failed), bail with empty context.
    total_queries = sum(len(v) for v in queries.values())
    if total_queries == 0:
        return {
            "queries": queries,
            "candidates_count": 0,
            "selected_count": 0,
            "prior_work_context": "",
            "saved_to": None,
        }

    # ── 2. Retrieve from arXiv (pure Python) ──
    candidates = _retrieve_arxiv_for_queries(
        queries, max_per_query=max_per_query,
    )
    candidates_json = json.dumps(candidates, ensure_ascii=False)

    if not candidates:
        return {
            "queries": queries,
            "candidates_count": 0,
            "selected_count": 0,
            "prior_work_context": "",
            "saved_to": None,
        }

    # ── 3. Filter to top_k by relevance (LLM) ──
    if hasattr(review_runtime, 'reset'):
        review_runtime.reset()
    selected_raw = filter_relevant_priors(
        paper_content=paper_content,
        candidates_json=candidates_json,
        top_k=top_k,
        runtime=review_runtime,
    )
    if debug_dir:
        try:
            with open(os.path.join(debug_dir, "_grounding_filter_raw.md"), "w", encoding="utf-8") as f:
                f.write(selected_raw)
        except OSError:
            pass
    try:
        selected_obj = parse_json(selected_raw)
        selected = selected_obj.get("selected", [])
    except ValueError:
        selected = []

    if not selected:
        return {
            "queries": queries,
            "candidates_count": len(candidates),
            "selected_count": 0,
            "prior_work_context": "",
            "saved_to": None,
        }

    # ── 4. Adaptive summarize (LLM, may use shell for fulltext fetch) ──
    if hasattr(exec_runtime, 'reset'):
        exec_runtime.reset()
    selected_json = json.dumps({"selected": selected}, ensure_ascii=False)
    summarize_reply = adaptive_summarize_priors(
        paper_content=paper_content,
        selected_json=selected_json,
        max_total_tokens=max_total_tokens,
        runtime=exec_runtime,
    )

    # adaptive_summarize_priors returns "Saved to <path>. ..." after persisting
    # the markdown to a file. Parse out the path and read the actual context.
    prior_work_context = ""
    extracted_path = None
    if "Saved to " in summarize_reply:
        try:
            extracted_path = summarize_reply.split("Saved to ", 1)[1].split(".", 1)[0] + ".md"
            extracted_path = extracted_path.strip()
            if os.path.exists(extracted_path):
                with open(extracted_path, "r", encoding="utf-8") as f:
                    prior_work_context = f.read()
        except (IndexError, OSError):
            pass

    # Fallback: if we couldn't recover the file, use the reply text itself.
    if not prior_work_context:
        prior_work_context = summarize_reply

    # Optional explicit save
    if save_to:
        os.makedirs(os.path.dirname(os.path.expanduser(save_to)), exist_ok=True)
        with open(os.path.expanduser(save_to), "w", encoding="utf-8") as f:
            f.write(prior_work_context)

    return {
        "queries": queries,
        "candidates_count": len(candidates),
        "selected_count": len(selected),
        "prior_work_context": prior_work_context,
        "saved_to": save_to or extracted_path,
    }


# ---------------------------------------------------------------------------
# apply_revision_plan — orchestrator: paper + plan → revised paper on disk
#
# This is the dedicated "fix" entry point, decoupled from review_loop.
# Can be called:
#   (a) automatically by review_loop / paper_improvement_loop (auto_fix=True)
#   (b) manually by user, after reviewing the revision_plan.md file
#
# Output layout:
#   output_dir/  ← contains the revised paper, mirroring source layout
#                  (multi-.tex preserved, single .md preserved, etc.)
#   output_dir/REVISION_LOG.md  ← change log + diff hints
# ---------------------------------------------------------------------------

def apply_revision_plan(
    paper_dir: str,
    plan_path: str,
    output_dir: str,
    exec_runtime: Runtime,
    round_num: int = 1,
) -> str:
    """Apply a revision plan to a paper, writing the revised version to disk.

    Args:
        paper_dir:    Source paper (any format supported by load_paper).
        plan_path:    Path to revision_plan.md produced by build_revision_plan.
        output_dir:   Where to write the revised paper. Created if missing.
        exec_runtime: Runtime for the fix_paper LLM call (author model).
        round_num:    Round number (for tracing in REVISION_LOG.md).

    Returns:
        Path to the revised paper. For multi-.tex inputs, returns output_dir
        (a directory of .tex files). For single-file inputs, returns the path
        to the single revised file inside output_dir.
    """
    paper_dir = os.path.expanduser(paper_dir)
    plan_path = os.path.expanduser(plan_path)
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    paper_content = _read_paper(paper_dir, exec_runtime)
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_text = f.read()

    fix_reply = fix_paper(
        paper_content=paper_content,
        review_feedback=plan_text,
        round_num=round_num,
        runtime=exec_runtime,
    )

    # Always save the raw fix output for forensics.
    _save(output_dir, "_fix_raw.md", fix_reply)

    # Strip the trailing JSON change-log block from the body before writing
    # it back as the actual paper. The JSON is preserved separately.
    body, change_log_json = _split_fix_output(fix_reply)

    if change_log_json:
        _save(output_dir, "REVISION_LOG.md",
              f"# Revision Log — Round {round_num}\n\n"
              f"Source paper: `{paper_dir}`\n"
              f"Plan: `{plan_path}`\n\n"
              f"## Change-log JSON\n\n```json\n{change_log_json}\n```\n")

    # Decide how to write the revised paper based on the source layout.
    revised_path = _write_revised_paper(paper_dir, body, output_dir)

    # Copy non-regenerated sibling assets (missing .tex, .bib/.sty/.cls,
    # figure dirs) so the revised tree is self-contained — review_loop and
    # paper_improvement_loop repoint paper_dir at output_dir next round,
    # and an asset-less tree breaks compile and later reviews.
    if os.path.isdir(paper_dir):
        _copy_sibling_assets(paper_dir, output_dir)
    return revised_path


_ASSET_EXTS = (".bib", ".bst", ".sty", ".cls", ".tex")


def _copy_sibling_assets(src_dir: str, output_dir: str) -> list[str]:
    """Copy source files the revision did not regenerate into output_dir.

    Existing files in output_dir are never overwritten."""
    import shutil
    copied = []
    for name in sorted(os.listdir(src_dir)):
        if name.startswith("."):
            continue
        src = os.path.join(src_dir, name)
        dst = os.path.join(output_dir, name)
        if os.path.exists(dst):
            continue
        if os.path.isdir(src):
            shutil.copytree(src, dst)
            copied.append(name + "/")
        elif name.lower().endswith(_ASSET_EXTS):
            shutil.copy2(src, dst)
            copied.append(name)
    return copied


def _split_fix_output(fix_reply: str) -> tuple[str, str]:
    """Separate the paper body from the trailing JSON change-log block.

    fix_paper is instructed to append a ```json {...} ``` change-log after
    the revised paper. This helper splits them so the body alone is written
    back as the .tex / .md, and the JSON is logged separately.
    """
    import re
    # Match the LAST fenced json block in the output.
    matches = list(re.finditer(r"```json\s*\n(.*?)\n```", fix_reply, re.DOTALL))
    if not matches:
        return fix_reply.strip(), ""
    last = matches[-1]
    body = fix_reply[:last.start()].rstrip()
    change_log = last.group(1).strip()
    return body, change_log


def _write_revised_paper(src_paper_dir: str, body: str,
                         output_dir: str) -> str:
    """Write the revised body to output_dir, preserving the source layout.

    Source layouts handled:
      - Directory of .tex files: parse `% === fname ===` markers in body and
        split back into per-file .tex. Markers absent → write all to
        output_dir/manuscript.tex (lossy fallback, with a warning file).
      - Single .pdf / .docx: write to output_dir/<original_stem>.md
      - Single .md / .tex / .txt / .html: write to output_dir/<basename>
      - Directory with single .pdf/.docx/.md: same as the file case
    """
    import re
    src_paper_dir = src_paper_dir.rstrip("/")
    os.makedirs(output_dir, exist_ok=True)

    # Resolve src to a "primary file" or recognize it as a multi-tex dir.
    if os.path.isdir(src_paper_dir):
        files = [f for f in os.listdir(src_paper_dir) if not f.startswith(".")]
        tex_files = sorted(f for f in files if f.endswith(".tex"))
        if tex_files:
            return _write_multi_tex(body, tex_files, output_dir)
        # Single-file directory case: pick the primary file
        primary = _pick_primary_file(src_paper_dir, files)
        if primary:
            return _write_single_file(primary, body, output_dir)
        # Empty dir fallback
        out = os.path.join(output_dir, "manuscript.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(body)
        return output_dir

    if os.path.isfile(src_paper_dir):
        return _write_single_file(src_paper_dir, body, output_dir)

    # Non-existent path; just dump.
    out = os.path.join(output_dir, "manuscript.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(body)
    return output_dir


def _pick_primary_file(directory: str, files: list[str]) -> Optional[str]:
    """Pick the primary paper file in a single-file directory."""
    for ext in ((".tex",), (".md", ".markdown"), (".pdf",),
                (".docx", ".doc"), (".txt", ".rst")):
        matches = [f for f in files if f.endswith(ext)]
        if len(matches) == 1:
            return os.path.join(directory, matches[0])
        if len(matches) > 1:
            # Pick the largest as a heuristic
            sized = [(f, os.path.getsize(os.path.join(directory, f)))
                     for f in matches]
            sized.sort(key=lambda x: x[1], reverse=True)
            return os.path.join(directory, sized[0][0])
    return None


def _write_multi_tex(body: str, original_files: list[str],
                     output_dir: str) -> str:
    """Split a fix_paper body back into per-file .tex using `% === fname ===`
    markers. If markers are missing or incomplete, write everything to a
    fallback file and emit a warning."""
    import re
    pattern = re.compile(r"%\s*===\s*([^\s=]+\.tex)\s*===\s*\n", re.MULTILINE)
    parts = pattern.split(body)
    # parts = [preamble, fname1, content1, fname2, content2, ...]

    if len(parts) >= 3:
        # Got at least one marker. Write each segment.
        written = []
        for i in range(1, len(parts), 2):
            fname = parts[i]
            content = parts[i + 1].strip() + "\n"
            out_path = os.path.join(output_dir, fname)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            written.append(fname)
        missing = set(original_files) - set(written)
        if missing:
            with open(os.path.join(output_dir, "_WARNING.md"), "w", encoding="utf-8") as f:
                f.write(
                    f"# Warning: fix_paper output dropped some source files\n\n"
                    f"Original .tex files: {sorted(original_files)}\n"
                    f"Written by fix_paper: {sorted(written)}\n"
                    f"Missing (NOT regenerated): {sorted(missing)}\n\n"
                    f"You may want to copy the missing files from the source "
                    f"manually if they should remain in the revised paper.\n"
                )
        return output_dir
    else:
        # No markers — fix_paper produced a single concatenated body.
        # Write as one file and warn.
        out_path = os.path.join(output_dir, "manuscript.tex")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(body)
        with open(os.path.join(output_dir, "_WARNING.md"), "w", encoding="utf-8") as f:
            f.write(
                f"# Warning: fix_paper output had no `% === fname ===` markers\n\n"
                f"Original was a multi-.tex layout: {sorted(original_files)}\n"
                f"All revised content was written to a single manuscript.tex.\n"
                f"You may need to manually re-split into per-file structure.\n"
            )
        return output_dir


def _write_single_file(src_path: str, body: str, output_dir: str) -> str:
    """Write the revised body to output_dir, naming the file based on the
    source. PDF/DOCX inputs are written as .md (since fix_paper outputs text)."""
    base = os.path.basename(src_path)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext in (".pdf", ".docx", ".doc"):
        out_name = f"{stem}.md"
    else:
        out_name = base
    out_path = os.path.join(output_dir, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)
    return out_path


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
        paper_dir:       Path to paper. Accepts any of:
                         - directory of .tex files (legacy)
                         - directory containing a single .pdf / .docx / .md
                         - direct path to a .pdf / .docx / .md / .tex / .txt / .html file
                         Conversion of .pdf / .docx is cached as a sibling .md.
        venue:           Target venue.
        exec_runtime:    Runtime for fixing (author model). Also drives PDF/DOCX
                         conversion when paper_dir is a non-text format.
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
    project_dir = _infer_project_dir(paper_dir)
    base_dir = os.path.join(project_dir, "auto_improvement")
    rounds_log = []

    venue_criteria = lookup_venue_criteria(venue=venue, runtime=review_runtime)

    for round_num in range(1, max_rounds + 1):
        round_dir = os.path.join(base_dir, f"round_{round_num}")
        paper_content = _read_paper(paper_dir, exec_runtime)

        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()

        reply = review_paper(
            paper_content=paper_content,
            venue=venue,
            venue_criteria=venue_criteria,
            runtime=review_runtime,
        )
        _save(round_dir, "review.md", reply)

        review = parse_review_or_extract(reply, venue=venue)
        review["round"] = round_num

        # Build revision plan from this single-reviewer report (paper_improvement_loop
        # has 1 reviewer, so individual_reviews == meta_review == reply).
        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()
        revision_plan = build_revision_plan(
            paper_content=paper_content,
            individual_reviews=reply,
            meta_review=reply,
            venue=venue,
            venue_criteria=venue_criteria,
            runtime=review_runtime,
        )
        _save(round_dir, "revision_plan.md", revision_plan)
        review["revision_plan_path"] = os.path.join(round_dir, "revision_plan.md")
        rounds_log.append(review)

        if callback:
            callback({"type": "review", "round": round_num, **review})

        if hasattr(exec_runtime, 'reset'):
            exec_runtime.reset()

        new_paper_dir = apply_revision_plan(
            paper_dir=paper_dir,
            plan_path=review["revision_plan_path"],
            output_dir=os.path.join(round_dir, "paper"),
            round_num=round_num,
            exec_runtime=exec_runtime,
        )

        # compile_paper expects a directory of .tex sources. Compile the
        # newly written revised version (skipped if it isn't .tex layout).
        if os.path.isdir(new_paper_dir) and any(
            f.endswith(".tex") for f in os.listdir(new_paper_dir)
        ):
            compile_paper(paper_dir=new_paper_dir, runtime=exec_runtime)

        # Next round operates on the revised paper.
        paper_dir = new_paper_dir

        if callback:
            callback({"type": "fix_and_compile", "round": round_num,
                      "new_paper_dir": new_paper_dir})

    summary_lines = [
        "# Paper Improvement Summary\n",
        f"- **Paper**: {paper_dir}",
        f"- **Venue**: {venue}",
        f"- **Rounds**: {len(rounds_log)}\n",
    ]
    for r in rounds_log:
        rn = r["round"]
        summary_lines.append(f"## Round {rn}")
        summary_lines.append(f"- Score: {r.get('score', '?')}/10")
        summary_lines.append(f"- Review: `round_{rn}/review.md`")
        summary_lines.append(f"- Fix: `round_{rn}/fix.md`")
        summary_lines.append("")

    summary = "\n".join(summary_lines)
    _save(base_dir, "SUMMARY.md", summary)

    return {"summary": summary, "rounds": rounds_log}


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


# ---------------------------------------------------------------------------
# Multi-reviewer: N independent reviews + Area Chair meta-review
# ---------------------------------------------------------------------------

def _run_single_review(paper_content: str, paper_dir: str,
                       venue: str, venue_criteria: str,
                       round_num: int, max_rounds: int,
                       difficulty: str, reviewer_memory: str,
                       review_runtime: Runtime,
                       prior_work_context: str = "",
                       persona: str = "") -> str:
    """Run one independent review (fresh session).

    If `prior_work_context` is non-empty, dispatches to review_paper_grounded
    (which honors `persona`) instead of vanilla review_paper.
    """
    if hasattr(review_runtime, 'reset'):
        review_runtime.reset()

    if difficulty == "medium":
        return _review_medium(
            paper_content, venue, venue_criteria,
            round_num, max_rounds, review_runtime,
            prior_work_context=prior_work_context,
            persona=persona,
        )
    elif difficulty == "hard":
        return _review_hard(
            paper_content, venue, venue_criteria,
            round_num, max_rounds, reviewer_memory, review_runtime,
            prior_work_context=prior_work_context,
            persona=persona,
        )
    else:
        return _review_nightmare(
            paper_dir, venue, venue_criteria,
            round_num, max_rounds, reviewer_memory, review_runtime,
            prior_work_context=prior_work_context,
            persona=persona,
        )


def _meta_review(individual_reviews: str, venue: str, runtime: Runtime) -> str:
    """Venue-aware Area Chair meta-review using tool-use to force structured output.

    Schema is built dynamically from the venue spec, so:
      - score range matches the venue (ARR 1-5, NeurIPS 1-6, ICLR 0-10, etc.)
      - sub_scores follow the venue's exact dimensions
      - verdict uses the venue's vocabulary

    Avoids the prior failure mode where gpt-5.5 wrote an author-response
    draft instead of a meta-review when given a free-text prompt.
    """
    from research_harness.references.venue_scoring import (
        get_venue_spec, build_meta_review_schema,
    )
    from research_harness.utils import call_with_schema

    spec = get_venue_spec(venue)
    schema = build_meta_review_schema(spec)
    n_reviewers = max(individual_reviews.count("### Reviewer "), 1)

    instructions = (
        f"You are the Area Chair for {spec.name}. {n_reviewers} independent "
        f"reviewers have submitted reports on the same paper. Your job:\n"
        f"  1. Identify consensus points (issues ALL reviewers agree on).\n"
        f"  2. Identify disagreements and adjudicate them.\n"
        f"  3. Produce a consolidated assessment with deduplicated weaknesses "
        f"     and strengths, a final score on the venue's scale, and a "
        f"     one-line verdict using the venue's vocabulary.\n\n"
        f"## Required scoring scale\n"
        f"Use {spec.name}'s exact {spec.overall_dim.scale[0]}-"
        f"{spec.overall_dim.scale[1]} scale. Acceptance threshold is "
        f"{spec.accept_threshold}. The schema enforces valid range — "
        f"out-of-range values will be rejected.\n\n"
        f"You MUST call the submit_meta_review tool. Do NOT write an author "
        f"response. Do NOT summarize the paper. Submit the structured meta-review.\n\n"
        f"=== INDIVIDUAL REVIEWER REPORTS ===\n\n{individual_reviews}"
    )
    result = call_with_schema(
        runtime=runtime,
        instructions=instructions,
        schema_name="submit_meta_review",
        schema_description=(
            f"Submit the Area Chair's consolidated meta-review for {spec.name}: "
            f"final score, verdict, deduplicated weaknesses and strengths."
        ),
        parameters=schema,
    )
    result["venue"] = spec.name
    result["score_scale"] = f"{spec.overall_dim.scale[0]}-{spec.overall_dim.scale[1]}"
    return json.dumps(result, ensure_ascii=False, indent=2)


# Stub kept for backward-compat with anything that imported the old @agentic_function form.
def _meta_review_legacy(individual_reviews: str, venue: str, runtime: Runtime) -> str:
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n\n"
            f"=== INDIVIDUAL REVIEWER REPORTS ===\n\n{individual_reviews}"
        )},
    ])


def review_loop(
    paper_dir: str,
    venue: str = "NeurIPS",
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    num_reviewers: int = 4,
    max_rounds: int = 4,
    pass_threshold: Optional[float] = None,
    difficulty: str = "medium",
    auto_fix: bool = False,
    with_grounding: bool = True,
    grounding_top_k: int = 8,
    personas: Optional[tuple[str, ...]] = None,
    external_providers: tuple[str, ...] = (),
    external_review_urls: Optional[dict] = None,
    external_email: str = "",
    with_gptzero: bool = False,
    gptzero_humanize_threshold: float = 50.0,
    gptzero_cdp_url: str = "http://localhost:9222",
    callback: Optional[callable] = None,
) -> dict:
    """Multi-reviewer review loop with Area Chair meta-review.

    Each round: [grounded retrieval] → N independent reviews →
                 AC meta-review → revision plan → (optional fix).

    Following AI-Scientist / AgentReview design:
    - N reviewers independently review the paper (fresh sessions, same runtime)
    - Area Chair synthesizes all reviews into a meta-review with final score
    - Variation comes from fresh sessions (no shared context between reviewers)

    With grounding (Stanford Agentic Reviewer style, default ON):
    - Before reviewing, retrieve top-k prior works from arXiv across 3 query
      layers (benchmark / same_problem / same_technique) and feed them as
      context to each reviewer. This counters the well-documented LLM bias
      of underweighting novelty.

    Difficulty controls information asymmetry:
        medium:    Author curates content for reviewer.
        hard:      + Reviewer memory across rounds + debate protocol.
        nightmare: Reviewer reads files independently, author has zero control.

    Args:
        paper_dir:        Path to paper. Accepts any of:
                          - directory of .tex files (legacy multi-file concat)
                          - directory containing a single .pdf / .docx / .md
                          - direct path to a .pdf / .docx / .md / .tex / .txt / .html file
                          Conversion of .pdf / .docx is cached as a sibling .md
                          and reused on subsequent rounds.
        venue:            Target venue.
        exec_runtime:     Runtime for fixing (author). Also drives PDF/DOCX
                          conversion and prior-work fulltext fetches.
        review_runtime:   Runtime for reviewing (each reviewer gets a fresh session).
        num_reviewers:    Number of independent reviewers per round (default: 4).
        max_rounds:       Max review-fix cycles (default: 4).
        pass_threshold:   Min score to pass, on the venue's own scale.
                          Default None = the venue's accept threshold.
        difficulty:       "medium" | "hard" | "nightmare".
        auto_fix:         If True, auto-fix paper after each round (default: False).
        with_grounding:   If True, retrieve prior work from arXiv before each
                          round and feed it to reviewers (default: True).
        grounding_top_k:  Number of prior works to surface per round (default: 8).
        personas:         Per-reviewer persona pool (ReviewerToo-style diversity).
                          Default = DEFAULT_PERSONAS = ("empiricist", "theorist",
                          "novelty_hawk", "devils_advocate") — the widest
                          4-lens spread (experiments / theory / prior work /
                          claim-level attack; clarity issues are also caught
                          by paper_improvement_loop). Full pool (see
                          _PERSONA_INSTRUCTIONS in review_paper_grounded):
                          balanced, empiricist, theorist, novelty_hawk,
                          clarity_critic, methodologist, statistician,
                          reproducibility_auditor, devils_advocate.
                          Reviewer i gets personas[i % len(personas)].
                          Persona is only honored when with_grounding=True
                          (review_paper_grounded path). Set to () or None to
                          disable persona injection.
        external_providers:    Tuple of external review services to also query
                          (e.g. ("paperreview_ai",)). Each provider's review
                          is appended to individual_reviews as an extra reviewer
                          and feeds into AC meta-review + revision plan.
                          Default: () (no external providers).
        external_review_urls:  Pre-fetched result URLs keyed by provider name
                          (e.g. {"paperreview_ai": "https://paperreview.ai/review?id=xxx"}).
                          When None or missing for a provider, review_loop emits
                          manual instructions to round_dir/external_<provider>_pending.md
                          and skips that reviewer for the round (non-blocking).
                          Pass URLs in on a re-run after manual submission.
        external_email:   Email to use when registering with external services.
                          Empty string lets the user supply it via memory or
                          ad-hoc prompting.
        with_gptzero:     If True, run a GPTZero AI-detection pass on the
                          paper's abstract+intro slice (~4.5k chars) each
                          round and attach the result to the review dict
                          under "ai_detection". Requires Chrome running with
                          --remote-debugging-port=9222 (or `openprogram
                          browser attach`). Default False — turn on only when
                          a CDP-attached Chrome is available.
        gptzero_humanize_threshold: AI-percent threshold (0-100) above which
                          the round is flagged as recommend_humanize=True.
                          Default 50. The flag is informational; review_loop
                          does NOT auto-rewrite the paper, that is a separate
                          stage the user opts into.
        gptzero_cdp_url:  CDP base URL. Default http://localhost:9222.
        callback:         Called after review and fix. Return False to break.

    Returns:
        dict with: passed, rounds, final_score, reviews, difficulty, num_reviewers,
        with_grounding
    """
    if exec_runtime is None:
        raise ValueError("exec_runtime is required")
    if review_runtime is None:
        review_runtime = exec_runtime
    if difficulty not in ("medium", "hard", "nightmare"):
        raise ValueError(f"Invalid difficulty: {difficulty}")

    if personas is None:
        personas = DEFAULT_PERSONAS

    paper_dir = os.path.expanduser(paper_dir)
    project_dir = _infer_project_dir(paper_dir)
    reviews = []
    reviewer_memory = ""
    commitment_ledger: list[dict] = []  # accumulated revision-plan commitments

    venue_criteria = lookup_venue_criteria(venue=venue, runtime=review_runtime)
    from research_harness.references.venue_scoring import get_venue_spec
    venue_scale = get_venue_spec(venue).overall_dim.scale  # (lo, hi)
    passed = False

    for round_num in range(1, max_rounds + 1):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ── 1. Read paper (any format: dir, .pdf, .docx, .md, .tex, ...) ──
        paper_content = _read_paper(paper_dir, exec_runtime)

        # ── 1.5. Build prior-work context (grounded retrieval) ──
        base_dir = os.path.join(project_dir, "auto_review")
        round_dir = os.path.join(base_dir, f"round_{round_num}")
        prior_work_context = ""
        grounding_meta = None
        if with_grounding:
            grounding_save_path = os.path.join(round_dir, "prior_work_context.md")
            os.makedirs(round_dir, exist_ok=True)
            try:
                grounding_meta = build_prior_work_context(
                    paper_content=paper_content,
                    exec_runtime=exec_runtime,
                    review_runtime=review_runtime,
                    top_k=grounding_top_k,
                    save_to=grounding_save_path,
                    debug_dir=round_dir,
                )
                prior_work_context = grounding_meta.get("prior_work_context", "")
            except Exception as e:
                # Grounding is best-effort; if arxiv is unreachable etc.,
                # fall back to vanilla review (no context).
                grounding_meta = {"error": str(e)}
                prior_work_context = ""

        # ── 1.7. Commitment ledger audit (R&R traceability) ──
        # Prior rounds' revision-plan commitments are verified against the
        # CURRENT paper at the start of the review phase. NOT_ADDRESSED /
        # MADE_WORSE (and UNVERIFIED) items carry forward verbatim into
        # this round's revision-plan input.
        carry_items = []
        commitment_audit = None
        if commitment_ledger:
            commitment_audit = _audit_commitments(
                commitments=commitment_ledger,
                paper_content=paper_content,
                review_runtime=review_runtime,
            )
            _save(round_dir, "commitment_audit.json",
                  json.dumps(commitment_audit, ensure_ascii=False, indent=2))
            _append_auto_review(
                base_dir, _commitment_audit_table(commitment_audit, round_num))
            carry_items = _carry_from_audit(
                commitment_audit, commitment_ledger[-_COMMITMENT_FEED_CAP:])

        # ── 2. N independent reviews (each with fresh session) ──
        individual_replies = []
        individual_parsed = []
        for reviewer_id in range(1, num_reviewers + 1):
            persona = personas[(reviewer_id - 1) % len(personas)] if personas else ""
            reply = _run_single_review(
                paper_content=paper_content, paper_dir=paper_dir,
                venue=venue, venue_criteria=venue_criteria,
                round_num=round_num, max_rounds=max_rounds,
                difficulty=difficulty, reviewer_memory=reviewer_memory,
                review_runtime=review_runtime,
                prior_work_context=prior_work_context,
                persona=persona,
            )
            individual_replies.append(reply)
            # Filename includes persona for traceability
            persona_tag = f"_{persona}" if persona else ""
            _save(round_dir, f"reviewer_{reviewer_id}{persona_tag}.md", reply)

            parsed = parse_review_or_extract(reply, venue=venue)
            parsed["reviewer_id"] = reviewer_id
            parsed["persona"] = persona
            individual_parsed.append(parsed)

        # ── 2.5. External reviewers (e.g. paperreview.ai) ──
        external_meta = []
        for provider in external_providers:
            url = (external_review_urls or {}).get(provider, "")
            ext_reply = fetch_external_review(
                paper_path=paper_dir,
                provider=provider,
                venue=venue,
                email=external_email,
                review_url=url,
                runtime=exec_runtime,
            )
            # Detect "needs_manual_step" / "not_ready" responses that should
            # NOT be counted as a real review.
            try:
                ext_parsed_pre = parse_json(ext_reply)
                ext_status = ext_parsed_pre.get("status", "")
            except (ValueError, AttributeError):
                ext_parsed_pre = None
                ext_status = ""

            if ext_status in ("needs_manual_step", "not_ready"):
                _save(round_dir, f"external_{provider}_pending.md", ext_reply)
                external_meta.append({
                    "provider": provider,
                    "status": ext_status,
                    "saved_to": os.path.join(round_dir,
                                             f"external_{provider}_pending.md"),
                })
                if callback:
                    callback({"type": "external_pending",
                              "provider": provider, "round": round_num,
                              "instructions_path": os.path.join(
                                  round_dir, f"external_{provider}_pending.md")})
                continue

            # Treat as a real reviewer: append to individual lists.
            ext_id = num_reviewers + len([m for m in external_meta
                                          if m.get("status") == "ok"]) + 1
            individual_replies.append(ext_reply)
            _save(round_dir,
                  f"reviewer_{ext_id}_external_{provider}.md", ext_reply)
            try:
                ext_parsed = parse_json(ext_reply)
            except ValueError:
                ext_parsed = {"score": 0, "weaknesses": [], "strengths": []}
            ext_parsed["reviewer_id"] = ext_id
            ext_parsed["persona"] = f"external_{provider}"
            ext_parsed["external_provider"] = provider
            individual_parsed.append(ext_parsed)
            external_meta.append({
                "provider": provider,
                "status": "ok",
                "url": url,
                "saved_to": os.path.join(
                    round_dir, f"reviewer_{ext_id}_external_{provider}.md"),
            })

        # ── 3. Area Chair meta-review ──
        all_reviews_text = "\n\n---\n\n".join(
            f"### Reviewer {i+1}"
            f"{' [' + p['persona'] + ']' if p.get('persona') else ''}"
            f" (Score: {p.get('score', '?')})\n\n{r}"
            for i, (r, p) in enumerate(zip(individual_replies, individual_parsed))
        )

        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()
        meta_reply = _meta_review(
            individual_reviews=all_reviews_text,
            venue=venue,
            runtime=review_runtime,
        )
        # Save raw AC output
        _save(round_dir, "meta_review.md", meta_reply)

        # ── 4. Parse meta-review ──
        review = parse_review_or_extract(meta_reply, venue=venue)
        # If meta_reply parsing yields no score, average the per-reviewer scores
        # as a final fallback.
        if not review.get("score"):
            scores = [p.get("score", 0) for p in individual_parsed
                      if isinstance(p.get("score"), (int, float))]
            if scores:
                review["score"] = round(sum(scores) / len(scores), 2)
                review["individual_scores"] = scores
        # Carry over aggregated weaknesses/strengths if meta missed them
        if not review.get("weaknesses"):
            review["weaknesses"] = [w for p in individual_parsed
                                    for w in p.get("weaknesses", [])]
        if not review.get("strengths"):
            review["strengths"] = [s for p in individual_parsed
                                   for s in p.get("strengths", [])]

        review["round"] = round_num
        review["full_review"] = meta_reply
        review["individual_reviews"] = individual_replies
        review["individual_parsed"] = individual_parsed
        review["difficulty"] = difficulty
        review["timestamp"] = ts
        review["num_reviewers"] = num_reviewers
        if grounding_meta is not None:
            review["grounding"] = {
                "candidates_count": grounding_meta.get("candidates_count", 0),
                "selected_count": grounding_meta.get("selected_count", 0),
                "saved_to": grounding_meta.get("saved_to"),
                "error": grounding_meta.get("error"),
            }
        if external_meta:
            review["external"] = external_meta

        # ── 4.4. GPTZero AI-detection on the paper itself ──
        if with_gptzero:
            sample = _gptzero_sample(paper_content)
            try:
                ai_det = check_ai_score_gptzero(
                    sample, cdp_url=gptzero_cdp_url, poll_timeout=60.0,
                )
            except Exception as e:
                ai_det = {"status": "error",
                          "error": f"{type(e).__name__}: {e}",
                          "ai_pct": None}
            ai_pct = ai_det.get("ai_pct")
            ai_det["recommend_humanize"] = (
                isinstance(ai_pct, (int, float))
                and ai_pct >= gptzero_humanize_threshold
            )
            ai_det["sample_chars"] = len(sample)
            ai_det["humanize_threshold"] = gptzero_humanize_threshold
            review["ai_detection"] = ai_det
            _save(round_dir, "ai_detection.json",
                  json.dumps(ai_det, ensure_ascii=False, indent=2))

        # ── 4.5. Calibrate score from sub-scores (venue-aware regression) ──
        # AC meta-review's raw `score` may be unreliable when LLM emits a single
        # scalar; if sub_scores are present we compute a calibrated score from
        # the per-dimension regression. The raw score is preserved as `raw_score`.
        sub_scores = review.get("sub_scores", {})
        if isinstance(sub_scores, dict) and sub_scores:
            try:
                calib = calibrate_score(sub_scores=sub_scores, venue=venue)
                review["calibration"] = calib
                # Override score with calibrated value, but keep raw available.
                review["raw_score_from_meta"] = review.get("score")
                review["score"] = calib["calibrated_score"]
            except Exception as e:
                review["calibration"] = {"error": str(e)}

        # Accumulate reviewer memory (hard/nightmare)
        if difficulty in ("hard", "nightmare"):
            reviewer_memory += (
                f"\n## Round {round_num} — Meta Score: {review.get('score', 0)}/10\n"
                f"- **Suspicions**: {meta_reply[:500]}\n"
            )

        # ── 5. Debate (hard/nightmare) — rulings APPLIED to the review ──
        # Concession-threshold protocol: withdraw only at rebuttal score 5,
        # downgrade at 4, escalating to 5-only after any concession.
        # Withdrawn weaknesses are dropped and the score is adjusted BEFORE
        # the stop-condition check (closes the old "debate is cosmetic" gap).
        if difficulty in ("hard", "nightmare") and review.get("weaknesses"):
            debate = _run_debate(
                review["weaknesses"], paper_content,
                exec_runtime, review_runtime,
                return_rulings=True,
            )
            review["debate_transcript"] = debate["transcript"]
            if debate["rulings"]:
                review["debate_rulings"] = debate["rulings"]
                adj = _apply_debate_rulings(
                    review, debate["rulings"], scale_max=venue_scale[1])
                review["debate_adjustment"] = adj
                review["debate_transcript"] += (
                    "\n\n**Applied rulings:** "
                    + json.dumps(adj, ensure_ascii=False)
                )

        # ── 5.7. Score trajectory (per-dimension deltas vs previous round) ──
        regression_warning = ""
        traj = _score_trajectory(reviews + [review], scale_range=venue_scale)
        if traj:
            review["score_trajectory"] = traj
            _append_auto_review(base_dir, _trajectory_table(traj))
            if traj["regressions"]:
                review["regression_flags"] = traj["regressions"]
                regression_warning = _regression_warning(traj)
        if commitment_audit is not None:
            review["commitment_audit"] = commitment_audit
        if carry_items:
            review["carried_commitments"] = carry_items

        # ── 6. Save debate + accumulate reviews ──
        if review.get("debate_transcript"):
            _save(round_dir, "debate.md", review["debate_transcript"])

        # ── 6.5. Build revision plan (always; this is the contract between
        #         review and fix, decoupled from auto_fix decision) ──
        if hasattr(review_runtime, 'reset'):
            review_runtime.reset()
        carry_text = _carry_section(carry_items)
        revision_plan = build_revision_plan(
            paper_content=paper_content,
            individual_reviews=all_reviews_text,
            # Carried-over commitments ride along with the meta-review so the
            # planner cannot silently drop them.
            meta_review=meta_reply + ("\n" + carry_text if carry_text else ""),
            venue=venue,
            venue_criteria=venue_criteria,
            runtime=review_runtime,
        )
        # The saved plan IS the fix prompt (apply_revision_plan reads it):
        # append the regression warning + carried commitments verbatim so the
        # author model sees what it damaged and what it still owes.
        if regression_warning or carry_text:
            revision_plan = revision_plan + regression_warning + carry_text
        _save(round_dir, "revision_plan.md", revision_plan)
        review["revision_plan"] = revision_plan
        review["revision_plan_path"] = os.path.join(round_dir, "revision_plan.md")

        reviews.append(review)

        if callback and callback({"type": "review", **review}) is False:
            break

        # ── 7. Stop if passed (venue-aware) ──
        score = review.get("score", 0)
        verdict_text = str(review.get("verdict", ""))
        # Use venue's accept_threshold rather than the loop's pass_threshold,
        # because pass_threshold is on the venue's scale (e.g. ARR 1-5 vs
        # NeurIPS 1-6) and may have been left at default by the caller.
        from research_harness.references.venue_scoring import (
            get_venue_spec, map_verdict_to_score,
        )
        venue_spec = get_venue_spec(venue)
        venue_threshold = venue_spec.accept_threshold
        # A caller-supplied threshold (on the venue's own scale) wins;
        # the default is the venue's main-track accept threshold. Taking
        # max() against a fixed 1-10-scale default made passing impossible
        # for venues scored on 1-5 / 1-6 scales.
        effective_threshold = (
            venue_threshold if pass_threshold is None else float(pass_threshold)
        )

        passed_by_score = score >= effective_threshold
        # Verdict-keyword fallback uses venue-specific mapping (ARR's "Findings"
        # → 3.0 < 4.0 = NOT main-track accept, even though "accept" is in the string).
        verdict_score = map_verdict_to_score(venue_spec, verdict_text)
        passed_by_verdict = (
            verdict_score is not None and verdict_score >= effective_threshold
        )
        if passed_by_score or passed_by_verdict:
            passed = True
            break

        # ── 8. Apply revision plan (only if auto_fix enabled) ──
        # Default is auto_fix=False: review_loop stops here. The user (or a
        # downstream orchestrator) decides whether to call apply_revision_plan
        # against the saved revision_plan.md.
        if not auto_fix:
            break

        # ── 7.5. Commitment ledger: persist this plan's action items ──
        new_commitments = _parse_plan_commitments(revision_plan)
        for c in new_commitments:
            c["round"] = round_num
        if new_commitments:
            _save(round_dir, "commitments.json",
                  json.dumps({"round": round_num,
                              "commitments": new_commitments},
                             ensure_ascii=False, indent=2))
            commitment_ledger.extend(new_commitments)

        if hasattr(exec_runtime, 'reset'):
            exec_runtime.reset()

        new_paper_dir = apply_revision_plan(
            paper_dir=paper_dir,
            plan_path=review["revision_plan_path"],
            output_dir=os.path.join(round_dir, "paper"),
            round_num=round_num,
            exec_runtime=exec_runtime,
        )
        # Subsequent rounds read from the new versioned dir.
        paper_dir = new_paper_dir

        if callback:
            callback({"type": "fix", "round": round_num,
                      "new_paper_dir": new_paper_dir})
    else:
        passed = False

    # ── Build summary ──
    final_score = reviews[-1].get("score", 0) if reviews else 0
    total_rounds = reviews[-1].get("round", 0) if reviews else 0

    summary_lines = [
        f"# Review Summary",
        f"",
        f"- **Paper**: {paper_dir}",
        f"- **Venue**: {venue}",
        f"- **Difficulty**: {difficulty}",
        f"- **Reviewers per round**: {num_reviewers}",
        f"- **Rounds completed**: {total_rounds}",
        f"- **Auto-fix**: {'enabled' if auto_fix else 'disabled'}",
        f"- **Grounded retrieval**: {'enabled' if with_grounding else 'disabled'}",
        f"- **Result**: {'PASSED' if passed else 'NOT PASSED'} (score: {final_score})",
        f"",
    ]

    for r in reviews:
        rn = r.get("round", "?")
        summary_lines.append(f"## Round {rn}")
        g = r.get("grounding")
        if g:
            if g.get("error"):
                summary_lines.append(
                    f"- Grounding: **FAILED** ({g['error'][:80]})"
                )
            else:
                summary_lines.append(
                    f"- Grounding: **{g.get('selected_count', 0)}/"
                    f"{g.get('candidates_count', 0)}** priors → "
                    f"`round_{rn}/prior_work_context.md`"
                )
        for ip in r.get("individual_parsed", []):
            rid = ip.get("reviewer_id", "?")
            s = ip.get("score", "?")
            persona = ip.get("persona", "")
            persona_tag = f"_{persona}" if persona else ""
            persona_label = f" [{persona}]" if persona else ""
            summary_lines.append(
                f"- Reviewer {rid}{persona_label}: **{s}** "
                f"→ `round_{rn}/reviewer_{rid}{persona_tag}.md`"
            )
        summary_lines.append(f"- Area Chair: **{r.get('score', '?')}** → `round_{rn}/meta_review.md`")
        ad = r.get("ai_detection")
        if ad:
            if ad.get("status") == "ok" and isinstance(ad.get("ai_pct"), (int, float)):
                flag = " ⚠ recommend humanize" if ad.get("recommend_humanize") else ""
                summary_lines.append(
                    f"- GPTZero (AI %): **{ad.get('ai_pct')}%** "
                    f"(mixed {ad.get('mixed_pct', 0)}%, human {ad.get('human_pct', 0)}%, "
                    f"{ad.get('confidence', '?')} confidence){flag} "
                    f"→ `round_{rn}/ai_detection.json`"
                )
            else:
                summary_lines.append(
                    f"- GPTZero (AI %): **{ad.get('status', 'error').upper()}** — "
                    f"{(ad.get('error') or '')[:120]}"
                )
        for em in r.get("external", []):
            prov = em.get("provider", "?")
            if em.get("status") == "ok":
                summary_lines.append(
                    f"- External [{prov}]: **OK** → `{os.path.basename(em.get('saved_to', ''))}`"
                )
            else:
                summary_lines.append(
                    f"- External [{prov}]: **{em.get('status', 'unknown').upper()}** "
                    f"→ see `{os.path.basename(em.get('saved_to', ''))}` for instructions"
                )
        if r.get("debate_transcript"):
            summary_lines.append(f"- Debate → `round_{rn}/debate.md`")
        da = r.get("debate_adjustment")
        if da:
            summary_lines.append(
                f"- Debate rulings applied: {da.get('withdrawn', 0)} withdrawn, "
                f"{da.get('downgraded', 0)} downgraded, "
                f"{da.get('sustained', 0)} sustained "
                f"(score {da.get('pre_debate_score', '?')} → "
                f"{da.get('adjusted_score', '?')})"
            )
        if r.get("revision_plan_path"):
            summary_lines.append(f"- Revision plan → `round_{rn}/revision_plan.md`")
        summary_lines.append(f"- Verdict: {r.get('verdict', 'N/A')}")
        summary_lines.append("")
        if r.get("commitment_audit"):
            summary_lines.append(
                _commitment_audit_table(r["commitment_audit"], rn))
        if r.get("score_trajectory"):
            summary_lines.append(_trajectory_table(r["score_trajectory"]))

    summary_lines.append("")
    summary_lines.append("## Next steps")
    if passed:
        summary_lines.append("- Paper passed. No fix needed.")
    elif reviews:
        last = reviews[-1]
        if last.get("revision_plan_path"):
            summary_lines.append(
                f"- Review the revision plan at "
                f"`round_{last.get('round', '?')}/revision_plan.md`."
            )
            summary_lines.append(
                f"- To apply it: call `apply_revision_plan(paper_dir, "
                f"plan_path, output_dir, exec_runtime)` "
                f"(or re-run review_loop with `auto_fix=True`)."
            )
        summary_lines.append("")

    summary = "\n".join(summary_lines)
    base_dir = os.path.join(project_dir, "auto_review")
    _save(base_dir, "AUTO_REVIEW.md", summary)

    return {
        "passed": passed,
        "rounds": total_rounds,
        "final_score": final_score,
        "reviews": reviews,
        "difficulty": difficulty,
        "num_reviewers": num_reviewers,
        "with_grounding": with_grounding,
        "summary": summary,
    }


__all__ = [
    'adaptive_summarize_priors', 'apply_revision_plan',
    'build_prior_work_context', 'build_revision_plan',
    'calibrate_score',
    'check_ai_score_gptzero',
    'detect_ai_flavor', 'docx_to_markdown',
    'fetch_external_review',
    'filter_relevant_priors', 'fix_paper',
    'generate_multi_specificity_queries',
    'load_paper', 'lookup_venue_criteria', 'pdf_to_markdown',
    'review_paper', 'review_paper_grounded',
    'paper_improvement_loop', 'review_loop',
    'DEFAULT_PERSONAS',
]
