"""Extract verbatim human reviewer sentences as v6 prompt templates.

Reads:  processed/human_reviews.json (52 GPTZero-verified human reviews)
Writes: processed/sentence_templates.txt (categorized verbatim sentences)

The output file is consumed by review_paper.py (and review_paper_grounded.py)
as a forced-skeleton pool: the LLM is required to write each review
sentence as a minimal modification of one of these templates.

Why this is a separate extractor (vs. mine_phrases.py):
  - mine_phrases produces aggregate statistics (n-gram frequencies,
    sentence-length percentiles) — useful for analysis but proven
    ineffective as a generation constraint (see LESSONS.md, v5 result).
  - This script preserves complete sentences verbatim, which is the
    only mechanism that actually moves the LLM's token distribution
    (see LESSONS.md, v6 result: GPTZero 0% AI).

Categories produced:
  SUMMARY, STRENGTH, WEAKNESS, TRANSITION, HEDGE, QUESTION, CLOSING,
  GENERIC. A sentence may appear in multiple categories.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DERIVED_ROOT = _HERE.parent / "processed"
CORPUS_PATH = DERIVED_ROOT / "human_reviews.json"
OUT_PATH = DERIVED_ROOT / "sentence_templates.txt"


# Sentence-quality filters: drop URLs, very short fragments, citation-
# heavy lines, all-caps headings.
def _looks_useful(s: str) -> bool:
    if len(s) < 25 or len(s) > 350:
        return False
    if s.count("[") > 2 or s.count("(") > 4:
        return False
    alpha = [c for c in s if c.isalpha()]
    if alpha and sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.4:
        return False
    return True


# Functional classification: a sentence may carry multiple tags.
_JUDGMENT_RE = re.compile(
    r"\b(I (?:think|find|feel|like|liked|enjoyed|appreciate|believe|"
    r"am|'m|wonder|suspect|worry|noticed|disagree|agree|"
    r"would (?:say|argue|expect|prefer|like|love|love to))|"
    r"in my (?:opinion|view|reading)|to me,?|"
    r"my (?:concern|main|biggest)|perhaps|arguably)\b",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(
    r"^(However|Although|Though|That said|Still|Yet|"
    r"On the other hand|Unfortunately|Specifically|"
    r"In particular|For example|For instance|"
    r"Moreover|Furthermore|First|Second|Third|Finally|"
    r"In addition|Importantly|Notably|Interestingly)[,\s]",
)
_WEAKNESS_RE = re.compile(
    r"\b(concern|issue|problem|weakness|drawback|limitation|"
    r"unclear|insufficient|missing|lack|not convincing|"
    r"weak(ness)?|fail(s|ed)?|incorrect|misleading|"
    r"would (?:argue|like to see|like the authors|push back)|"
    r"however|unfortunately)\b",
    re.IGNORECASE,
)
_STRENGTH_RE = re.compile(
    r"\b(well[-\s]written|well[-\s]motivated|interesting|novel|"
    r"elegant|impressive|strong contribution|appreciate|like(d)?|"
    r"enjoyed|clear(ly)?|reasonable|practical|sound|solid)\b",
    re.IGNORECASE,
)


def _classify(sent: dict) -> list[str]:
    s = sent["text"]
    tags: list[str] = []
    if s.rstrip().endswith("?"):
        tags.append("QUESTION")
    if _JUDGMENT_RE.search(s):
        tags.append("HEDGE")
    if _TRANSITION_RE.match(s):
        tags.append("TRANSITION")
    if _WEAKNESS_RE.search(s) and "QUESTION" not in tags:
        tags.append("WEAKNESS")
    if (_STRENGTH_RE.search(s) and "WEAKNESS" not in tags
            and "QUESTION" not in tags):
        tags.append("STRENGTH")
    if sent["is_first"]:
        tags.append("SUMMARY")
    if sent["is_last"]:
        tags.append("CLOSING")
    if not tags:
        tags.append("GENERIC")
    return tags


# Per-category caps to keep the prompt context manageable.
_CAPS = {
    "SUMMARY": 30, "STRENGTH": 30, "WEAKNESS": 50, "TRANSITION": 40,
    "HEDGE": 30, "QUESTION": 40, "CLOSING": 20, "GENERIC": 60,
}


def extract() -> dict[str, int]:
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(
            f"{CORPUS_PATH} missing. Run filter_with_gptzero.py first.")
    reviews = json.loads(CORPUS_PATH.read_text())

    # Flatten to sentences with positional info (for SUMMARY / CLOSING).
    sentences: list[dict] = []
    for r in reviews:
        text = r.get("text") or ""
        # Strip URLs (citations, OpenReview links).
        text = re.sub(r"https?://\S+", "", text)
        sents_raw = re.split(r"(?<=[.!?])\s+", text)
        sents = [s.strip() for s in sents_raw if s.strip()]
        n = len(sents)
        for i, s in enumerate(sents):
            sentences.append({
                "text": s, "is_first": i < 2, "is_last": i >= n - 2,
            })

    # Bucket by tag.
    buckets: dict[str, list[str]] = defaultdict(list)
    for sent in sentences:
        if not _looks_useful(sent["text"]):
            continue
        for tag in _classify(sent):
            buckets[tag].append(sent["text"])

    # Dedup within each bucket (case-insensitive prefix match).
    for tag in buckets:
        seen: set[str] = set()
        unique: list[str] = []
        for s in buckets[tag]:
            key = s.lower()[:100]
            if key not in seen:
                seen.add(key)
                unique.append(s)
        buckets[tag] = unique

    # Write out, capping each bucket and normalizing whitespace.
    DERIVED_ROOT.mkdir(parents=True, exist_ok=True)
    bucket_sizes: dict[str, int] = {}
    with OUT_PATH.open("w") as f:
        f.write(f"# Real human reviewer sentences extracted verbatim from "
                f"{len(reviews)} GPTZero-verified-human reviews.\n")
        f.write(f"# Source: {CORPUS_PATH.name}\n")
        f.write(f"# Use these as sentence-skeleton templates: keep the "
                f"syntactic frame, replace specific paper content with "
                f"target-paper facts.\n\n")
        for tag in ["SUMMARY", "STRENGTH", "WEAKNESS", "TRANSITION", "HEDGE",
                    "QUESTION", "CLOSING", "GENERIC"]:
            if tag not in buckets:
                continue
            items = buckets[tag][:_CAPS.get(tag, 50)]
            bucket_sizes[tag] = len(items)
            f.write(f"\n========== {tag} ({len(items)}) ==========\n")
            for s in items:
                s_clean = re.sub(r"\s+", " ", s).strip()
                f.write(f"{s_clean}\n")

    return bucket_sizes


if __name__ == "__main__":
    sizes = extract()
    print(f"wrote {OUT_PATH}")
    print(f"  buckets: {dict(sorted(sizes.items()))}")
    print(f"  total kept: {sum(sizes.values())}")
