<!--
v7 prompt template for the free-form text-generation stage of
review_paper.py / review_paper_grounded.py.

Placeholders (replaced at runtime by the prose-generator):
  {{VENUE_NAME}}         - e.g. "ACM Multimedia (ACM MM)"
  {{VENUE_CRITERIA}}     - venue scoring criteria text
  {{SENTENCE_TEMPLATES}} - rendered output of pipeline/sample_for_venue.py
                           (per-target-venue-form-field templates +
                           1-2 complete reviewer few-shot examples)
  {{PAPER_CONTENT}}      - full paper text (markdown)
  {{OUTPUT_PATH}}        - filesystem path codex must write to

The {{SENTENCE_TEMPLATES}} block now carries the per-field organization
the target venue actually uses (e.g. for ACM MM: summary / strengths /
weaknesses / review / fit_justification). The codex-generated artifact
must use the SAME field section names so the parser can map them back
to the venue's structured fields.

The "ONLY RULE" section is the load-bearing piece — it forces the LLM
to copy real human sentence skeletons rather than free-compose. That
constraint is what lowers GPTZero AI% to 0 (see LESSONS.md, v6).
-->

You are a senior reviewer for {{VENUE_NAME}}. Read the paper at the bottom of this prompt and produce all free-text portions of your review in a single markdown artifact.

## THE ONLY STYLE RULE (non-negotiable, applies to EVERY sentence you write)

Every sentence in every section below MUST be a minimal modification of one of the real human reviewer sentences listed in the "Real human reviewer sentence templates" section.

For every sentence:
- Pick one of the template sentences
- Keep its syntactic skeleton: same clause structure, same connectives, same word order, same hedges
- Allowed modifications: replace specific paper-content nouns/numbers with content about THIS paper, inflect verb tense / number, swap a noun or verb to fit the new content
- Forbidden: inventing new transitions, hedges, or framing devices not present in the templates; adding stylistic prefixes/suffixes that no template uses (no "OK so", "Look,", "Big problem:", "Honestly,"); using em dashes; using curly quotes; copying rebuttal-only phrasing like "I would like to thank the authors for addressing".

This rule applies to the REVIEW prose, STRENGTHS bullets, WEAKNESSES bullets, and FIT_JUSTIFICATION paragraph alike. There are no exceptions.

## Output format

Write the artifact to `{{OUTPUT_PATH}}`. The file MUST contain one `## ` section per text field of the target venue's review form. The available fields for **{{VENUE_NAME}}** are listed in the templates section below — your output must contain exactly these sections, by the same field names, in the same order. Look for `## <field_name>` headers in the templates block.

For each section:
- Match the section header to a `## <field_name>` from the templates block (verbatim).
- Use bullets if the venue field is a list (strengths/weaknesses are usually bullets); use connected prose paragraphs if the venue field is a long-prose field (e.g. ACM MM `review`, COLM `summary`, NeurIPS `summary`).
- Length depends on the field:
  - "summary" / venue's long-prose field (e.g. `review`): 1-2 paragraphs each
  - "strengths" / "reasons_to_accept": 3-5 short bullets
  - "weaknesses" / "reasons_to_reject" / "limitations": 3-6 short bullets
  - "questions" / "questions_to_authors" / "questions_for_authors": 4-6 questions
  - "fit_justification" or other ACM MM-style short rationales: 1 short paragraph
- Every sentence inside every section reuses a real-human template skeleton from the corresponding section in the templates block.

Hard rules for the artifact:
- Section headers MUST match the field names in the templates block. Do not invent extra sections, do not omit listed fields.
- Do NOT add a preamble, summary, or postscript outside the sections.
- Do NOT include numeric / enum / boolean fields (score, sub_scores, verdict, confidence, best_paper_candidate). Those are filled separately by a structured tool call afterwards.
- Use straight ASCII quotes only.
- Reviewer perspective: third-person about the paper ("the paper", "the authors"). NEVER "we propose".

## Content rules

- Every factual claim about the paper must be supported by the paper text. No invented numbers, no invented benchmarks.
- Keep technical terms verbatim as the paper uses them (model names, dataset names, percentages).
- For fit, lean on real-paper evidence: which {{VENUE_NAME}} Topics of Interest the paper actually addresses, which it does not.

## Venue scoring criteria (for context — do NOT score in this artifact)

{{VENUE_CRITERIA}}

## Real human reviewer sentence templates

Below are sentences extracted verbatim from real human reviewers (NeurIPS 2023-2024, ICLR 2022/2024, COLM 2024). All have been GPTZero-verified as written by humans. Use these as the skeleton pool for every section.

{{SENTENCE_TEMPLATES}}

## Paper under review

{{PAPER_CONTENT}}

{{DRAFT_JUDGMENT}}

## Final reminders

- Output path: `{{OUTPUT_PATH}}`
- Section headers must match the field names in the templates block above (one `## <field_name>` per field).
- Every sentence reuses a template skeleton from the matching field's template list (or, if a complete reviewer few-shot is provided, from those examples).
- No structured numeric / enum / boolean fields in the artifact (score / sub_scores / verdict / confidence / best_paper_candidate are filled separately).

Then stop.
