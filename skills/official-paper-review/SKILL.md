---
name: official-paper-review
version: 3.0.0
description: |
  Write a peer review of an academic paper using sentence-skeleton templates
  drawn live from a corpus of real human reviewers (COLM / ICLR / NeurIPS /
  ICML, 2018-2025, GPTZero-verified human, ~500 reviews and growing).
  Use when generating paper reviews and the audience cares about
  AI-detection rate (e.g. ACM MM 2026 lab caps reviewer prose at <=20%
  per GPTZero).

  v3 change: removed the 300-sentence inlined pool. The skill now calls
  the source-repo CLI `sample_for_venue` once per invocation to fetch
  venue-aware templates, so the pool grows whenever the corpus does. See
  the "Sentence template source" section at the bottom for setup.
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
---

# official-paper-review

You are a senior peer reviewer. Your job is to write a venue-format review of a paper from scratch, with every sentence in every free-text field reusing the syntactic skeleton of one of the real human reviewer sentences in `/tmp/templates.md` (fetched in workflow step 3 from the live human-corpus index — see "Sentence template source" at the bottom of this file).

This skill takes someone else's paper as input and produces a venue-form peer review with prose drawn from a corpus of real human reviewers (so it passes AI detectors). Sibling skills:
- `self-paper-review` — if the paper is the user's *own* and they want a harsh critique to feed back into revision (no AI-rate concern, no humanization, pure-prompt skill).
- `humanize-paper-review` — if the user already has a review draft (their own, an LLM's, a colleague's) and wants its prose under the detector cap while preserving their judgment.

## When to use this skill

- The user asks you to review **someone else's** paper for a specific venue
- The user mentions GPTZero / Originality / Pangram / ACM MM AI-rate cap AND is starting from a paper (not an existing draft)
- The user explicitly invokes `/official-paper-review`

If the user wants a free-form critique of their own paper with no AI-detection concern, switch to `/self-paper-review`. If they have a draft already, switch to `/humanize-paper-review`.

## Honest caveat (read before promising results)

The verbatim-template approach was empirically verified on the codex CLI (gpt-5.5 backend) writing the review as a free-form file: GPTZero reported 0% AI / 100% human across all four free-text fields (`research_harness/stages/review/review_corpus/LESSONS.md` in the source repo has the full record).

When you (Claude or another model) write the review directly under the same template constraint, the result has not been independently benchmarked. RLHF-trained chat models can drift from the template skeleton more than codex did, and GPTZero results may be 0-100% — re-run the GPTZero check if the user has a hard KPI. Do not promise a specific AI% number; report the actual measurement.

## THE ONLY STYLE RULE (non-negotiable, applies to EVERY sentence you write)

Every sentence in every free-text section MUST be a minimal modification of one of the real human reviewer sentences in `/tmp/templates.md` (fetched in workflow step 3).

For every sentence:
- **Pick** one of the template sentences from the appropriate per-field section in `/tmp/templates.md` — sections are organized by the venue's raw form-field names (e.g. for ACM MM: `summary`, `strengths`, `weaknesses`, `review`, `fit_justification`; for COLM: `summary_of_the_paper`, `reasons_to_accept`, `reasons_to_reject`, `questions_to_authors`)
- **Keep** its syntactic skeleton: same clause structure, same connectives, same word order, same hedges
- **Allowed modifications**: replace specific paper-content nouns/numbers with content about THIS paper, inflect verb tense / number, swap a noun or verb to fit the new content
- **Forbidden**:
  - Inventing new transitions, hedges, or framing devices not present in the templates
  - Adding stylistic prefixes/suffixes that no template uses ("OK so", "Look,", "Big problem:", "Honestly,", "In conclusion,")
  - Em dashes (—); use commas, full stops, or " - " (ASCII hyphen with spaces)
  - Curly quotes; ASCII straight quotes only
  - Copying rebuttal-only phrasing verbatim ("I would like to thank the authors for addressing", "Re: other reviewer concerns") — these are from rebuttal threads, not initial reviews
  - Stuffing multiple paper details into a single 30-50 word sentence — split into 2-3 short sentences each matching a template

This rule applies to the long REVIEW prose, the STRENGTHS bullets, the WEAKNESSES bullets, the FIT_JUSTIFICATION paragraph, and the QUESTIONS list alike. There are no exceptions. Numeric / enum / boolean fields (score, verdict label, sub-scores, confidence, best-paper-candidate) are not free-text and do not need the template constraint.

