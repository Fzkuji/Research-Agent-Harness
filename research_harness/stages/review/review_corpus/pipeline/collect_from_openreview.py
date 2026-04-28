"""Pull review content + paper metadata from OpenReview into a corpus.

Output layout:
    stages/review/review_corpus/source/<venue>/<year>/<forum_id>/reviewer_<id>.json

The on-disk format is documented in review_corpus/SCHEMA.md (v2 schema).
Briefly:
  - schema_version, venue, year, forum_id, reviewer
  - paper: {title, authors, abstract, keywords, decision, openreview_url}
  - review_fields: {<original_field_name>: text}  ← all venue-specific keys
  - review_metadata: {rating, confidence, sub_dim_scores, ...}
  - source: {openreview_field_keys, openreview_invitation, api_version,
             collected_at}
  - ai_score: filled in later by filter_with_gptzero.py

This is the *raw* dump. GPTZero filtering and dedup live in a separate stage.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import time
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
RAW_ROOT = os.path.join(_HERE, "..", "source")        # raw reviewer JSON
DERIVED_ROOT = os.path.join(_HERE, "..", "processed")      # collection_summary.json


def _http_json(url: str, *, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "research-harness/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _qs(params: dict) -> str:
    return urllib.parse.urlencode(params, doseq=True)


# ---------------------------------------------------------------------------
# Venue-specific listing — different invitations / API versions.
# ---------------------------------------------------------------------------

def list_oral_neurips_v2(year: int, *, limit: int = 30) -> list[dict]:
    """NeurIPS 2023+ uses V2 API. Returns Oral submissions only."""
    qs = _qs({
        "content.venueid": f"NeurIPS.cc/{year}/Conference",
        "limit": 200,
    })
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    notes = data.get("notes", [])
    orals = [
        n for n in notes
        if (n.get("content", {}).get("venue", {}).get("value", "") or "")
           .lower().endswith("oral")
    ]
    return orals[:limit]


def list_oral_colm_v2(year: int, *, limit: int = 30) -> list[dict]:
    """COLM uses V2 API. The venue field on COLM 2024 is just 'COLM'
    (no oral/poster split), so we return arbitrary submissions; the
    higher-quality filter is GPTZero downstream."""
    qs = _qs({
        "content.venueid": f"colmweb.org/COLM/{year}/Conference",
        "limit": 200,
    })
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    return data.get("notes", [])[:limit]


def list_oral_iclr(year: int, *, limit: int = 30,
                   nlp_keywords: tuple[str, ...] = (
                       "language model", "llm", "transformer", "in-context",
                       "instruction", "prompt", "tokeniz", "attention",
                       "alignment", "rlhf", "dpo", "translation",
                       "summariz", "question answering", "reasoning",
                   )) -> list[dict]:
    """ICLR — 2020-2022 use V1, 2023+ use V2. Filter to Oral + NLP-flavored."""
    if year >= 2024:
        qs = _qs({
            "content.venueid": f"ICLR.cc/{year}/Conference",
            "limit": 1000,
        })
        url = f"https://api2.openreview.net/notes?{qs}"
        data = _http_json(url)
        notes = data.get("notes", [])
        getval = lambda n, k: (n.get("content", {}).get(k, {}) or {}).get("value", "")
    else:
        qs = _qs({
            "invitation": f"ICLR.cc/{year}/Conference/-/Blind_Submission",
            "content.venue": f"ICLR {year} Oral",
            "limit": 1000,
        })
        url = f"https://api.openreview.net/notes?{qs}"
        data = _http_json(url)
        notes = data.get("notes", [])
        getval = lambda n, k: n.get("content", {}).get(k, "")

    out = []
    for n in notes:
        venue = (getval(n, "venue") or "").lower()
        # Year >= 2023: still need to drop posters; year < 2023: already filtered.
        if year >= 2024 and not venue.endswith("oral"):
            continue
        title = (getval(n, "title") or "").lower()
        abstract = (getval(n, "abstract") or "").lower()
        text = title + " " + abstract
        if any(k in text for k in nlp_keywords):
            out.append(n)
    return out[:limit]


# ---------------------------------------------------------------------------
# Broader-coverage listers — used when growing the corpus past oral-only.
# Reject and poster reviews are essential for a richer WEAKNESS / QUESTION
# pool: oral reviews are mostly "praise + minor concerns", reject reviews
# carry the long-form critical sentence patterns the LLM otherwise has to
# invent (and gets caught by the AI detector).
# ---------------------------------------------------------------------------

def list_all_neurips_v2(year: int, *, limit: int = 30,
                        decisions: tuple[str, ...] = (
                            "oral", "spotlight", "poster", "reject"
                        )) -> list[dict]:
    """NeurIPS V2 (2023+). Returns submissions with ANY of the listed decision
    types. Defaults: oral + spotlight + poster + reject — the full corpus.
    Pass decisions=("reject",) to harvest only reject papers (more critical
    review prose).
    """
    qs = _qs({
        "content.venueid": f"NeurIPS.cc/{year}/Conference",
        "limit": 1000,
    })
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    notes = data.get("notes", [])
    decisions_lower = tuple(d.lower() for d in decisions)
    out = []
    for n in notes:
        venue = (n.get("content", {}).get("venue", {}).get("value", "")
                 or "").lower()
        # OpenReview venue strings look like: "NeurIPS 2024 oral",
        # "NeurIPS 2024 spotlight", "NeurIPS 2024 poster",
        # "NeurIPS 2024 Submitted" (= reject), etc. We match by suffix.
        if any(venue.endswith(d) or f" {d}" in venue for d in decisions_lower):
            out.append(n)
        elif "reject" in decisions_lower and (
                venue.endswith("submitted") or "withdrawn" in venue):
            # Heuristic: NeurIPS marks rejects as "Submitted" after the
            # decision is published.
            out.append(n)
    return out[:limit]


def list_all_neurips_v1(year: int, *, limit: int = 30,
                        decisions: tuple[str, ...] = (
                            "oral", "spotlight", "poster", "reject"
                        )) -> list[dict]:
    """NeurIPS V1 (2021-2022). Reviews are public, but submissions live on
    the V1 endpoint with invitation '.../Blind_Submission'. Venue strings:
    'NeurIPS 2021 Poster/Spotlight/Oral/Submitted'. Reviewer notes use the
    Official_Comment invitation with content key 'main_review' (handled by
    fetch_reviews_for_forum).
    """
    qs = _qs({
        "invitation": f"NeurIPS.cc/{year}/Conference/-/Blind_Submission",
        "limit": 1000,
    })
    data = _http_json(f"https://api.openreview.net/notes?{qs}")
    notes = data.get("notes", [])
    decisions_lower = tuple(d.lower() for d in decisions)
    out = []
    for n in notes:
        venue = (n.get("content", {}).get("venue", "") or "").lower()
        if any(venue.endswith(d) or f" {d}" in venue for d in decisions_lower):
            out.append(n)
        elif "reject" in decisions_lower and (
                venue.endswith("submitted") or "withdrawn" in venue):
            out.append(n)
    return out[:limit]


def list_all_automl_v2(year: int, *, limit: int = 30) -> list[dict]:
    """AutoML conference (V2). Small venue — return everything we can."""
    qs = _qs({
        "content.venueid": f"automl.cc/AutoML/{year}/Conference",
        "limit": 1000,
    })
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    return data.get("notes", [])[:limit]


def list_all_icml_v2(year: int, *, limit: int = 30,
                     decisions: tuple[str, ...] = (
                         "oral", "spotlight", "poster", "reject"
                     )) -> list[dict]:
    """ICML V2 (2024+). Venue strings: 'ICML 2025 oral/spotlight/poster',
    'ICML 2024 Oral/Spotlight/Poster' (case varies by year). 2025 also uses
    'spotlightposter' as a single token — matched via substring."""
    qs = _qs({
        "content.venueid": f"ICML.cc/{year}/Conference",
        "limit": 1000,
    })
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    notes = data.get("notes", [])
    decisions_lower = tuple(d.lower() for d in decisions)
    out = []
    for n in notes:
        venue = (n.get("content", {}).get("venue", {}).get("value", "")
                 or "").lower()
        if any(d in venue for d in decisions_lower):
            out.append(n)
    return out[:limit]


def list_all_uai_v2(year: int, *, limit: int = 30,
                    decisions: tuple[str, ...] = (
                        "oral", "spotlight", "poster", "reject"
                    )) -> list[dict]:
    """UAI V2 (2024+). Venue strings: 'UAI 2024 oral/spotlight/poster'."""
    qs = _qs({
        "content.venueid": f"auai.org/UAI/{year}/Conference",
        "limit": 1000,
    })
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    notes = data.get("notes", [])
    decisions_lower = tuple(d.lower() for d in decisions)
    out = []
    for n in notes:
        venue = (n.get("content", {}).get("venue", {}).get("value", "")
                 or "").lower()
        if any(d in venue for d in decisions_lower):
            out.append(n)
    return out[:limit]


def list_all_iclr(year: int, *, limit: int = 30,
                  decisions: tuple[str, ...] = (
                      "oral", "spotlight", "poster", "reject"
                  )) -> list[dict]:
    """ICLR — broader version of list_oral_iclr. Same V1/V2 split, no NLP
    topic filter, and lets you pull poster + reject too.
    """
    if year >= 2024:
        qs = _qs({
            "content.venueid": f"ICLR.cc/{year}/Conference",
            "limit": 1000,
        })
        url = f"https://api2.openreview.net/notes?{qs}"
        data = _http_json(url)
        notes = data.get("notes", [])
        getval = lambda n, k: (n.get("content", {}).get(k, {}) or {}).get("value", "")
    else:
        qs = _qs({
            "invitation": f"ICLR.cc/{year}/Conference/-/Blind_Submission",
            "limit": 1000,
        })
        url = f"https://api.openreview.net/notes?{qs}"
        data = _http_json(url)
        notes = data.get("notes", [])
        getval = lambda n, k: n.get("content", {}).get(k, "")

    decisions_lower = tuple(d.lower() for d in decisions)
    out = []
    venues_seen = 0
    for n in notes:
        venue = (getval(n, "venue") or "").lower()
        if venue:
            venues_seen += 1
        if any(venue.endswith(d) or f" {d}" in venue for d in decisions_lower):
            out.append(n)
        elif "reject" in decisions_lower and (
                venue.endswith("submitted") or "withdrawn" in venue):
            out.append(n)
    # ICLR 2018-2020 V1 has empty venue field for all notes — no decision
    # tag was stored. Fall back to "take everything" so early years still
    # contribute candidates.
    if not out and venues_seen == 0:
        out = list(notes)
    return out[:limit]


def list_all_colm_v2(year: int, *, limit: int = 30) -> list[dict]:
    """COLM V2. Same as list_oral_colm_v2 (COLM doesn't tag oral/poster on
    the venueid). Aliased for VENUE_PLAN consistency."""
    return list_oral_colm_v2(year, limit=limit)


def list_tmlr(year: int, *, limit: int = 30) -> list[dict]:
    """TMLR (Transactions on Machine Learning Research). Rolling journal,
    submissions accumulate under venueid='TMLR'. Returns the most recent
    `limit` accepted papers — TMLR API does not support per-year filter
    via venueid, so the year argument is informational only.

    Reviewer notes on TMLR forums use the Official_Comment invitation
    (not Official_Review), but our fetch_reviews_for_forum already
    accepts Official_Comment with /Reviewer_ signatures.
    """
    qs = _qs({"content.venueid": "TMLR", "limit": 200})
    data = _http_json(f"https://api2.openreview.net/notes?{qs}")
    notes = data.get("notes", [])
    # OpenReview returns newest-first by default; just take the head.
    return notes[:limit]


# ---------------------------------------------------------------------------
# Per-forum review pull. OpenReview field naming varies wildly across years
# and venues; we try a list of common keys and fall back to the longest text
# block we can find.
# ---------------------------------------------------------------------------

WEAKNESS_KEYS = (
    "weaknesses", "weaknesses_and_limitations",
    "weaknesses_and_questions", "cons", "limitations",
    # ARR / EMNLP / NAACL / COLM use these instead of "weaknesses".
    "reasons_to_reject",
)
STRENGTH_KEYS = (
    "strengths", "pros", "strengths_and_questions",
    "reasons_to_accept",
)
SUMMARY_KEYS = ("summary", "summary_of_the_paper", "paper_summary")
# Some venues split out a separate "questions for authors" field. We treat
# it as additional content rather than a fallback — gets concatenated onto
# weaknesses if present, since they're usually critique-flavored.
QUESTIONS_KEYS = ("questions_to_authors", "questions_for_authors", "questions")
# Fallback when no separate weaknesses/strengths fields exist (ICLR V1 puts
# everything in "main_review"; older COLM/NeurIPS comments).
FULL_REVIEW_KEYS = (
    "main_review", "review", "comment",
    "summary_of_the_review",
)


def _content_value(content: dict, key: str) -> str:
    v = content.get(key)
    if v is None:
        return ""
    if isinstance(v, dict):
        v = v.get("value", "")
    if isinstance(v, str):
        return v.strip()
    return ""


def _pick(content: dict, keys: tuple[str, ...]) -> tuple[str, str]:
    for k in keys:
        s = _content_value(content, k)
        if s:
            return k, s
    return "", ""


SCHEMA_VERSION = 2

# Numeric / enum / boolean fields the venue may capture. We pull whichever
# of these are present in the reviewer note's content. Missing ones are
# simply absent from review_metadata.
NUMERIC_FIELDS = (
    # overall
    "rating", "recommendation", "overall_evaluation", "overall_score",
    # confidence / expertise
    "confidence", "expertise",
    # NeurIPS / ICLR / ICML sub-dimensions
    "soundness", "presentation", "contribution",
    "quality", "clarity", "significance", "originality",
    # ARR
    "excitement", "reproducibility",
    # ACM MM
    "fit", "technical_quality", "technical_presentation",
    # KDD
    "relevance", "novelty",
    # generic
    "scientific_quality", "writing",
)

BOOLEAN_FIELDS = (
    "best_paper_candidate", "ethics_review_needed", "flag_for_ethics_review",
    "is_member", "interaction",
)


def _content_value_raw(content: dict, key: str):
    """Return content[key] unwrapped from the OpenReview {"value": ...}
    nesting, but preserve type (str / int / float / bool / list)."""
    v = content.get(key)
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("value")
    return v


def _content_value(content: dict, key: str) -> str:
    v = _content_value_raw(content, key)
    if isinstance(v, str):
        return v.strip()
    return ""


def _pick(content: dict, keys: tuple[str, ...]) -> tuple[str, str]:
    for k in keys:
        s = _content_value(content, k)
        if s:
            return k, s
    return "", ""


def _all_text_fields(content: dict, *, min_chars: int = 30) -> dict[str, str]:
    """Pull every non-trivial text field from a reviewer note's content.

    Used to populate v2's review_fields dict — we want to keep ALL the
    venue-specific text the reviewer typed, not just the canonical 4
    (summary / strengths / weaknesses / questions). Skips fields that
    are too short to be a real review section (acks, e.g. "N/A").
    """
    out: dict[str, str] = {}
    skip_keys = {
        # OpenReview internal / non-review fields
        "title", "authors", "authorids", "abstract", "keywords",
        "TLDR", "tldr",
        "decision", "venue", "venueid", "paperhash",
        "pdf", "supplementary_material", "code_of_conduct", "ethics_review",
        # numeric fields handled separately
        *NUMERIC_FIELDS, *BOOLEAN_FIELDS,
    }
    for k, v in content.items():
        if k in skip_keys:
            continue
        s = _content_value(content, k)
        if len(s) >= min_chars:
            out[k] = s
    return out


def fetch_paper_meta(forum_id: str, *, api_v2: bool) -> dict:
    """Pull paper-level metadata: title / authors / abstract / keywords /
    decision / openreview URL. Returns a dict suitable for the v2 schema's
    `paper` field. Decision comes from a separate Decision note attached
    to the same forum.
    """
    base = "https://api2.openreview.net" if api_v2 else "https://api.openreview.net"

    # Fetch the forum note (the Submission) — has title/authors/abstract.
    try:
        sub_data = _http_json(f"{base}/notes?id={forum_id}")
    except Exception:
        sub_data = {"notes": []}
    sub_notes = sub_data.get("notes", [])

    title = ""
    authors: list[str] = []
    abstract = ""
    keywords: list[str] = []
    if sub_notes:
        c = sub_notes[0].get("content", {}) or {}
        title = _content_value(c, "title")
        # Authors may be a list or a single string
        a_raw = _content_value_raw(c, "authors")
        if isinstance(a_raw, list):
            authors = [str(x) for x in a_raw if x]
        elif isinstance(a_raw, str):
            authors = [s.strip() for s in a_raw.split(",") if s.strip()]
        abstract = _content_value(c, "abstract")
        kw_raw = _content_value_raw(c, "keywords")
        if isinstance(kw_raw, list):
            keywords = [str(x) for x in kw_raw if x]
        elif isinstance(kw_raw, str):
            keywords = [s.strip() for s in kw_raw.split(",") if s.strip()]

    # Pull all notes attached to forum to find the Decision (if any).
    decision: str | None = None
    try:
        all_data = _http_json(
            f"{base}/notes?{_qs({'forum': forum_id, 'limit': 200})}")
    except Exception:
        all_data = {"notes": []}
    for n in all_data.get("notes", []):
        invs = n.get("invitations") or ([n.get("invitation")]
                                        if n.get("invitation") else [])
        for i in invs:
            if i and i.endswith("/Decision"):
                d = _content_value(n.get("content", {}) or {}, "decision")
                if d:
                    decision = d
                break
        if decision:
            break

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords,
        "decision": decision,
        "openreview_url": f"https://openreview.net/forum?id={forum_id}",
    }


def fetch_reviews_for_forum(forum_id: str, *, api_v2: bool) -> list[dict]:
    """Return one v2-schema record per Reviewer note attached to this forum.

    Each record carries:
      - reviewer id (anonymized signature suffix)
      - review_fields: every content key that has substantive text (raw)
      - review_metadata: numeric / enum / boolean fields the venue captured
      - source: openreview_field_keys, openreview_invitation, api_version

    Paper meta is filled in by collect_all() (one fetch per forum, applied
    to every reviewer record). ai_score is added later by the GPTZero filter.
    """
    base = "https://api2.openreview.net" if api_v2 else "https://api.openreview.net"
    qs = _qs({"forum": forum_id, "limit": 200})
    data = _http_json(f"{base}/notes?{qs}")
    notes = data.get("notes", [])

    out = []
    for n in notes:
        sigs = n.get("signatures") or []
        # Reviewer notes carry a signature like ".../Reviewer_xxxx" (V2,
        # NeurIPS V1) or ".../AnonReviewer<n>" (ICLR V1 2018-2020).
        if not any("/Reviewer_" in s or "/AnonReviewer" in s for s in sigs):
            continue
        # Skip Official_Comment / Rebuttal etc — keep only Official_Review.
        invs = n.get("invitations") or ([n.get("invitation")]
                                        if n.get("invitation") else [])
        inv_tail = ""
        for i in invs:
            if i and "/-/" in i:
                # Most invitations end like ".../-/Official_Review" (V2,
                # NeurIPS V1) but ICLR V1 uses ".../-/PaperN/Official_Review"
                # — drop any path segments before the final word.
                inv_tail = i.split("/-/")[-1].split("/")[-1]
                break
        if inv_tail and inv_tail not in (
                "Official_Review", "Official_Comment", "Review"):
            continue

        content = n.get("content", {}) or {}

        # Pull EVERY substantive text field — keeps the venue's original
        # field names so the by-field extractor can map them to canonical
        # buckets later.
        text_fields = _all_text_fields(content)
        if not text_fields:
            continue

        # Also do a canonical-key map for fast downstream consumption (e.g.
        # the GPTZero filter just wants summary+strengths+weaknesses+questions).
        wk_field, _ = _pick(content, WEAKNESS_KEYS)
        st_field, _ = _pick(content, STRENGTH_KEYS)
        sm_field, _ = _pick(content, SUMMARY_KEYS)
        q_field, _ = _pick(content, QUESTIONS_KEYS)
        full_field, full_text = _pick(content, FULL_REVIEW_KEYS)
        # Skip ack-only "comment" notes (e.g. "Thanks for the response").
        if not (wk_field or st_field or sm_field or q_field):
            if not full_text or len(full_text) < 400:
                continue

        # Numeric / enum / boolean metadata
        review_metadata: dict = {}
        for k in NUMERIC_FIELDS:
            v = _content_value_raw(content, k)
            if v is None:
                continue
            # OpenReview sometimes stores numeric as "5: Strong Accept" — try
            # to parse leading int/float; otherwise keep raw string.
            if isinstance(v, (int, float)):
                review_metadata[k] = v
            elif isinstance(v, str):
                m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", v)
                review_metadata[k] = (
                    float(m.group(1)) if m and "." in m.group(1)
                    else int(m.group(1)) if m
                    else v.strip()
                )
        for k in BOOLEAN_FIELDS:
            v = _content_value_raw(content, k)
            if v is None:
                continue
            if isinstance(v, bool):
                review_metadata[k] = v
            elif isinstance(v, str):
                review_metadata[k] = v.strip().lower() in ("yes", "true", "1")

        rid = re.sub(r"^(Anon)?Reviewer_?",
                     "", sigs[0].split("/")[-1])
        out.append({
            "reviewer": rid,
            "review_fields": text_fields,
            "review_metadata": review_metadata,
            "source_extras": {
                "openreview_field_keys": {
                    "summary":    sm_field,
                    "strengths":  st_field,
                    "weaknesses": wk_field,
                    "questions":  q_field,
                    "full_review": full_field,
                },
                "openreview_invitation": inv_tail,
                "api_version": "v2" if api_v2 else "v1",
            },
        })
    return out


# ---------------------------------------------------------------------------
# Top-level orchestration — what venues × years to crawl.
# ---------------------------------------------------------------------------

# Original "oral-only" plan (kept for back-compat — produces the existing 57
# reviewer JSONs). Use this when you want the small reproducible corpus.
VENUE_PLAN_ORAL_ONLY = [
    # (label, year, lister, api_v2_for_replies)
    ("NeurIPS", 2023, list_oral_neurips_v2, True),
    ("NeurIPS", 2024, list_oral_neurips_v2, True),
    ("COLM",    2024, list_oral_colm_v2,    True),
    ("ICLR",    2024, list_oral_iclr,       True),
    ("ICLR",    2023, list_oral_iclr,       True),
    ("ICLR",    2022, list_oral_iclr,       False),
    ("ICLR",    2021, list_oral_iclr,       False),
]

# Broad plan for growing the corpus to ~500+ reviews. Mixes accept (oral /
# spotlight / poster) AND reject papers — reject reviews are the source of
# the long-form critical sentence patterns the WEAKNESS / QUESTION buckets
# need to be useful for harshly-rated submissions. See LESSONS.md §4.
VENUE_PLAN_BROAD = [
    # (label, year, lister, api_v2_for_replies)
    ("NeurIPS", 2023, list_all_neurips_v2, True),
    ("NeurIPS", 2024, list_all_neurips_v2, True),
    ("ICLR",    2024, list_all_iclr,       True),
    ("ICLR",    2023, list_all_iclr,       True),
    ("ICLR",    2022, list_all_iclr,       False),
    ("ICLR",    2021, list_all_iclr,       False),
    ("COLM",    2024, list_all_colm_v2,    True),
]

# Active plan — flip to BROAD when growing the corpus.
VENUE_PLAN = VENUE_PLAN_ORAL_ONLY

# How many forums (papers) per (venue, year) bucket.
# - 4 = original small reproducible corpus (≈57 reviews after filter)
# - 30 = ~500 reviews after GPTZero filter (~3-5 hours of filter runtime)
# - 60 = ~1000 reviews (overnight run)
PAPERS_PER_BUCKET = 4


def _safe_get_value(content: dict, key: str) -> str:
    v = content.get(key)
    if isinstance(v, dict):
        v = v.get("value", "")
    return v if isinstance(v, str) else ""


def collect_all(*, force_refresh: bool = False) -> dict:
    """Walk VENUE_PLAN and write v2-schema reviewer JSONs under source/.

    Idempotent by default: skips reviewer JSONs that already exist on disk
    (preserves any GPTZero ai_score the filter has already computed). Set
    force_refresh=True to overwrite.
    """
    now_iso = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "collected_at": now_iso,
        "buckets": [],
        "total_forums": 0,
        "total_reviews_written": 0,
        "total_reviews_skipped_existing": 0,
    }
    for label, year, lister, api_v2 in VENUE_PLAN:
        bucket_dir = os.path.join(RAW_ROOT, label, str(year))
        os.makedirs(bucket_dir, exist_ok=True)
        try:
            forums = lister(year, limit=PAPERS_PER_BUCKET)
        except Exception as e:
            summary["buckets"].append({
                "venue": label, "year": year,
                "error": f"{type(e).__name__}: {e}",
            })
            continue

        forum_records = []
        for f in forums:
            fid = f["id"]

            # First pass: pull paper-level meta once per forum (title/
            # authors/abstract/keywords/decision). We pass api_v2 along
            # so we hit the right API.
            try:
                paper_meta = fetch_paper_meta(fid, api_v2=api_v2)
            except Exception as e:
                paper_meta = {
                    "title": _safe_get_value(f.get("content", {}) or {}, "title"),
                    "authors": [], "abstract": "", "keywords": [],
                    "decision": None,
                    "openreview_url": f"https://openreview.net/forum?id={fid}",
                    "_meta_error": f"{type(e).__name__}: {e}",
                }

            try:
                reviews = fetch_reviews_for_forum(fid, api_v2=api_v2)
            except Exception as e:
                forum_records.append(
                    {"forum_id": fid, "title": paper_meta.get("title", ""),
                     "error": f"{type(e).__name__}: {e}"}
                )
                time.sleep(0.4)
                continue

            forum_dir = os.path.join(bucket_dir, fid)
            os.makedirs(forum_dir, exist_ok=True)

            written = 0
            skipped = 0
            for r in reviews:
                rpath = os.path.join(forum_dir,
                                     f"reviewer_{r['reviewer']}.json")
                # Idempotency: keep existing file (preserves ai_score).
                if os.path.isfile(rpath) and not force_refresh:
                    skipped += 1
                    continue

                # Build the v2-schema record.
                source_extras = r.pop("source_extras", {})
                source_extras["collected_at"] = now_iso
                record = {
                    "schema_version": SCHEMA_VERSION,
                    "venue": label,
                    "year": year,
                    "forum_id": fid,
                    "reviewer": r["reviewer"],
                    "paper": paper_meta,
                    "review_fields": r["review_fields"],
                    "review_metadata": r.get("review_metadata", {}),
                    "source": source_extras,
                    # ai_score added later by filter_with_gptzero.py
                }
                with open(rpath, "w") as out:
                    json.dump(record, out, ensure_ascii=False, indent=2)
                written += 1

            forum_records.append({
                "forum_id": fid,
                "title": paper_meta.get("title", ""),
                "decision": paper_meta.get("decision"),
                "reviews_written": written,
                "reviews_skipped_existing": skipped,
            })
            summary["total_reviews_written"] += written
            summary["total_reviews_skipped_existing"] += skipped
            time.sleep(0.4)

        summary["buckets"].append({
            "venue": label, "year": year,
            "forums": forum_records,
            "forum_count": len(forum_records),
        })
        summary["total_forums"] += len(forum_records)

    os.makedirs(DERIVED_ROOT, exist_ok=True)
    with open(os.path.join(DERIVED_ROOT, "collection_summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing reviewer JSONs (loses ai_score "
                        "unless you re-run filter_with_gptzero.py).")
    args = p.parse_args()
    s = collect_all(force_refresh=args.force)
    print(json.dumps(s, indent=2, ensure_ascii=False))
