"""Venue-aware sample of sentence templates + complete reviewer few-shots.

Replaces the old sample_templates.py (kept on disk for back-compat).

Logic:
  1. User specifies a target venue.
  2. We look up the venue's form fields (canonical bucket per field).
  3. For each text field of the target venue:
     - If target venue has its own corpus AND that exact field exists in
       it → sample sentences from target venue / that exact field
       (preserves the venue's own phrasing).
     - Else → fall back: pull sentences from ANY venue whose corpus
       has the same canonical bucket (e.g. AAAI weaknesses → use any
       venue's WEAKNESSES bucket).
  4. Also pick 1-2 complete reviewer JSONs as few-shot examples
     (same venue if available, else cross-venue).

Input:
  - processed/sentence_templates_by_field.json (built by extract_by_field.py)
  - source/<venue>/<year>/<forum>/reviewer_*.json (for few-shots)

Output:
  - dict with structure:
    {
      "venue":           "ACM Multimedia (ACM MM)",  # canonical
      "fallback_used":   True,                       # bool
      "fields": {                                    # by target venue's form
        "summary":           ["sent1", "sent2", ...],
        "strengths":         [...],
        "weaknesses":        [...],
        "review":            [...],                  # ACM MM long prose
        "fit_justification": [...],                  # ACM MM-specific
      },
      "few_shot_reviewers": [
        { full reviewer JSON 1 },
        { full reviewer JSON 2 }
      ],
      "sample_meta": {
        "num_reviewers_per_venue_field": K,
        "seed": int | None,
        "target_venue_in_corpus": bool,
      }
    }
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DERIVED_ROOT = _HERE.parent / "processed"
RAW_ROOT = _HERE.parent / "source"
INDEX_PATH = DERIVED_ROOT / "sentence_templates_by_field.json"


# Per-venue form: which fields the venue's review form actually has,
# and which canonical bucket each maps to. Used for both:
#   (a) target venue field discovery — what fields to populate when
#       the user asks for a review of this venue
#   (b) cross-venue fallback — when target has no corpus, find sentences
#       from ANY venue whose canonical bucket matches
#
# For venues NOT on OpenReview (AAAI, CVPR, ACM MM), we still list the
# form here so the sampler knows what fields to produce, even though it
# will always fall back to cross-venue sourcing.
VENUE_FORM: dict[str, dict[str, str]] = {
    # ---- NLP / language ----
    "COLM (Conference on Language Modeling)": {
        "summary":              "SUMMARY",
        "reasons_to_accept":    "STRENGTHS",
        "reasons_to_reject":    "WEAKNESSES",
        "questions_to_authors": "QUESTIONS",
    },
    "ACL Rolling Review (ARR)": {
        "summary":              "SUMMARY",
        "strengths":            "STRENGTHS",
        "weaknesses":           "WEAKNESSES",
        "questions_for_authors": "QUESTIONS",
    },
    # ---- ML / generic ----
    "NeurIPS": {
        "summary":      "SUMMARY",
        "strengths":    "STRENGTHS",
        "weaknesses":   "WEAKNESSES",
        "questions":    "QUESTIONS",
        "limitations":  "WEAKNESSES",
    },
    "ICLR": {
        "summary":      "SUMMARY",
        "strengths":    "STRENGTHS",
        "weaknesses":   "WEAKNESSES",
        "questions":    "QUESTIONS",
        "limitations":  "WEAKNESSES",
    },
    "ICML": {
        "summary":      "SUMMARY",
        "strengths":    "STRENGTHS",
        "weaknesses":   "WEAKNESSES",
        "questions":    "QUESTIONS",
    },
    # ---- Vision (no OpenReview corpus) ----
    "CVPR / ICCV / ECCV (CVF)": {
        "summary":      "SUMMARY",
        "strengths":    "STRENGTHS",
        "weaknesses":   "WEAKNESSES",
        "questions":    "QUESTIONS",
    },
    # ---- Multimedia (no OpenReview corpus) ----
    "ACM Multimedia (ACM MM)": {
        "summary":            "SUMMARY",
        "strengths":          "STRENGTHS",
        "weaknesses":         "WEAKNESSES",
        "review":             "FULL",          # long prose
        "fit_justification":  "FULL",
    },
    "ACM MM Asia": {
        "summary":            "SUMMARY",
        "strengths":          "STRENGTHS",
        "weaknesses":         "WEAKNESSES",
        "review":             "FULL",
        "fit_justification":  "FULL",
    },
    # ---- AI generic (no OpenReview corpus) ----
    "AAAI": {
        "summary":      "SUMMARY",
        "strengths":    "STRENGTHS",
        "weaknesses":   "WEAKNESSES",
        "questions":    "QUESTIONS",
    },
    # ---- Default fallback for unknown venues ----
    "_default": {
        "summary":      "SUMMARY",
        "strengths":    "STRENGTHS",
        "weaknesses":   "WEAKNESSES",
        "questions":    "QUESTIONS",
    },
}


def _resolve_venue(venue: str) -> tuple[str, dict[str, str]]:
    """Resolve user-given venue name to canonical name + form."""
    try:
        from research_harness.references.venue_scoring import get_venue_spec
        spec = get_venue_spec(venue)
        canonical = spec.name
    except Exception:
        canonical = venue

    if canonical in VENUE_FORM:
        return canonical, VENUE_FORM[canonical]
    # Try a loose match
    for k, form in VENUE_FORM.items():
        if k.lower().startswith(canonical.lower()):
            return canonical, form
    return canonical, VENUE_FORM["_default"]


def _venue_in_corpus(canonical_venue: str, sentences: list[dict]) -> bool:
    """Check whether the target venue has any sentences in the corpus."""
    short = canonical_venue.split(" ")[0]   # "NeurIPS", "ICLR", "COLM", "ACM"
    for s in sentences:
        if (s["venue"] == canonical_venue
                or s["venue"] == short
                or s["venue"].startswith(short)):
            return True
    return False


def _load_reviewer_jsons() -> list[dict]:
    """Load all on-disk reviewer JSONs (for few-shot picking)."""
    out = []
    if not RAW_ROOT.is_dir():
        return out
    for venue_dir in sorted(p for p in RAW_ROOT.iterdir() if p.is_dir()):
        for year_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
            for forum_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
                for rpath in sorted(forum_dir.glob("reviewer_*.json")):
                    try:
                        d = json.loads(rpath.read_text())
                        # Only include if marked human by GPTZero
                        score = d.get("ai_score") or {}
                        if (score.get("status") == "ok"
                                and score.get("human_pct") is not None
                                and score["human_pct"] >= 80):
                            out.append(d)
                    except Exception:
                        continue
    return out


def sample_for_venue(*, venue: str, num_reviewers: int = 10,
                     few_shot_count: int = 2,
                     seed: int | None = None) -> dict:
    """Build a venue-aware template sample.

    Args:
      venue: target venue name (any alias accepted; resolved via
             venue_scoring.py).
      num_reviewers: when sampling target-venue reviewers, take this many.
                     For cross-venue fallback, ~num_reviewers * 5 sentences
                     are sampled per field instead.
      few_shot_count: how many full reviewer JSONs to attach as few-shot.
      seed: random seed for reproducibility (None = fresh random).
    """
    if not INDEX_PATH.is_file():
        raise FileNotFoundError(
            f"{INDEX_PATH} missing. Run extract_by_field.py first.")

    canonical_venue, form = _resolve_venue(venue)
    index = json.loads(INDEX_PATH.read_text())
    sentences: list[dict] = index["sentences"]

    in_corpus = _venue_in_corpus(canonical_venue, sentences)
    rng = random.Random(seed)

    # Group sentences by venue/raw_field and by canonical bucket.
    by_venue_field: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_canonical: dict[str, list[dict]] = defaultdict(list)
    for s in sentences:
        by_venue_field[(s["venue"], s["field"])].append(s)
        by_canonical[s["canonical_field"]].append(s)

    out_fields: dict[str, list[str]] = {}
    field_sources: dict[str, str] = {}   # raw_field → "exact"|"same_venue"|"cross_venue"
    fallback_used = False
    short = canonical_venue.split(" ")[0]
    for raw_field, canonical in form.items():
        # 1) Target-venue + exact field name (v2 schema preferred path).
        own = []
        if in_corpus:
            for v_key in (canonical_venue, short):
                own.extend(by_venue_field.get((v_key, raw_field), []))

        source_kind = "exact"
        if not own and in_corpus:
            # 2) Same target-venue, fall back to whatever raw field maps
            #    to the same canonical bucket. Useful for v1 schema data
            #    where the venue's specific field names haven't been split.
            same_canon_in_venue = [
                s for s in sentences
                if (s["venue"] == canonical_venue or s["venue"] == short
                    or (s["venue"] or "").startswith(short))
                and s["canonical_field"] == canonical
            ]
            if same_canon_in_venue:
                own = same_canon_in_venue
                source_kind = "same_venue_canonical"

        if own:
            # Reviewer-based sampling: pick K reviewers, take all their
            # sentences in this canonical bucket / field. Preserves voice.
            reviewers_with_field = list({s["reviewer"] for s in own})
            picked_revs = set(rng.sample(
                reviewers_with_field,
                min(num_reviewers, len(reviewers_with_field))))
            chosen = [s["text"] for s in own
                      if s["reviewer"] in picked_revs]
            out_fields[raw_field] = chosen
            field_sources[raw_field] = source_kind
        else:
            # 3) Cross-venue fallback by canonical bucket.
            pool = by_canonical.get(canonical, [])
            if pool:
                k = min(num_reviewers * 5, len(pool))
                chosen_sents = rng.sample(pool, k)
                out_fields[raw_field] = [s["text"] for s in chosen_sents]
                field_sources[raw_field] = "cross_venue"
                fallback_used = True
            else:
                out_fields[raw_field] = []
                field_sources[raw_field] = "empty"

    # Few-shot: complete reviewer JSONs.
    all_reviewers = _load_reviewer_jsons()
    short = canonical_venue.split(" ")[0]
    same_venue = [r for r in all_reviewers
                  if r.get("venue") == canonical_venue
                  or r.get("venue") == short
                  or (r.get("venue") or "").startswith(short)]
    if len(same_venue) >= few_shot_count:
        few_shot = rng.sample(same_venue, few_shot_count)
    elif len(all_reviewers) >= few_shot_count:
        few_shot = rng.sample(all_reviewers, few_shot_count)
    else:
        few_shot = all_reviewers

    return {
        "venue": canonical_venue,
        "fallback_used": fallback_used,
        "fields": out_fields,
        "field_sources": field_sources,
        "few_shot_reviewers": few_shot,
        "sample_meta": {
            "num_reviewers_per_venue_field": num_reviewers,
            "few_shot_count": few_shot_count,
            "seed": seed,
            "target_venue_in_corpus": in_corpus,
            "form_field_to_canonical": form,
        },
    }


def render_for_prompt(sample: dict) -> str:
    """Render sample as the markdown text we paste into the codex prompt.

    Layout: each form field is a `## <FIELD_NAME>` section listing the
    sampled sentences as bullets; few-shot reviewers come last as fenced
    JSON blocks.
    """
    lines: list[str] = []
    lines.append(f"# Sentence templates for {sample['venue']}")
    lines.append(f"# (fallback_used={sample['fallback_used']}, "
                 f"target_venue_in_corpus="
                 f"{sample['sample_meta']['target_venue_in_corpus']}, "
                 f"seed={sample['sample_meta']['seed']})")
    lines.append("")
    lines.append("Each section below is one field of the target review form. "
                 "Every sentence YOU write in that field MUST reuse the "
                 "syntactic skeleton of one of the listed templates. Replace "
                 "the paper-specific nouns/numbers; do not invent new "
                 "transitions, hedges, or framing devices.")
    lines.append("")
    for raw_field, sents in sample["fields"].items():
        lines.append(f"## {raw_field}  ({len(sents)} templates)")
        if not sents:
            lines.append("(no templates available — use the few-shot examples "
                         "below to infer the style)")
            continue
        for s in sents:
            lines.append(f"- {s}")
        lines.append("")

    # Few-shot complete reviewers.
    lines.append("# Complete reviewer examples (for overall structure / tone)")
    lines.append("")
    for i, r in enumerate(sample["few_shot_reviewers"], 1):
        lines.append(f"## Example reviewer {i} "
                     f"(venue={r.get('venue')} year={r.get('year')} "
                     f"forum={r.get('forum_id')} reviewer={r.get('reviewer')})")
        # Show the structured fields cleanly
        fields = (r.get("review_fields") if r.get("schema_version") == 2
                  else None)
        if fields:
            for fname, ftext in fields.items():
                lines.append(f"### {fname}")
                lines.append(ftext)
                lines.append("")
        else:
            # v1 fallback
            for k in ("summary", "strengths", "weaknesses", "full_review"):
                v = (r.get(k) or "").strip()
                if not v:
                    continue
                lines.append(f"### {k}")
                lines.append(v)
                lines.append("")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(prog="sample_for_venue")
    p.add_argument("--venue", required=True,
                   help='Target venue name. Aliases handled (e.g. '
                        '"NeurIPS"/"nips", "ACM Multimedia"/"acm mm").')
    p.add_argument("--num_reviewers", type=int, default=10,
                   help="Number of reviewers to sample per field when "
                        "target venue has its own corpus. "
                        "Default 10.")
    p.add_argument("--few_shot_count", type=int, default=2,
                   help="Complete reviewer JSONs to attach. Default 2.")
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed (omit for fresh random each call).")
    p.add_argument("--out", default=None,
                   help="Write rendered prompt to this path (default: stdout).")
    p.add_argument("--dry_run", action="store_true",
                   help="Print summary stats only.")
    args = p.parse_args()

    sample = sample_for_venue(
        venue=args.venue,
        num_reviewers=args.num_reviewers,
        few_shot_count=args.few_shot_count,
        seed=args.seed,
    )
    if args.dry_run:
        print(f"venue (canonical):  {sample['venue']}")
        print(f"target in corpus:   "
              f"{sample['sample_meta']['target_venue_in_corpus']}")
        print(f"fallback used:      {sample['fallback_used']}")
        print(f"fields produced:")
        for f, ss in sample["fields"].items():
            src = sample["field_sources"].get(f, "?")
            print(f"  {f:24} {len(ss):>4} templates  [{src}]")
        print(f"few-shot reviewers: {len(sample['few_shot_reviewers'])} "
              f"({[(r.get('venue'), r.get('year'), r.get('reviewer')) for r in sample['few_shot_reviewers']]})")
    else:
        rendered = render_for_prompt(sample)
        if args.out:
            Path(args.out).expanduser().write_text(rendered)
            print(f"wrote {args.out} ({len(rendered)} chars)")
        else:
            print(rendered)
