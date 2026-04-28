---
name: humanize-paper-review
version: 4.0.0
description: |
  Humanize an existing LLM-generated peer review so it passes
  AI-detection (e.g. GPTZero <=20% for ACM MM 2026), while preserving
  the user's score / verdict / sub_scores / observations.

  v4 uses 2-stage redaction (the previous in-context rewrite path
  empirically failed at 100% AI): stage A compresses the draft into a
  structured judgment dict (numbers + ≤80-char fragment bullets); stage
  B regenerates prose from scratch via review_app --draft, so no
  draft-prose token ever enters the prose-generator's context.
  Empirical: 1% AI on GPTZero, ACM MM smoke test.

  Sibling `paper-review` is for the from-scratch case (no draft).
  Use this skill when the user has a draft they want to keep the
  judgment from.
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
---

# humanize-paper-review

Wrap an LLM-generated review draft into a humanized version that preserves
the user's judgment but generates the prose from scratch using a corpus
of real human reviewer sentence templates. The whole thing is delegated
to `research_harness.review_app --draft` — this skill's job is to
collect inputs, run the CLI, and report the result.

## When to use this skill

- The user has an existing review draft (their own LLM, a colleague's,
  a previous draft) and wants its prose to pass an AI detector
- The user mentions GPTZero / Originality / Pangram / ACM MM AI-rate cap
  AND is starting from a draft (not from a paper alone)
- The user explicitly invokes `/humanize-paper-review`

If the user has only the paper (no draft), use `/paper-review` instead.

## Empirical evidence (v4)

| stage                                       | AI%  | Human% |
|---------------------------------------------|------|--------|
| Raw GPT-written draft (baseline)            | 100  | 0      |
| v3 in-context rewrite (gentle, 9/58 lines)  | 100  | 0      |
| v3 in-context rewrite (strict, 18/58 lines) | 100  | 0      |
| **v4 2-stage redaction (this skill)**       | **1**  | **99**   |

(GPTZero, ACM MM smoke test, 2026-04-28)

The v3 in-context path failed because GPTZero detects token-level LLM
signatures, not surface phrasing — once the LLM reads the draft's prose,
the rewrite carries the signature regardless of paraphrase strength.
v4 sidesteps this by never letting any downstream LLM see the draft's
sentences: only its numbers and short fragment bullets pass through.

## Required inputs (use AskUserQuestion if missing)

- **Paper** (file or directory) — needed because stage B reads the paper
  itself to write the new prose. Accepts .pdf / .docx / .md / .tex / .txt
  or a directory of .tex files.
- **Review draft to humanize** — file path. Markdown with `## Summary`,
  `## Strengths`, etc. is preferred; any structured form works as long
  as score / verdict / per-section content is identifiable.
- **Target venue** — *optional but recommended*. Default: NeurIPS.
  Aliases handled (e.g. "ACM Multimedia"/"acm mm", "NeurIPS"/"nips").
- **Output JSON path** — default: `<paper_dir>/humanized_review.json`.

## Workflow

1. **Confirm inputs via AskUserQuestion** if any are missing.

2. **Run the CLI** (the actual work happens here — both extract_judgment
   and the from-scratch generation are inside `review_app`):
   ```bash
   python -m research_harness.review_app \
       <paper_path> \
       --venue "<venue>" \
       --draft <draft_path> \
       --output <output_path>
   ```
   This runs about 4-7 minutes (one codex CLI call to extract judgment
   from the draft, one codex CLI call to generate prose from scratch).

3. **Read the output JSON** at `<output_path>`. It has:
   - `score`, `verdict`, `sub_scores`, `confidence`, `best_paper_candidate`
     — all preserved verbatim from the draft
   - per-venue free-text fields (e.g. for ACM MM: `summary`, `strengths`,
     `weaknesses`, `review`, `fit_justification`) — re-written from
     scratch using corpus templates
   - `venue` — canonical venue name

4. **(Recommended) Verify GPTZero**. The user's lab requires <=20% AI;
   v4 typically lands at 1-5%. To verify, extract the prose fields and
   score them:
   ```bash
   python3 -c "
   import json, sys
   r = json.load(open('<output_path>'))
   parts = []
   for k in ('summary','review','fit_justification'):
       v = r.get(k)
       if isinstance(v, str): parts.append(v)
   for k in ('strengths','weaknesses','questions'):
       v = r.get(k)
       if isinstance(v, list): parts.extend(v)
   print('\n\n'.join(parts))
   " > /tmp/humanized_prose.txt
   ```
   Then run that text through GPTZero (or whatever detector the user
   targets). If above the cap, re-run step 2 with a different seed (the
   underlying corpus sample is fresh on each call) and re-check.

5. **Report to the user**:
   - Where the JSON was saved
   - Score / verdict that were preserved from the draft
   - Whether GPTZero was checked and the result
   - Honest note if applicable: "If your detector is not GPTZero, the
     1% number does not transfer — pangram / Originality may behave
     differently."

## What NOT to do

- Don't try to rewrite the draft sentence-by-sentence in your own
  conversation context. v3 of this skill did that; the empirical result
  was 100% AI on every attempt. Always delegate to the CLI.
- Don't change any number in the draft's score / verdict / sub_scores /
  confidence. The whole point is to preserve the user's judgment. The
  CLI handles this automatically — don't post-edit.
- Don't combine this skill with general-purpose humanizers
  (StealthWriter, aihumanize.io, DIPPER) — those introduce factual
  errors and the v4 output is already clean.
- Don't promise a specific AI% number. Report what GPTZero actually
  said when you ran it.

## Setup

This skill assumes the source repo (research_harness) is on
`PYTHONPATH` so `python -m research_harness.review_app` resolves. The
CLI in turn assumes the corpus index has been built (run
`python -m research_harness.stages.review.review_corpus.pipeline.extract_by_field`
once if you get an `INDEX_PATH missing` error).

The corpus underneath grows as new reviews are GPTZero-filtered (current:
14 venue-year buckets across COLM 2024-2025, ICLR 2018-2024,
NeurIPS 2021-2025, ICML 2025; ~500 GPTZero-verified human reviews;
5 canonical buckets × 1100-2600 sentences per bucket). Each invocation
samples fresh templates from the live index.

For background on why the verbatim-template approach works (and why
prompt-only rewrite approaches fail), see
`research_harness/stages/review/review_corpus/LESSONS.md` in the source
repo.
