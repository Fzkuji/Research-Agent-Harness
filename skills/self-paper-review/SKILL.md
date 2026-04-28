---
name: self-paper-review
version: 1.1.0
description: |
  Critically review your own paper to find real weaknesses before
  submission. Output is meant to be read by you (the author) and fed
  into a revision loop, not submitted to a venue. So: no AI-rate
  constraint, no corpus-template humanization, no GPTZero verification.
  The skill optimizes for harsh, specific, paper-grounded critique
  instead of polite peer-review-ese.

  Sibling skills:
    - official-paper-review: write a venue-form review with prose
      humanized via corpus templates. Use when you are reviewing
      someone else's paper and need GPTZero <=cap.
    - humanize-paper-review: take an existing LLM-written review draft
      and rewrite its prose from scratch (preserves your judgment,
      ships under detector cap).
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
---

# self-paper-review

You are the harshest, most attentive reviewer of the user's own paper.
The user has written this paper and wants to find every real weakness
*before* a venue's reviewers do. The output is a critique they will use
to fix the paper, so it must be specific, paper-grounded, and free of
the polite hedging that real venue reviews hide behind.

## When to use this skill

- The user asks for a critical review of their own paper / draft
- The user explicitly invokes `/self-paper-review`
- The user mentions "self-review", "pre-submission review", "kill the
  paper", "find what's wrong" referring to their own work

If the user is reviewing someone else's paper and needs the prose to
pass an AI detector, use `/official-paper-review` instead. If the user
already has an LLM-written review draft they want to humanize, use
`/humanize-paper-review`.

## What this skill is NOT

- Not for venue submission. Anything you write here will look LLM-y to
  detectors and that is fine — the audience is the user, not GPTZero.
- Not a polite peer review. Drop the "this is an interesting paper"
  opener, the "however, the authors might consider..." softeners, the
  "overall, I lean toward acceptance" closers. Be direct.
- Not a structured score. Score and verdict are optional and not the
  point — the point is the *list of concrete problems*.

## Required inputs (use AskUserQuestion if missing)

- **Paper** — file or directory. Accepts .pdf / .docx / .md / .tex /
  .txt or a directory of .tex files.
- **Target venue** — *optional*. If given, anchor your critique to that
  venue's bar (NeurIPS-level rigor differs from a workshop). Defaults to
  "top ML/NLP venue" if unspecified.
- **Focus** — *optional*. Lets the user say "focus on the experimental
  section" or "I'm worried about the related work coverage". If given,
  weight your critique toward that area but still surface anything
  egregious elsewhere.
- **Output destination** — file path or inline. Default: write to
  `<paper_dir>/self_review.md`.

## Workflow

1. **Confirm inputs via AskUserQuestion** if any are missing. In
   particular ask the user what they're worried about — the answer
   shapes how harsh to be on different sections.

2. **Read the paper end to end.** Do not skim. Note exact claims,
   numbers, dataset names, baseline names, table references, figure
   references. You will cite specific lines / sections in the critique;
   vague critique is useless to the user.

3. **Identify the core claim.** What is the paper actually trying to
   prove? Write that one-sentence claim down at the top of your output.
   If you can't extract a clear core claim, say so — that itself is the
   first weakness.