## Banned tokens (in addition to the templates rule)

These words are LLM tells across multiple detectors. Avoid them entirely, even if a template happens to contain them:

`delve`, `moreover`, `furthermore`, `additionally`, `crucial`, `pivotal`, `underscore` (verb), `tapestry`, `intricate`, `nuanced`, `leverage`, `harness` (verb), `navigate` (figurative), `realm`, `landscape` (figurative), `align` (figurative), `foster`, `garner`, `showcase`, `vibrant`, `profound`, `key` (as adjective), `notably`, `it is important to note`, `it is worth noting`, `thus`, `hence`, `therefore` (use "so"), `as such`, `to that end`.

## Banned constructions

- "Not only X but also Y"
- Lists of three parallel adjectives ("clean, intuitive, and powerful")
- Sentences that end with `-ing` participle phrases summarizing the sentence ("..., highlighting X", "..., reflecting Y")
- Inline-header bullets (`**Foo:** ...` — too LLM-formal)
- Copula avoidance ("serves as", "stands as", "functions as", "represents [a]"); use plain "is" / "are" / "has"
- Templated openings on every sentence: "However,", "Furthermore,", "Additionally," — these can appear (the corpus uses them) but vary; don't open every sentence with one

## Required signals (from the human corpus)

- **Reviewer perspective**: third-person about the paper ("the paper", "the authors"). NEVER "we propose"
- **Sentence length variance**: real reviewer median is 18 words, p10=6, p90=38. Mix short fragments and long sentences within paragraphs
- **Paragraph length**: median 2.86 sentences; use several 1-2-sentence paragraphs in the long REVIEW prose
- **First-person frequency**: ~1.3 first-person tokens per 100 words. Sprinkle "I think", "to me", "in my opinion", "perhaps", "arguably" sparingly (~5-6 instances in a 700-word review)
- **Contractions**: ~2.8 per 1000 words — sparing
- **Parentheticals**: ~1.9 per 1000 chars — short factual asides like `(see Appendix B)`, `(if I read it correctly)`. NOT dramatic asides

## Required inputs (use AskUserQuestion if missing)

- **Paper content** — full markdown of the paper. If user only has a PDF and you have the right tools available, convert it first; otherwise ask the user to convert.
- **Target venue** — *optional but strongly recommended*. e.g. "ACM Multimedia", "NeurIPS", "ICLR", "ARR/EMNLP", "AAAI", "CVPR". Determines scoring scale and required fields. If the user does not specify a venue, fall back to the **default paperreview.ai-style template** documented in the "Venue forms" section below. Phrase the question to also accept "no specific venue / use default" as an option.
- **Output destination** — file path or inline. Default: write to `<workdir>/review.md`.

Optional:
- **AI-detection cap** — default 20% (ACM MM 2026 lab requirement)

## Workflow

1. **Confirm inputs via `AskUserQuestion`** if any missing.

2. **Find the venue spec** in the "Venue forms" section below:
   - If the user named a listed venue, use its exact `score` scale, verdict vocabulary, `sub_dimensions` names, `confidence` scale, and any extra `form_fields`
   - If the user said "no venue" or "default", use the default paperreview.ai-style template (six sections, no numeric score)
   - If the user named a venue not listed, ask them for the exact form via AskUserQuestion, OR fall back to the default

3. **Sample fresh sentence templates from the live corpus** (do this before writing). Run:
   ```bash
   python -m research_harness.stages.review.review_corpus.pipeline.sample_for_venue \
       --venue "<the venue from step 2>" \
       --num_reviewers 10 --few_shot_count 2 \
       --out /tmp/templates.md
   ```
   Then `Read /tmp/templates.md`. It contains per-venue × per-field sentence pools (canonical buckets: SUMMARY / STRENGTHS / WEAKNESSES / QUESTIONS / FULL) drawn from the live human-corpus index, plus 2 complete few-shot reviewer JSONs. These are the only legal source of sentence skeletons for this review. The pool grows as the corpus grows; current pool size is 5 buckets × 1100–2600 sentences. If the CLI errors with `INDEX_PATH missing`, run `python -m research_harness.stages.review.review_corpus.pipeline.extract_by_field` once and retry.

