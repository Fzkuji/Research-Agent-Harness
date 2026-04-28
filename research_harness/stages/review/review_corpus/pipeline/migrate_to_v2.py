"""Upgrade existing v1 reviewer_*.json files in source/ to v2 schema.

For each v1 reviewer JSON in source/<venue>/<year>/<forum>/reviewer_*.json:
  1. Skip if schema_version == 2 already.
  2. Re-fetch paper meta (authors/abstract/keywords/decision) from
     OpenReview using the stored forum_id.
  3. Re-fetch the reviewer's raw OpenReview note to get every content
     field separately (v1 had fold-ed questions into weaknesses; v2
     keeps them apart).
  4. Preserve the existing ai_score so we don't waste GPTZero calls.
  5. Write back as v2 schema.

OpenReview API is hit once per forum (paper meta) plus once per
reviewer (the reviewer note). Total network: ~2× number of v1 JSONs.
For the existing 127-reviewer corpus that's ~250 requests, ≈3-5 min
at 0.4s/request.

Run with:
    python -m research_harness.stages.review.review_corpus.pipeline.migrate_to_v2
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RAW_ROOT = _HERE.parent / "source"

# Re-use the v2 collector's helpers — keeps the schema identical.
from research_harness.stages.review.review_corpus.pipeline.collect_from_openreview import (  # noqa: E402
    SCHEMA_VERSION,
    fetch_paper_meta,
    fetch_reviews_for_forum,
)


def _is_api_v2(venue: str, year: int) -> bool:
    """Decide which OpenReview API version a (venue, year) lives on.

    Mirror of the table in collect_from_openreview.py. ICLR pre-2023 is
    on V1; everything else we currently care about is on V2.
    """
    venue_lower = (venue or "").lower()
    if venue_lower.startswith("iclr") and year < 2023:
        return False
    return True


def migrate_one(rpath: Path, *, dry_run: bool = False) -> dict:
    """Upgrade one reviewer JSON. Returns a status dict."""
    try:
        old = json.loads(rpath.read_text())
    except Exception as e:
        return {"path": str(rpath), "status": "error",
                "error": f"read failed: {type(e).__name__}: {e}"}

    if old.get("schema_version") == SCHEMA_VERSION:
        return {"path": str(rpath), "status": "skipped_already_v2"}

    venue = old.get("venue")
    year = int(old.get("year") or 0)
    forum_id = old.get("forum_id")
    reviewer = old.get("reviewer")
    if not (venue and year and forum_id and reviewer):
        return {"path": str(rpath), "status": "error",
                "error": f"missing identity fields in old JSON: "
                         f"venue={venue} year={year} "
                         f"forum_id={forum_id} reviewer={reviewer}"}

    api_v2 = _is_api_v2(venue, year)

    # 1. Paper meta
    try:
        paper_meta = fetch_paper_meta(forum_id, api_v2=api_v2)
    except Exception as e:
        return {"path": str(rpath), "status": "error",
                "error": f"paper meta fetch failed: {type(e).__name__}: {e}"}

    # 2. Reviewer raw fields — fetch all reviewers on this forum, find ours.
    try:
        revs = fetch_reviews_for_forum(forum_id, api_v2=api_v2)
    except Exception as e:
        return {"path": str(rpath), "status": "error",
                "error": f"reviewer fetch failed: {type(e).__name__}: {e}"}
    match = next((r for r in revs if r.get("reviewer") == reviewer), None)
    if match is None:
        # Reviewer note disappeared from OpenReview (uncommon — could be
        # privacy redaction). Synthesize a minimal v2 record from the v1
        # data so we don't lose the ai_score.
        v1_fields = {}
        for k in ("summary", "strengths", "weaknesses"):
            v = (old.get(k) or "").strip()
            if v:
                v1_fields[k] = v
        if (old.get("full_review") or "").strip():
            v1_fields["main_review"] = old["full_review"]
        review_fields = v1_fields
        review_metadata: dict = {}
        source_extras = {
            "openreview_field_keys": (old.get("field_keys") or {}),
            "openreview_invitation":
                (old.get("field_keys") or {}).get("invitation_tail", ""),
            "api_version": "v2" if api_v2 else "v1",
            "_migration_note":
                "reviewer note not found on OpenReview at migration time; "
                "carried over v1 fields verbatim",
        }
    else:
        review_fields = match["review_fields"]
        review_metadata = match.get("review_metadata", {})
        source_extras = match.get("source_extras", {})
        source_extras["api_version"] = "v2" if api_v2 else "v1"

    source_extras["collected_at"] = (
        datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )
    source_extras["migrated_from_v1_at"] = source_extras["collected_at"]

    # 3. Preserve ai_score (verifies via GPTZero). The new text might be
    # *slightly* different from the v1 concat (questions split out etc.),
    # but the GPTZero classification is on the *same human reviewer* so
    # it remains a valid validation signal.
    new_record = {
        "schema_version": SCHEMA_VERSION,
        "venue": venue,
        "year": year,
        "forum_id": forum_id,
        "reviewer": reviewer,
        "paper": paper_meta,
        "review_fields": review_fields,
        "review_metadata": review_metadata,
        "source": source_extras,
    }
    if old.get("ai_score") is not None:
        new_record["ai_score"] = old["ai_score"]

    if dry_run:
        return {"path": str(rpath), "status": "dry_run_would_upgrade",
                "preview_keys": list(new_record.keys()),
                "n_review_fields": len(review_fields),
                "decision": paper_meta.get("decision"),
                "n_authors": len(paper_meta.get("authors", []))}

    rpath.write_text(json.dumps(new_record, indent=2, ensure_ascii=False))
    return {"path": str(rpath), "status": "upgraded",
            "n_review_fields": len(review_fields),
            "decision": paper_meta.get("decision")}


def migrate_all(*, dry_run: bool = False, sleep_between: float = 0.4) -> dict:
    if not RAW_ROOT.is_dir():
        raise SystemExit(f"source/ not found at {RAW_ROOT}")

    counts = {
        "total": 0,
        "skipped_already_v2": 0,
        "upgraded": 0,
        "error": 0,
        "dry_run_would_upgrade": 0,
    }
    log: list[dict] = []
    paths = sorted(RAW_ROOT.glob("*/*/*/reviewer_*.json"))
    print(f"found {len(paths)} reviewer JSONs", flush=True)

    for i, p in enumerate(paths, 1):
        res = migrate_one(p, dry_run=dry_run)
        counts["total"] += 1
        counts[res["status"]] = counts.get(res["status"], 0) + 1
        log.append(res)
        tag = res["status"]
        extra = ""
        if "n_review_fields" in res:
            extra = f"  fields={res['n_review_fields']}"
        if "decision" in res:
            extra += f"  decision={res['decision']!r}"
        if "error" in res:
            extra += f"  error={res['error'][:80]}"
        print(f"  [{i}/{len(paths)}] {tag:25} {p.relative_to(RAW_ROOT)}{extra}",
              flush=True)
        # Network politeness — but skip sleep for skips (no network hit).
        if res["status"] not in ("skipped_already_v2", "error"):
            time.sleep(sleep_between)

    return {"counts": counts, "log_path": None}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry_run", action="store_true",
                   help="Print what would be upgraded; do not write.")
    p.add_argument("--sleep_between", type=float, default=0.4,
                   help="Seconds between OpenReview API calls. Default 0.4.")
    args = p.parse_args()
    print(f"\nrunning migrate_to_v2 (dry_run={args.dry_run})\n")
    result = migrate_all(dry_run=args.dry_run,
                         sleep_between=args.sleep_between)
    print()
    print(f"=== summary ===")
    for k, v in result["counts"].items():
        print(f"  {k:25} {v}")
