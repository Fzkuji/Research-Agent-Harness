# reviewer JSON schema (v2)

This is the on-disk format for every entry under
`source/<venue>/<year>/<forum_id>/reviewer_<id>.json` produced by
`pipeline/collect_from_openreview.py`.

Goal of v2 (vs the original schema): store every piece of paper +
review information exactly once, separately, so that downstream
extractors / samplers can pull out per-field content (e.g. only
`review_questions` for the QUESTIONS bucket) without re-parsing
concatenated text. Also adds paper-level metadata (authors, abstract,
decision) needed for venue-similarity matching when the user asks for a
review of a venue we have no corpus for.

## Top-level keys

```jsonc
{
  // ---- Identity ----
  "schema_version": 2,                  // bump when changing this file
  "venue":          "COLM",             // exactly as written under source/
  "year":           2024,
  "forum_id":       "aajyHYjjsk",       // OpenReview forum id
  "reviewer":       "Pvmb",             // anonymized reviewer id
  
  // ---- Paper metadata ----
  "paper": {
    "title":         "...",
    "authors":       ["A. Smith", "B. Jones"],   // [] if anonymous
    "abstract":      "...",
    "keywords":      ["language model", "..."],   // [] if missing
    "decision":      "Accept (oral)",            // "Accept (poster)" / "Reject" / "Withdraw" / null
    "openreview_url":"https://openreview.net/forum?id=aajyHYjjsk"
  },
  
  // ---- Review content (each field stored separately, raw OpenReview value) ----
  "review_fields": {
    // Map each well-known field to its raw text. Missing fields are
    // simply absent (not "" or null). Different venues use different
    // field names — we KEEP the original name so the by-field extractor
    // can group correctly.
    //
    // Common fields across venues:
    //   summary | paper_summary | summary_of_the_paper
    //   strengths | reasons_to_accept | pros
    //   weaknesses | reasons_to_reject | cons | limitations
    //   questions | questions_to_authors | questions_for_authors
    //   main_review | review | comment | summary_of_the_review
    //   ethics_concerns | flag_for_ethics_review
    //   broader_impact | impact_concerns
    //   limitations
    //   related_work
    //
    // Whatever OpenReview returned that has non-empty text goes here.
    "summary":            "...",
    "reasons_to_accept":  "...",
    "reasons_to_reject":  "...",
    "questions_to_authors": "..."
  },
  
  // ---- Review numeric / enum metadata (the venue's score scale fields) ----
  "review_metadata": {
    // Examples vary by venue. All optional.
    "rating":              6,            // overall recommendation, raw int/float
    "confidence":          4,
    "soundness":           3,            // ICLR / NeurIPS sub-dim
    "presentation":        4,
    "contribution":        3,
    "excitement":          4,            // ARR
    "reproducibility":     5,
    "fit":                 3,            // ACM MM
    "technical_quality":   4,
    "technical_presentation": 4,
    "best_paper_candidate": false        // ACM MM
    // ... other numeric / enum / bool fields the venue captures
  },
  
  // ---- GPTZero verification (added by filter_with_gptzero.py) ----
  "ai_score": {
    "status":     "ok",                  // ok | text_too_long | error | skipped
    "ai_pct":     0,                     // 0-100, only when status=ok
    "human_pct":  100,
    "mixed_pct":  0,
    "verdict":    "We are highly confident this text is entirely human",
    "confidence": "highly",
    "chars":      2040,
    "words":      315,
    "ai_vocab":   0,
    "url":        "https://app.gptzero.me/documents/...",
    "scored_chars": 2040,                // length of the text we sent
    "error":      null
  },
  
  // ---- Collection bookkeeping ----
  "source": {
    "openreview_field_keys": {           // which raw OpenReview key each
      "summary":            "summary",   // logical field came from
      "strengths":          "reasons_to_accept",
      "weaknesses":         "reasons_to_reject",
      "questions":          "questions_to_authors"
    },
    "openreview_invitation": "Official_Review",
    "api_version":           "v2",
    "collected_at":          "2026-04-27T20:14:00Z"
  }
}
```

## Backward compatibility

Old (v1) reviewer JSONs in `source/` look like:

```jsonc
{
  "reviewer":     "Pvmb",
  "weaknesses":   "...",     // pre-concatenated text
  "strengths":    "...",
  "summary":      "...",
  "full_review":  "",
  "field_keys":   {...},
  "venue":        "COLM",
  "year":         2024,
  "forum_id":     "aajyHYjjsk",
  "paper_title":  "...",
  "ai_score":     {...}
}
```

`filter_with_gptzero.py` and `sample_templates.py` both detect schema
by presence of the `schema_version` key and fall back to v1 reading
when absent. The migration script
`pipeline/migrate_to_v2.py` upgrades v1 → v2 in place by re-fetching
paper meta + raw review fields from OpenReview while preserving the
existing `ai_score` so we don't waste GPTZero calls.

## Why "review_fields" is a dict not flat

Different venues call the same logical thing different names:
- "weaknesses" (NeurIPS, ICLR) vs "reasons_to_reject" (ARR, COLM)
- "questions" (NeurIPS) vs "questions_to_authors" (ARR, COLM)
- "main_review" (ICLR V1) vs "comment" (older COLM)

Storing under the venue's original name preserves the source ground
truth. The downstream extractor maps these to canonical buckets
(SUMMARY / STRENGTHS / WEAKNESSES / QUESTIONS / FULL) for sampling, but
the raw form is here if a future analysis needs it.