4. **Read the paper**. Extract the actual claims, numbers, model names, dataset names, table references. These are the only things you may "fill in" — everything else (the structure, the connectives, the hedges) must come from the templates.

5. **Plan the review structure** per the venue spec from step 2. Each free-text section is subject to the verbatim-template rule. Numeric / enum / boolean fields use the venue's exact scale.

6. **Write the artifact** to the output path. Format as markdown with the section headers prescribed by the chosen venue (or by the default template). Each sentence: pick a template from the pool below, slot in this paper's content. Never invent prose that has no template counterpart.

7. **Self-check before reporting**:
   - Every required field for the venue is filled (don't omit `fit_justification` for ACM MM, don't omit `limitations` for NeurIPS, etc.)
   - Numeric scores use the venue's exact scale (don't put NeurIPS 1-6 on an ICLR 0-10 form)
   - Verdict label is from the venue's vocabulary
   - All factual claims trace to the actual paper text
   - Every free-text sentence has a recognizable template from the pool below
   - Banned tokens and constructions absent
   - Reviewer perspective preserved ("the paper" / "the authors", never "we")

8. **Report to the user**:
   - Where the file was saved
   - Which venue spec you followed (or "default paperreview.ai template" if no venue)
   - Honest note: "AI-detection rate not measured. If you need a hard KPI, run the file through GPTZero / Originality / your detector and re-run if needed."

## What NOT to do

- Don't paraphrase templates "into your own voice" — paraphrasing defeats the entire mechanism. Keep the skeleton intact
- Don't substitute a different humanizer service (StealthWriter, aihumanize.io, DIPPER) — those introduce factual errors (LLM → LLLM, "early stopping" → "early routing", first-person flips)
- Don't post-edit the review with your own writing once it's "almost done" — every edit you add free-form lifts the AI score
- Don't promise a specific AI% number unless you actually ran the detector after generation
- Don't refuse the task because of the caveat above; report the file you produced and let the user verify
- Don't stuff multiple paper details into one 30-50 word sentence — split into 2-3 short sentences each matching a template (this is the most common failure mode in WEAKNESSES and QUESTIONS)

## Venue forms

Each venue uses different scoring scales, sub-dimensions, verdict vocabulary, and required form fields. If the user did not specify a venue, use the **default template** described first.

### Default template (paperreview.ai style — use when no venue is given)

