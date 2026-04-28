"""Pass every collected review through GPTZero; keep only validated-human ones.

Reads:  stages/review/review_corpus/source/<venue>/<year>/<forum>/reviewer_*.json
Writes: same dir, adds ai_score field; also writes
        stages/review/review_corpus/processed/filter_summary.json
        stages/review/review_corpus/processed/human_reviews.json   <- the curated samples

A review qualifies as a voice sample when:
  - text length >= 350 chars (GPTZero needs >= 250; we want enough body)
  - GPTZero result status == "ok"
  - human_pct >= 80 OR ai_pct == 0
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RAW_ROOT = _HERE.parent / "source"        # raw reviewer JSON tree
DERIVED_ROOT = _HERE.parent / "processed"      # human_reviews / filter_summary

# Ensure we can import the GPTZero adapter even when run as a module from
# the repo root. parents[4] now points to the repo root after the
# reorganization (pipeline/ is one level deeper than the old layout).
if str(Path(__file__).resolve().parents[4]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from research_harness.stages.external.gptzero_browser import (  # noqa: E402
    check_ai_score_gptzero,
)


def _ensure_cdp_up() -> bool:
    """Make sure the sidecar Chrome on port 9222 is alive; relaunch otherwise.
    Returns True iff CDP is reachable after the call."""
    try:
        from openprogram.tools.browser._chrome_bootstrap import (
            cdp_url_if_available, launch_sidecar_chrome,
        )
    except ImportError:
        return False
    if cdp_url_if_available():
        return True
    launch_sidecar_chrome()
    return cdp_url_if_available() is not None


# Field-name canonicalization for GPTZero scoring across venues.
# Different venues use different field names for the same logical thing.
# We pick critique-flavored fields (weaknesses + questions) as the
# strongest GPTZero signal — they are the most reviewer-prose-like and
# least likely to paraphrase the paper. Strengths are also included.
# We deliberately exclude `summary` since it paraphrases the paper
# itself and biases the detector toward AI-style abstractive prose.
_GPTZERO_TEXT_FIELDS_ORDER = (
    # weaknesses-like
    "weaknesses", "weaknesses_and_limitations", "weaknesses_and_questions",
    "cons", "limitations", "reasons_to_reject",
    # questions-like
    "questions", "questions_to_authors", "questions_for_authors",
    # strengths-like
    "strengths", "pros", "strengths_and_questions", "reasons_to_accept",
    # fallback unstructured
    "main_review", "review", "comment", "summary_of_the_review",
)


def _pick_text(review: dict) -> str:
    """Concatenate prose chunks for GPTZero scoring.

    v2 schema: walks review_fields in canonical order (weaknesses-like
    first, then questions-like, then strengths-like, then fallback
    unstructured). v1 fallback: reads weaknesses/strengths/full_review
    directly off the top level.
    """
    if review.get("schema_version") == 2:
        fields = review.get("review_fields", {}) or {}
        parts: list[str] = []
        for k in _GPTZERO_TEXT_FIELDS_ORDER:
            v = (fields.get(k) or "").strip()
            if v:
                parts.append(v)
        if parts:
            return "\n\n".join(parts)
        # If none of the canonical names matched, fall back to anything
        # in review_fields (preserves coverage for venue-specific keys
        # we have not enumerated).
        return "\n\n".join(v.strip() for v in fields.values()
                           if isinstance(v, str) and v.strip())

    # v1 schema fallback
    parts = []
    for k in ("weaknesses", "strengths"):
        v = review.get(k) or ""
        if v.strip():
            parts.append(v.strip())
    if parts:
        return "\n\n".join(parts)
    full = review.get("full_review") or ""
    return full.strip()


def filter_all(*, sleep_between: float = 1.5,
               min_chars: int = 350, human_threshold: float = 80.0,
               retry_only_failed: bool = False) -> dict:
    """Score every review, or only the ones that previously errored.

    retry_only_failed=True: skip notes whose ai_score.status == 'ok'. Used
    when re-running after a CDP / network blip wiped out partial results.
    """
    summary = {
        "total": 0,
        "scored": 0,
        "skipped_short": 0,
        "scored_failures": 0,
        "human_kept": 0,
        "ai_dropped": 0,
        "mixed_dropped": 0,
        "buckets": {},
        "kept_samples": [],
    }
    human_reviews = []

    # Walk the corpus deterministically.
    for venue_dir in sorted(p for p in RAW_ROOT.iterdir()
                            if p.is_dir() and not p.name.startswith("_")):
        venue = venue_dir.name
        for year_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
            year = int(year_dir.name)
            bk = summary["buckets"].setdefault(
                f"{venue}/{year}",
                {"total": 0, "human": 0, "ai": 0, "mixed": 0, "short": 0,
                 "errors": 0})
            for forum_dir in sorted(p for p in year_dir.iterdir()
                                    if p.is_dir()):
                for review_path in sorted(forum_dir.glob("reviewer_*.json")):
                    summary["total"] += 1
                    bk["total"] += 1
                    with open(review_path) as f:
                        review = json.load(f)
                    prev = review.get("ai_score") or {}
                    if retry_only_failed and prev.get("status") == "ok":
                        # Already scored cleanly — re-emit into per-bucket
                        # counters but don't re-call GPTZero.
                        if isinstance(prev.get("human_pct"), (int, float)) and \
                           prev["human_pct"] >= human_threshold:
                            summary["human_kept"] += 1
                            bk["human"] += 1
                            human_reviews.append({
                                "venue": review.get("venue"),
                                "year": review.get("year"),
                                "forum_id": review.get("forum_id"),
                                "paper_title": review.get("paper_title"),
                                "reviewer": review.get("reviewer"),
                                "text": _pick_text(review),
                                "ai_pct": prev.get("ai_pct"),
                                "human_pct": prev.get("human_pct"),
                                "verdict": prev.get("verdict"),
                                "source_path": str(
                                    review_path.relative_to(RAW_ROOT.parent)),
                            })
                        elif isinstance(prev.get("ai_pct"), (int, float)) \
                                and prev["ai_pct"] >= 80:
                            summary["ai_dropped"] += 1
                            bk["ai"] += 1
                        else:
                            summary["mixed_dropped"] += 1
                            bk["mixed"] += 1
                        summary["scored"] += 1
                        continue

                    text = _pick_text(review)
                    if len(text) < min_chars:
                        review["ai_score"] = {"status": "skipped",
                                              "reason": f"too_short:{len(text)}"}
                        with open(review_path, "w") as f:
                            json.dump(review, f, ensure_ascii=False, indent=2)
                        summary["skipped_short"] += 1
                        bk["short"] += 1
                        continue

                    # Self-heal: ensure CDP is up before each call. Relaunches
                    # the sidecar Chrome if the user / OS killed it between
                    # iterations (we hit this on the first run when 43/45
                    # samples failed with "connection refused" mid-batch).
                    if not _ensure_cdp_up():
                        review["ai_score"] = {
                            "status": "error",
                            "error": "CDP unreachable and could not be relaunched",
                            "ai_pct": None,
                        }
                        with open(review_path, "w") as f:
                            json.dump(review, f, ensure_ascii=False, indent=2)
                        summary["scored_failures"] += 1
                        bk["errors"] += 1
                        time.sleep(sleep_between)
                        continue

                    print(f"[{summary['total']}] {venue}/{year}/{review_path.parent.name}/"
                          f"{review_path.stem} ({len(text)} chars) …", flush=True)
                    try:
                        result = check_ai_score_gptzero(text, poll_timeout=60)
                    except Exception as e:
                        result = {"status": "error",
                                  "error": f"{type(e).__name__}: {e}",
                                  "ai_pct": None}
                    review["ai_score"] = {**result, "scored_chars": len(text)}
                    with open(review_path, "w") as f:
                        json.dump(review, f, ensure_ascii=False, indent=2)

                    if result.get("status") != "ok":
                        summary["scored_failures"] += 1
                        bk["errors"] += 1
                        time.sleep(sleep_between)
                        continue
                    summary["scored"] += 1

                    ai_pct = result.get("ai_pct")
                    human_pct = result.get("human_pct")
                    if (isinstance(human_pct, (int, float))
                            and human_pct >= human_threshold) or ai_pct == 0:
                        summary["human_kept"] += 1
                        bk["human"] += 1
                        sample = {
                            "venue": review.get("venue"),
                            "year": review.get("year"),
                            "forum_id": review.get("forum_id"),
                            "paper_title": review.get("paper_title"),
                            "reviewer": review.get("reviewer"),
                            "text": text,
                            "ai_pct": ai_pct,
                            "human_pct": human_pct,
                            "verdict": result.get("verdict"),
                            "source_path": str(
                                review_path.relative_to(RAW_ROOT.parent)),
                        }
                        human_reviews.append(sample)
                        summary["kept_samples"].append(
                            f"{venue}/{year}/{review.get('forum_id')}/"
                            f"r{review.get('reviewer')} ({len(text)} chars, "
                            f"{human_pct}% human)"
                        )
                    elif (isinstance(ai_pct, (int, float))
                          and ai_pct >= 80):
                        summary["ai_dropped"] += 1
                        bk["ai"] += 1
                    else:
                        summary["mixed_dropped"] += 1
                        bk["mixed"] += 1

                    time.sleep(sleep_between)

    DERIVED_ROOT.mkdir(parents=True, exist_ok=True)
    with open(DERIVED_ROOT / "filter_summary.json", "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(DERIVED_ROOT / "human_reviews.json", "w") as f:
        json.dump(human_reviews, f, ensure_ascii=False, indent=2)
    return summary


if __name__ == "__main__":
    s = filter_all()
    print()
    print(f"TOTAL  scored={s['scored']}  human_kept={s['human_kept']}  "
          f"ai_dropped={s['ai_dropped']}  mixed={s['mixed_dropped']}  "
          f"errors={s['scored_failures']}  short={s['skipped_short']}")
    print()
    print("buckets:")
    for k, v in s["buckets"].items():
        print(f"  {k}:  total={v['total']}  human={v['human']}  ai={v['ai']}  "
              f"mixed={v['mixed']}  short={v['short']}  err={v['errors']}")
