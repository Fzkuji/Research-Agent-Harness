"""Sample a per-call subset of the human-reviewer template pool.

Why sampling instead of always passing the full pool:
  - The full sentence_templates.txt is the union of every human reviewer's
    句子. Generating 100 reviews against that fixed pool produces 100 reviews
    that all sound like the *average* of the pool — same hedge frequency,
    same opener distribution, same complaint pattern.
  - Reviewer-grouped sampling preserves the within-reviewer coherence: each
    reviewer has their own "voice" (hedges, openers, length preferences).
    Picking a random subset of K reviewers per call gives the LLM a tighter
    voice signal that varies between calls.

Two sampling modes (use --mode):
  1. by_reviewer — pick K random reviewers, take ALL their sentences. Best
     for "voice coherence per call". Default.
  2. by_sentence — flat random sample of N sentences across all reviewers,
     proportional to bucket sizes. Best when corpus is small / by_reviewer
     would yield too few sentences per bucket.

Output: same format as extract_sentence_templates.py — `## SECTION`
headers + verbatim lines. Drop-in replacement for the full file.

Usage:
  # Pick a fresh batch each call (recommended for review_paper.py stage 1):
  python -m research_harness.stages.review.review_corpus.pipeline.sample_templates \\
      --mode by_reviewer --num_reviewers 8 --out /tmp/sentence_templates_subset.txt

  # Reproducible batches (testing / debugging):
  python -m research_harness.stages.review.review_corpus.pipeline.sample_templates \\
      --mode by_reviewer --num_reviewers 8 --seed 42 \\
      --out /tmp/sentence_templates_subset.txt

  # Show what got picked without writing:
  python -m research_harness.stages.review.review_corpus.pipeline.sample_templates \\
      --mode by_reviewer --num_reviewers 8 --dry_run
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DERIVED_ROOT = _HERE.parent / "processed"
CORPUS_PATH = DERIVED_ROOT / "human_reviews.json"
DEFAULT_OUT = DERIVED_ROOT / "sentence_templates_subset.txt"


# Same filter / classify as extract_sentence_templates.py — duplicated here
# so the sampler is self-contained. If you change one, change the other.
def _looks_useful(s: str) -> bool:
    if len(s) < 25 or len(s) > 350:
        return False
    if s.count("[") > 2 or s.count("(") > 4:
        return False
    alpha = [c for c in s if c.isalpha()]
    if alpha and sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.4:
        return False
    return True


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


def _classify(text: str, *, is_first: bool, is_last: bool) -> list[str]:
    tags: list[str] = []
    if text.rstrip().endswith("?"):
        tags.append("QUESTION")
    if _JUDGMENT_RE.search(text):
        tags.append("HEDGE")
    if _TRANSITION_RE.match(text):
        tags.append("TRANSITION")
    if _WEAKNESS_RE.search(text) and "QUESTION" not in tags:
        tags.append("WEAKNESS")
    if (_STRENGTH_RE.search(text) and "WEAKNESS" not in tags
            and "QUESTION" not in tags):
        tags.append("STRENGTH")
    if is_first:
        tags.append("SUMMARY")
    if is_last:
        tags.append("CLOSING")
    if not tags:
        tags.append("GENERIC")
    return tags


_BUCKET_ORDER = ["SUMMARY", "STRENGTH", "WEAKNESS", "TRANSITION",
                 "HEDGE", "QUESTION", "CLOSING", "GENERIC"]


def _explode_to_sentences(reviews: list[dict]) -> list[dict]:
    """Each output: {reviewer_key, text, tags}."""
    out: list[dict] = []
    for r in reviews:
        rkey = (r.get("venue"), r.get("year"), r.get("forum_id"),
                r.get("reviewer"))
        text = r.get("text") or ""
        text = re.sub(r"https?://\S+", "", text)
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
                 if s.strip()]
        n = len(sents)
        for i, s in enumerate(sents):
            if not _looks_useful(s):
                continue
            tags = _classify(s, is_first=i < 2, is_last=i >= n - 2)
            out.append({"reviewer_key": rkey, "text": s, "tags": tags})
    return out


def sample_by_reviewer(reviews: list[dict], *, num_reviewers: int,
                       seed: int | None) -> tuple[list[dict], list[tuple]]:
    """Pick K random reviewers, return all their useful sentences.

    Returns (sentences, picked_reviewer_keys).
    """
    rng = random.Random(seed)
    by_reviewer: dict[tuple, list[dict]] = defaultdict(list)
    for r in reviews:
        rkey = (r.get("venue"), r.get("year"), r.get("forum_id"),
                r.get("reviewer"))
        by_reviewer[rkey].append(r)
    all_keys = list(by_reviewer.keys())
    if num_reviewers > len(all_keys):
        print(f"warning: requested {num_reviewers} reviewers but only "
              f"{len(all_keys)} available; using all of them",
              file=sys.stderr)
        picked = all_keys
    else:
        picked = rng.sample(all_keys, num_reviewers)
    chosen_reviews = [r for k in picked for r in by_reviewer[k]]
    sents = _explode_to_sentences(chosen_reviews)
    return sents, picked


def sample_by_sentence(reviews: list[dict], *, total: int,
                       seed: int | None) -> tuple[list[dict], list[tuple]]:
    """Flat random sample of N sentences across the whole corpus.

    Returns (sentences, [] — no per-reviewer grouping).
    """
    rng = random.Random(seed)
    all_sents = _explode_to_sentences(reviews)
    if total >= len(all_sents):
        return all_sents, []
    return rng.sample(all_sents, total), []


def _bucket_and_dedup(sentences: list[dict]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for s in sentences:
        for tag in s["tags"]:
            key = s["text"].lower()[:100]
            if key in seen[tag]:
                continue
            seen[tag].add(key)
            buckets[tag].append(s["text"])
    return buckets


def write_subset(buckets: dict[str, list[str]], out_path: Path, *,
                 source_meta: dict) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open("w") as f:
        f.write("# Real human reviewer sentences — sampled subset.\n")
        f.write(f"# Source: {source_meta.get('source_path', '?')}\n")
        f.write(f"# Sampling: mode={source_meta.get('mode')}, "
                f"seed={source_meta.get('seed')}, "
                f"picked_reviewers={source_meta.get('num_reviewers_picked')}\n")
        f.write(f"# Use these as sentence-skeleton templates: keep the "
                f"syntactic frame, replace specific paper content with "
                f"target-paper facts.\n\n")
        for tag in _BUCKET_ORDER:
            if tag not in buckets or not buckets[tag]:
                continue
            items = buckets[tag]
            total += len(items)
            f.write(f"\n========== {tag} ({len(items)}) ==========\n")
            for s in items:
                s = re.sub(r"\s+", " ", s).strip()
                f.write(f"{s}\n")
    return total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sample_templates")
    p.add_argument("--mode", choices=("by_reviewer", "by_sentence"),
                   default="by_reviewer",
                   help="by_reviewer (default): pick K reviewers, take all "
                        "their sentences (preserves within-reviewer voice). "
                        "by_sentence: flat random N sentences across pool.")
    p.add_argument("--num_reviewers", type=int, default=10,
                   help="(by_reviewer mode) number of reviewers to sample. "
                        "Each reviewer contributes ~5-25 sentences.")
    p.add_argument("--total", type=int, default=300,
                   help="(by_sentence mode) total sentences to sample.")
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed for reproducibility. Omit for fresh "
                        "random sample each call.")
    p.add_argument("--out", default=str(DEFAULT_OUT),
                   help=f"Output path. Default {DEFAULT_OUT}")
    p.add_argument("--corpus", default=str(CORPUS_PATH),
                   help=f"Source corpus JSON. Default {CORPUS_PATH}")
    p.add_argument("--dry_run", action="store_true",
                   help="Print picked reviewers + bucket counts but do not "
                        "write a file.")
    args = p.parse_args(argv)

    corpus_path = Path(args.corpus).expanduser()
    if not corpus_path.is_file():
        print(f"error: corpus missing: {corpus_path}. "
              f"Run filter_with_gptzero.py first.", file=sys.stderr)
        return 2
    reviews = json.loads(corpus_path.read_text())
    if not reviews:
        print("error: corpus is empty", file=sys.stderr)
        return 2

    if args.mode == "by_reviewer":
        sents, picked = sample_by_reviewer(
            reviews, num_reviewers=args.num_reviewers, seed=args.seed)
    else:
        sents, picked = sample_by_sentence(
            reviews, total=args.total, seed=args.seed)

    buckets = _bucket_and_dedup(sents)

    if args.dry_run:
        print(f"mode={args.mode} seed={args.seed}")
        if picked:
            print(f"picked {len(picked)} reviewers:")
            for k in picked:
                print(f"  {k[0]}/{k[1]} forum={k[2]} reviewer={k[3]}")
        print(f"\nbucket counts:")
        for tag in _BUCKET_ORDER:
            n = len(buckets.get(tag, []))
            if n:
                print(f"  {tag}: {n}")
        print(f"\ntotal unique sentences: "
              f"{sum(len(v) for v in buckets.values())}")
        return 0

    out_path = Path(args.out).expanduser()
    total = write_subset(buckets, out_path, source_meta={
        "source_path": str(corpus_path),
        "mode": args.mode,
        "seed": args.seed,
        "num_reviewers_picked": len(picked) if picked else None,
    })
    print(f"wrote {out_path}")
    print(f"  buckets: {dict((k, len(v)) for k, v in buckets.items() if v)}")
    print(f"  total sentences: {total}")
    if picked:
        print(f"  reviewers picked: {len(picked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