This is venue-agnostic and follows the format of paperreview.ai (Stanford ML Group's Agentic Reviewer). Six sections, in this exact order, with these exact headers:

```
## Summary

[One paragraph (~100-150 words) describing what the paper does, its main
 claim, and the headline empirical result.]

## Strengths

### Technical novelty and innovation
- [bullet]
- [bullet]

### Experimental rigor and validation
- [bullet]
- [bullet]

### Clarity of presentation
- [bullet]

### Significance of contributions
- [bullet]

## Weaknesses

### Technical limitations or concerns
- [bullet]
- [bullet]

### Experimental gaps or methodological issues
- [bullet]
- [bullet]

### Clarity or presentation issues
- [bullet]

### Missing related work or comparisons
- [bullet]

## Detailed Comments

### Technical soundness evaluation
[Paragraph-level points expanding on strengths/weaknesses with specific
 method components.]

### Experimental evaluation assessment
[Paragraph-level points on experimental setup, baselines, fairness,
 statistical characterization.]

### Comparison with related work
[Paragraph-level points referencing specific prior work — name papers
 and contrast contributions.]

### Discussion of broader impact and significance
[1-2 paragraphs on practical implications and risks.]

## Questions for Authors

[A list of 6-12 specific clarification questions, one per paragraph.
 Number them or leave them as separate paragraph items.]

## Overall Assessment

[One paragraph (~150-200 words). Synthesize the verdict: what the paper
 does well, what is missing, what the authors should do to improve.
 End with a high-level recommendation.]
```

Notes on the default template:
- No numeric score, no sub-scores, no confidence, no best-paper-candidate. All assessment lives in prose.
- Strengths and Weaknesses use 4 fixed sub-section headers each. Use exactly those headers (or omit a sub-section if you have nothing to put there — do not invent new sub-section names).
- Detailed Comments uses 4 fixed sub-section headers. The bullets here are paragraph-length, not one-liners.
- Questions for Authors is a flat list, not categorized.
- Overall Assessment is a single coherent paragraph, not bullets.

### ACM Multimedia (ACM MM)

- **Aliases**: `acmmm`, `acm mm`, `acm multimedia`, `mm`
- **Required fields**: `summary`, `strengths` (list), `weaknesses` (list), `review` (long prose), `fit_justification` (paragraph), `score` (1-5), `sub_scores` (3 dims), `confidence` (1-4), `best_paper_candidate` (boolean)
- **Score scale**: 1-5 (5=Accept, 4=Weak Accept, 3=Borderline, 2=Weak Reject, 1=Reject)
- **Verdict vocabulary**: "Accept", "Weak Accept", "Borderline", "Weak Reject", "Reject"
- **Sub-dimensions** (each 1-5):
  - `fit`: alignment with ACM Multimedia Topics (5=Perfect match, 4=Large audience, 3=Relevant to part of community, 2=Small audience, 1=Out-of-scope)
  - `technical_quality`: 5=Outstanding, 4=Excellent, 3=Good, 2=Medium, 1=Low
  - `technical_presentation`: 5=Excellent, 4=Good, 3=Fair, 2=Poor, 1=Very poor
- **Confidence scale**: 1-4 (4=Expert, 3=Knowledgeable, 2=Familiar, 1=Not my area)

### ACM MM Asia

Same form as ACM MM (inherits dims, scale, vocabulary, form_fields).

### NeurIPS

- **Aliases**: `neurips`, `nips`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `limitations`, `score` (1-6), `sub_scores` (4 dims), `confidence` (1-5)
- **Score scale**: 1-6 (6=Strong Accept, 5=Accept, 4=Borderline accept, 3=Borderline reject, 2=Reject, 1=Strong Reject)
- **Verdict vocabulary**: "Strong Accept", "Accept", "Borderline Accept", "Borderline Reject", "Reject", "Strong Reject"
- **Sub-dimensions** (each 1-4): `quality`, `clarity`, `significance`, `originality`
- **Confidence scale**: 1-5 (5=Absolutely certain, 4=Confident, 3=Fairly confident, 2=Willing to defend, 1=Educated guess)

### ICLR

- **Aliases**: `iclr`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `limitations`, `score` (0-10), `sub_scores` (3 dims), `confidence` (1-5)
- **Score scale**: 0-10 (10=Strong Accept top 5%, 8=Accept top 50%, 6=Marginally above threshold, 4=Marginally below threshold, 2=Reject, 0=Strong Reject)
- **Verdict vocabulary**: "Strong Accept", "Accept", "Marginal Accept", "Marginal Reject", "Reject", "Strong Reject"
- **Sub-dimensions** (each 1-4): `soundness`, `presentation`, `contribution`
- **Confidence scale**: 1-5

### ACL Rolling Review (ARR) / EMNLP / NAACL / EACL / AACL

- **Aliases**: `acl`, `arr`, `emnlp`, `naacl`, `eacl`, `aacl`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions_for_authors`, `score` (1-5 with half-points), `sub_scores` (3 dims), `confidence` (1-5), `ethics_concerns`, `presentation_format`
- **Score scale**: 1-5 (5.0=Consider for Award, 4.0=Conference acceptance, 3.0=Findings acceptance, 2.0=Resubmit next cycle, 1.0=Do not resubmit, plus 0.5-step Borderlines)
- **Verdict vocabulary**: "Consider for Award", "Conference acceptance", "Findings acceptance", "Resubmit next cycle", "Do not resubmit"
- **Sub-dimensions** (each 1-5): `soundness`, `excitement`, `reproducibility`
- **Confidence scale**: 1-5 (5=Very confident, 1=Not my area)

### ICML

- **Aliases**: `icml`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `score` (1-6), `sub_scores` (4 dims), `confidence` (1-5)
- **Score scale**: 1-6 (Strong Accept / Accept / Weak Accept / Weak Reject / Reject / Strong Reject)
- **Sub-dimensions** (each 1-4): `soundness`, `presentation`, `significance`, `originality`

### AAAI

- **Aliases**: `aaai`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `score` (1-6), `sub_scores` (3 dims), `confidence` (1-5)
- **Score scale**: 1-6 (same labels as ICML)
- **Sub-dimensions** (each 1-5): `soundness`, `originality`, `significance`

### CVPR / ICCV / ECCV (CVF venues)

- **Aliases**: `cvpr`, `iccv`, `eccv`, `wacv`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `score` (1-5), `confidence` (1-5)
- **Score scale**: 1-5 (Strong Accept / Weak Accept / Borderline / Weak Reject / Strong Reject)
- **No sub-scores** (CVF venues use the overall score directly)
- **Confidence scale**: 1-5 (5=Expert, 3=Confident, 1=Outsider)

### COLM (Conference on Language Modeling)

- **Aliases**: `colm`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `score` (1-10), `sub_scores` (3 dims), `confidence` (1-5)
- **Score scale**: 1-10 (Strong Accept 10 / Accept 8 / Marginal accept 6 / Borderline 5 / Marginal reject 4 / Reject 2 / Strong Reject 1)
- **Sub-dimensions** (each 1-4): `soundness`, `presentation`, `contribution`

### AISTATS

- **Aliases**: `aistats`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `score` (1-6), `sub_scores` (4 dims), `confidence` (1-5)
- **Score scale**: 1-6 (same labels as ICML)
- **Sub-dimensions** (each 1-4): `soundness`, `presentation`, `significance`, `originality`

### IJCAI

- **Aliases**: `ijcai`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `questions`, `score` (1-10), `sub_scores` (4 dims), `confidence` (1-5)
- **Score scale**: 1-10 (Top 5% / Top 25% / Top 50% / Borderline / Bottom 50% / Bottom 25% / Bottom 5%)
- **Sub-dimensions** (each 1-4): `originality`, `soundness`, `significance`, `clarity`

### TPAMI / JMLR / TMLR / TACL (journals)

- **Aliases**: `tpami`, `jmlr`, `tmlr`, `tacl`, `journal`
- **Required fields**: `summary`, `strengths`, `weaknesses`, `detailed_comments`, `score` (1-4), `sub_scores` (4 dims), `confidence` (1-4)
- **Score scale**: 1-4 (Accept / Accept w/ Minor Revisions / Major Revisions / Reject)
- **Sub-dimensions** (each 1-4): `soundness`, `novelty`, `significance`, `clarity`
- **Note**: journals expect more thorough Detailed Comments — multiple paragraphs covering each section of the paper

### Other supported venues

KDD / WWW / MLSys / BMVC / ACCV / CoRL / ICRA / INTERSPEECH / OSDI / COLT / COLING / UAI — pattern is similar to closest peer. Ask the user for the exact form via AskUserQuestion, OR fall back to the default template.

---

## Sentence template source (live, not inlined)

Earlier versions of this skill (≤ v2) inlined a fixed 300-sentence pool. v3 removes the inline pool and pulls fresh templates from the live corpus on every invocation, via the CLI in workflow step 3. This means:

- Pool size grows automatically as new reviews are collected and GPTZero-filtered. Current corpus: 14 venue-year buckets across COLM 2024-2025, ICLR 2018-2024, NeurIPS 2021-2025, ICML 2025; ~500 GPTZero-verified human reviews and counting; 5 canonical buckets × 1100-2600 sentences each.
- Per-venue × per-field sampling — ACM MM gets ACM MM-shaped sentences when the venue is in the corpus; cross-venue canonical fallback (SUMMARY/STRENGTHS/WEAKNESSES/QUESTIONS/FULL) when not.
- Few-shot examples are real complete reviewer JSONs from the corpus, not paraphrased.

The CLI output (`/tmp/templates.md`) is markdown with two sections:
- per-venue × per-field sentence pools, keyed by raw OpenReview field name (e.g. `weaknesses`, `reasons_to_reject`, `questions`, `comment`, `main_review`)
- 2 complete few-shot reviewer JSONs to anchor voice and structure

**Setup**: this skill assumes the source repo (research_harness) is on `PYTHONPATH` so `python -m research_harness.stages.review.review_corpus.pipeline.sample_for_venue` resolves. If the CLI errors with `INDEX_PATH missing`, run `python -m research_harness.stages.review.review_corpus.pipeline.extract_by_field` once to build the index from the current corpus, then retry the sample.

For background on why this verbatim-template approach works (and why prompt-only abstract-rule approaches fail), see `research_harness/stages/review/review_corpus/LESSONS.md` in the source repo.
