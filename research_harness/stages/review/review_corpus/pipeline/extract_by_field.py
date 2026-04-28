"""Extract sentence templates from human-verified reviews, grouped by
the venue-original field name (not heuristic content classification).

Inputs:
  - source/<venue>/<year>/<forum>/reviewer_*.json (v2 schema)
  - processed/human_reviews.json (filter output, lists which reviewers
    passed GPTZero)

Outputs:
  - processed/sentence_templates_by_field.json  ← structured for sampler
  - processed/sentence_templates_by_field.txt   ← human-readable preview

Each output entry tracks per-sentence:
  - text (verbatim sentence)
  - field (the OpenReview field it came from, e.g. "reasons_to_reject")
  - canonical_field (mapped to one of: SUMMARY / STRENGTHS / WEAKNESSES /
    QUESTIONS / FULL — see CANONICAL_FIELD_MAP below)
  - venue, year, forum_id, reviewer (provenance for sampler)

Replaces extract_sentence_templates.py (kept on disk for back-compat).
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DERIVED_ROOT = _HERE.parent / "processed"
RAW_ROOT = _HERE.parent / "source"
HUMAN_REVIEWS_PATH = DERIVED_ROOT / "human_reviews.json"
OUT_JSON = DERIVED_ROOT / "sentence_templates_by_field.json"
OUT_TXT = DERIVED_ROOT / "sentence_templates_by_field.txt"


CANONICAL_FIELD_MAP = {
    # SUMMARY — paper synopsis the reviewer wrote
    "summary":               "SUMMARY",
    "paper_summary":         "SUMMARY",
    "summary_of_the_paper":  "SUMMARY",

    # STRENGTHS — positive evaluation
    "strengths":             "STRENGTHS",
    "pros":                  "STRENGTHS",
    "strengths_and_questions": "STRENGTHS",
    "reasons_to_accept":     "STRENGTHS",

    # WEAKNESSES — critique
    "weaknesses":            "WEAKNESSES",
    "weaknesses_and_limitations": "WEAKNESSES",
    "weaknesses_and_questions":   "WEAKNESSES",
    "cons":                  "WEAKNESSES",
    "limitations":           "WEAKNESSES",
    "reasons_to_reject":     "WEAKNESSES",

    # QUESTIONS — direct questions to authors
    "questions":             "QUESTIONS",
    "questions_to_authors":  "QUESTIONS",
    "questions_for_authors": "QUESTIONS",

    # FULL — unstructured / single-block review (ICLR V1 main_review,
    # COLM comment). Mixed content not separated by field.
    "main_review":           "FULL",
    "review":                "FULL",
    "comment":               "FULL",
    "summary_of_the_review": "FULL",
}

BUCKET_ORDER = ("SUMMARY", "STRENGTHS", "WEAKNESSES", "QUESTIONS", "FULL")


def _looks_useful(s: str) -> bool:
    if len(s) < 25 or len(s) > 350:
        return False
    if s.count("[") > 2 or s.count("(") > 4:
        return False
    alpha = [c for c in s if c.isalpha()]
    if alpha and sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.4:
        return False
    return True


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"https?://\S+", "", text)
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if s.strip()]


def _load_reviewer_jsons(only_human_kept: bool = True) -> list[dict]:
    keep = None
    if only_human_kept and HUMAN_REVIEWS_PATH.is_file():
        kept = json.loads(HUMAN_REVIEWS_PATH.read_text())
        keep = {(r["venue"], int(r["year"]), r["forum_id"], r["reviewer"])
                for r in kept}
    out: list[dict] = []
    for venue_dir in sorted(p for p in RAW_ROOT.iterdir() if p.is_dir()):
        for year_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
            for forum_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
                for rpath in sorted(forum_dir.glob("reviewer_*.json")):
                    try:
                        d = json.loads(rpath.read_text())
                    except Exception:
                        continue
                    key = (d.get("venue"), int(d.get("year") or 0),
                           d.get("forum_id"), d.get("reviewer"))
                    if keep is not None and key not in keep:
                        continue
                    out.append(d)
    return out


def _extract_one(review: dict) -> list[dict]:
    venue = review.get("venue", "?")
    year = int(review.get("year") or 0)
    forum_id = review.get("forum_id", "?")
    reviewer = review.get("reviewer", "?")

    if review.get("schema_version") == 2:
        fields = review.get("review_fields", {}) or {}
    else:
        fields = {}
        for k in ("summary", "strengths", "weaknesses"):
            v = review.get(k) or ""
            if v.strip():
                fields[k] = v
        if review.get("full_review", "").strip():
            fields["main_review"] = review["full_review"]

    out: list[dict] = []
    for raw_field, text in fields.items():
        if not isinstance(text, str) or not text.strip():
            continue
        canonical = CANONICAL_FIELD_MAP.get(raw_field, "FULL")
        for sent in _split_sentences(text):
            if not _looks_useful(sent):
                continue
            sent = re.sub(r"\s+", " ", sent).strip()
            out.append({
                "text":            sent,
                "field":           raw_field,
                "canonical_field": canonical,
                "venue":           venue,
                "year":            year,
                "forum_id":        forum_id,
                "reviewer":        reviewer,
            })
    return out


def extract(only_human_kept: bool = True) -> dict:
    reviews = _load_reviewer_jsons(only_human_kept=only_human_kept)
    print(f"loaded {len(reviews)} reviewer JSONs", flush=True)
    if not reviews:
        raise SystemExit("no reviewer JSONs found")

    all_sents: list[dict] = []
    for r in reviews:
        all_sents.extend(_extract_one(r))

    by_bucket: dict[str, list[dict]] = defaultdict(list)
    seen_per_bucket: dict[str, set[str]] = defaultdict(set)
    for s in all_sents:
        key = s["text"].lower()[:100]
        if key in seen_per_bucket[s["canonical_field"]]:
            continue
        seen_per_bucket[s["canonical_field"]].add(key)
        by_bucket[s["canonical_field"]].append(s)

    index = {
        "schema_version": 2,
        "total_reviewers_used": len(reviews),
        "total_sentences": sum(len(v) for v in by_bucket.values()),
        "by_canonical_bucket": {
            b: len(by_bucket.get(b, [])) for b in BUCKET_ORDER
        },
        "by_canonical_bucket_x_venue": {},
        "by_raw_field": {},
        "sentences": [],
    }
    for b in BUCKET_ORDER:
        per_venue = defaultdict(int)
        for s in by_bucket.get(b, []):
            per_venue[s["venue"]] += 1
        index["by_canonical_bucket_x_venue"][b] = dict(per_venue)
    for s in all_sents:
        index["by_raw_field"][s["field"]] = (
            index["by_raw_field"].get(s["field"], 0) + 1)
    for b in BUCKET_ORDER:
        index["sentences"].extend(by_bucket.get(b, []))

    DERIVED_ROOT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(index, indent=2, ensure_ascii=False))

    with OUT_TXT.open("w") as f:
        f.write(f"# Sentence templates by canonical field, extracted from "
                f"{len(reviews)} GPTZero-verified-human reviewer JSONs.\n")
        f.write(f"# Source: review_corpus/source/ + processed/human_reviews.json\n")
        f.write(f"# Total unique sentences: {index['total_sentences']}\n\n")
        for b in BUCKET_ORDER:
            items = by_bucket.get(b, [])
            if not items:
                continue
            f.write(f"\n========== {b} ({len(items)}) ==========\n")
            for s in items:
                f.write(f"{s['text']}\n")
    return index


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--include_ai_dropped", action="store_true")
    args = p.parse_args()
    idx = extract(only_human_kept=not args.include_ai_dropped)
    print(f"\nwrote:")
    print(f"  {OUT_JSON}  ({OUT_JSON.stat().st_size} bytes)")
    print(f"  {OUT_TXT}   ({OUT_TXT.stat().st_size} bytes)")
    print(f"\ncanonical bucket sizes: {idx['by_canonical_bucket']}")
    print(f"per venue x bucket:")
    for b, vs in idx["by_canonical_bucket_x_venue"].items():
        print(f"  {b}: {dict(sorted(vs.items()))}")
    print(f"\nraw field counts (top 10):")
    sorted_raw = sorted(idx["by_raw_field"].items(),
                        key=lambda kv: -kv[1])[:10]
    for k, n in sorted_raw:
        print(f"  {k}: {n}")