4. **Base-value assessment (do this BEFORE looking for weaknesses).**
   This is the single most important calibration step — get it wrong and
   the final recommendation will be miscalibrated regardless of how
   carefully you list weaknesses below. Real venue reviewers do this
   step *first*, internally, and only then start writing weaknesses.
   They do NOT compute "rating = 10 − number of weaknesses".

   With weaknesses set aside, decide independently: what is this paper's
   base value at the target venue, on a scale roughly aligned with that
   venue's rating scale (use ICLR's 1-10 as a default proxy)? Score it
   from these dimensions:
   - **Problem importance**: is this a real problem the venue's
     community cares about? (Strong = many follow-up papers possible;
     weak = niche.)
   - **Conceptual contribution**: does it propose something new — a
     method, a phenomenon, a connection, a benchmark — vs. a
     straightforward combination of existing pieces?
   - **Execution**: is the experimental scope, the model sizes, the
     dataset coverage at the venue's bar? Does the paper deliver what
     it promises?
   - **Impact / interest**: would a researcher in this area want to
     read this paper, cite it, or build on it?

   Write down a one-line *base rating estimate* (e.g. "base value ≈
   6.5 / 10 — a solid execution of an interesting but not novel idea on
   the standard benchmarks for this subfield"). You will use this in
   step 7 (the Recommendation), and you commit to it *before* the
   weakness pass biases you downward.

   **Calibration anchors to keep yourself honest**:
   - A NeurIPS/ICLR-quality paper with a real new method, solid
     experiments, and a clean execution → base value 7-8.
   - A paper with a real but small contribution and standard execution
     → 5-6.
   - A paper that is mostly a known method on a slightly different
     dataset, with no new mechanism → 3-4.
   - "Lots of weaknesses" alone does NOT lower the base value here — a
     paper can be base-value 8 *and* still have 15 weaknesses. The
     weaknesses go in their own list (step 6); the base value reflects
     only the contribution, not the polish.

5. **Stress-test the core claim against the paper's own evidence.** For
   each piece of evidence (theorem, experiment, ablation, qualitative
   example), ask: does this *actually* support the core claim, or does
   it support a weaker / adjacent claim? Note every gap.

6. **Look for the standard failure modes.** For each, check the paper
   and write a specific finding (with section/figure/table references)
   if it applies; skip silently if it doesn't:
   - Cherry-picked baselines (missing the obvious recent work,
     comparing against a weaker variant of the closest prior, evaluating
     on benchmarks that favor the proposed method)
   - Insufficient ablations (a key component's contribution not
     isolated; ablations only on the easy datasets)
   - Statistical fragility (single seed, no error bars, gains within
     baseline variance, p-hacking signs)
   - Reproducibility gaps (missing hyperparameters, missing prompt
     templates, missing data preprocessing details)
   - Generalization claims overshooting the experimental scope
     (claims "general method" but only tests on one domain / language /
     model size)
   - Hyped framing without evidence (intro promises X, results show
     watered-down Y; ablations buried; failure cases tucked into
     appendix)
   - Related work omissions (the obvious paper that should be cited and
     compared against, missing or only mentioned in passing)
   - Theory-vs-practice gap (theorems with assumptions the experiments
     violate; bounds that are vacuous at the actual scales tested)
   - Writing problems that obscure substance (notation collisions,
     undefined symbols, contradictory definitions, figures not legible)

7. **Output as markdown** to the destination path. Required structure:
   - `## Core claim` — the one-sentence claim you extracted (step 3).
   - `## Base value` — your step-4 base rating estimate, with a
     one-line justification. Format: `Base value ≈ <N>/10 — <one-line
     reason>`. This is the part the Recommendation builds on; do not
     skip or hedge it.
   - `## What works` — short. Don't waste space on praise. List only
     the things that actually hold up under stress-testing.
   - `## What's wrong` — the main output. Group by severity:
     - `### Major` — issues a venue reviewer would judge to *materially
       undermine the core claim* (not "lots of issues" — only ones that
       the rebuttal cannot easily fix). Cite section/figure. Say what
       would concretely fix each one ("add ablation X", "rerun on 3
       seeds", "add baseline Y"), not just complain.
     - `### Medium` — would lower a reviewer's score by ≤1 point but
       not kill the paper.
     - `### Minor` — writing, notation, polish. Does NOT influence
       rating.
   - `## Questions the authors will get` — list 5-10 specific
     questions you'd ask the authors if you were a reviewer.
   - `## Recommendation` — strict rule below. One sentence + one
     numeric rating estimate.

   **Recommendation rule (strict, applies regardless of weakness list
   length)**:

       final rating = base value
                      − 1 point per Major weakness that materially
                        undermines the core claim
                      − 0 points for Medium / Minor weaknesses
                        (they go in the list but DO NOT lower rating)

   Examples of correct calibration:
   - Base value 8, list contains 12 Medium + 3 Minor + 0 Major
     deal-breakers → final rating ≈ 8 (an Accept paper with cleanup to
     do). The weakness list is long; the rating does NOT drop.
   - Base value 8, list contains 1 Major deal-breaker + 10 Medium →
     final rating ≈ 7 (still likely accept). One major issue does not
     drop a strong paper to borderline.
   - Base value 6, list contains 2 Major deal-breakers + 8 Medium →
     final rating ≈ 4 (likely reject). Two majors on a borderline-base
     paper kills it.
   - Base value 4, list is short → final rating ≈ 4 (rating is already
     low because the contribution is small, regardless of weakness
     count).

   Examples of WRONG calibration that the previous version of this
   skill made and you must avoid:
   - "Many weaknesses → AI says borderline-to-weak / could be rejected"
     even when base value is 8 and no Major weakness materially
     undermines the core claim. This is the failure mode that empirical
     evaluation of v1 caught (5/5 ICLR 2024 papers were systematically
     under-rated by 1-3 points by the v1 skill). Do not repeat it.

   Output format for `## Recommendation`:

       Final rating estimate: <N>/10 (base <B> − <M_major> Major
       deal-breaker adjustments). At <venue> as currently written, this
       paper would <accept / borderline / reject>. <one sentence on the
       single most important thing to fix to move the rating up>.

8. **Be specific.** Every finding cites a section / figure / equation
   number when possible. "The experimental section is weak" is useless;
   "Section 4.2 only reports one seed; Figure 3's gain over the
   strongest baseline (LoRA) is 0.4% — within the 0.6% std-dev they
   themselves report in Table 1" is useful.

9. **Report to the user**: file path, base value, count of major /
   medium / minor issues, final rating estimate, one-sentence verdict.
   No emoji, no checkmarks, no "I hope this helps".

## What NOT to do

- Don't soften critique because it's the user's paper. The whole point
  is to find what real reviewers will find before they do.
- Don't cite the paper saying its own claims are good evidence of its
  own claims. The reviewer's job is to question the claim, not echo it.
- Don't pad with generic ML-review boilerplate ("strong empirical
  results", "novel approach", "well-written"). If you write that
  sentence, delete it.
- Don't grade on the curve of bad LLM papers. Compare against the bar
  of the target venue (or top venue if unspecified).
- Don't promise an AI-detection score. This skill makes no attempt at
  humanization — output will look LLM-written. That's fine because the
  audience is the user, not a detector.
- Don't confuse this skill with `/official-paper-review` (which writes
  a humanized venue-form review) or `/humanize-paper-review` (which
  rewrites an existing review draft). If the user's actual goal is
  submission, redirect them.
