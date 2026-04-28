---
name: self-paper-review
version: 1.4.0
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

   With weaknesses set aside, **score each of the four dimensions
   below on its own 1-10 scale, then take the unweighted average to
   get the base value**. Do NOT skip the dimensional scores and
   directly write a single number — the dimensional decomposition is
   what produces useful spread across papers. (Earlier versions of
   this skill that asked for a single number directly produced
   distribution collapse: 4/5 papers all received the same modal
   rating regardless of their actual differences.)

   For each dimension, score 1-10 against the venue's bar (use ICLR
   as default). Use the same per-point ICLR anchors below for each
   dimension. State each score on its own line with one-sentence
   evidence from the paper.

   - **Problem importance** (P): is this a real problem the venue's
     community cares about?
     - 8: a problem multiple top-tier papers per year address.
     - 6: a problem the subfield acknowledges but is not the
       hottest direction.
     - 4: a niche / under-motivated problem.
     - 2: out-of-scope or contrived.
   - **Conceptual contribution** (C): does the paper propose something
     genuinely new — a method, a phenomenon, a connection, a benchmark
     — vs. a straightforward combination of existing pieces?
     - 8: a new mechanism, theoretical insight, or empirical finding
       that did not exist before.
     - 6: a real but incremental contribution (a new variant, a new
       application of an existing technique, a new analysis tool).
     - 4: a known method on a slightly different setting.
     - 2: nothing new beyond engineering.
   - **Execution** (E): is the experimental scope, model sizes,
     dataset coverage, and rigor at the venue's bar?
     - 8: comprehensive experiments across multiple settings, strong
       baselines, error bars, ablations.
     - 6: standard execution at the venue's bar.
     - 4: thin experiments (one dataset, one seed, weak baselines).
     - 2: experiments do not actually test the claim.
   - **Impact / interest** (I): would a researcher in the area
     actively want to read, cite, or build on this paper?
     - 8: yes, will be on a follow-up paper's reading list.
     - 6: noted by the subfield but not pivotal.
     - 4: of limited interest beyond a small group.
     - 2: unlikely to be read.

   Then compute:

       base value = round((P + C + E + I) / 4)

   Write the four scores and the resulting base value explicitly.
   You commit to this base value *before* the weakness pass biases
   you downward.

   **Calibration anchors — ICLR-style 1-10 scale**.

   The single biggest source of miscalibration in earlier versions of
   this skill was using vague band-anchors ("NeurIPS-quality = 7-8").
   Use the explicit per-point anchors below. When in doubt between two
   adjacent points, default to the *higher* one — the well-known LLM
   bias is to under-rate, not over-rate, so an active counter-bias
   keeps the base near the real distribution.

   - **10**: best-paper / oral-tier. Rare; top ~1%. Genuinely changes
     how the field thinks about the problem. If you are tempted to
     give 10 you are almost certainly wrong; reserve it for a
     once-a-year paper.
   - **8**: strong accept. Top ~15-20% at ICLR/NeurIPS. A real new
     method or phenomenon, clear motivation, solid experiments across
     more than one setting, the kind of paper a researcher in the area
     wants to read on day one. Most "spotlight" papers land here.
   - **6**: weak accept / borderline accept. The modal accepted poster
     at ICLR/NeurIPS. A real (often incremental) contribution, decent
     execution, no fatal flaw — the kind of paper that gets in but
     reviewers do not push to highlight. **If the paper has a real
     method that works on standard benchmarks at the venue's bar,
     default to 6 unless something clearly elevates or deflates it.**
   - **5**: borderline reject / weak reject. Either the contribution
     is small (one knob change, one new dataset, one new variant) or
     the execution is below the venue bar (single seed, missing
     baseline, narrow domain) but the paper is not fundamentally wrong.
     A reviewer leaning negative still goes here, not lower.
   - **3**: clear reject. Known method on a marginally different
     dataset with no new mechanism, OR experiments contradict the
     claim, OR the paper does not target a problem the venue cares
     about.
   - **1**: strong reject. Method is wrong (broken theorem, fabricated
     data, unsupported claim contradicted by the paper's own
     experiments) or out-of-scope.

   How to pick the number:
   1. Locate which two adjacent anchors the paper falls between.
   2. Pick the higher of the two unless you can name a *specific*
      reason to drop. "Could be more rigorous" / "I would have liked
      more analysis" / "writing could be tighter" are NOT reasons to
      drop — they go in `## What's wrong` later. Only "the
      contribution is genuinely smaller than the higher anchor
      requires" is a reason to drop.
   3. Round to integer. Half-points are not part of the scale; they
      indicate you are hedging instead of committing. If you wrote
      6.5, decide whether the contribution clears the 7-anchor bar
      ("strong accept territory") or sits at the modal-accept-poster
      bar (6).
   4. **Cross-check by venue distribution**: the modal accepted ICLR
     paper is rated 6 by reviewers. If your base is below 5, you are
     claiming this paper would not be accepted at ICLR; that is a
     strong claim and should match a specific deficit in
     contribution, not vibes about polish.

   "Lots of weaknesses" alone does NOT lower the base value — a paper
   can be base-value 8 *and* still have 15 weaknesses. The weaknesses
   go in their own list (step 6); the base value reflects only the
   contribution, not the polish.

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
   - `## Base value` — the four dimensional scores from step 4, plus
     the average. Required format:

         - Problem importance (P): <N>/10 — <evidence>
         - Conceptual contribution (C): <N>/10 — <evidence>
         - Execution (E): <N>/10 — <evidence>
         - Impact / interest (I): <N>/10 — <evidence>
         - **Base value = round((P + C + E + I) / 4) = <N>/10**

     Do not skip the dimensional breakdown. Do not pre-decide the base
     value and then write dimensions to match it; do dimensions first
     and let the average produce the base.
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

   **Recommendation rule (strict)**:

       final rating = base value (from step 4, unchanged)

   That is: the weakness list does NOT lower the rating, no matter how
   long it is or how severe the items look. The list goes into
   `## What's wrong` so the user can use it to revise the paper, but
   it does not drive the verdict.

   Why this rule (read once and internalize):
   v1.0 of this skill let weakness count drive the rating directly,
   producing 5/5 systematically under-rated papers (e.g. ratings of 8
   read as "borderline-to-weak"). v1.1 tried to fix it by allowing
   only Major deal-breakers to subtract — but LLMs (you, me, all of
   us) cannot reliably distinguish Major from Medium and consistently
   over-classify ordinary "could-be-improved" issues as Major. v1.2
   removes the subtraction entirely. The base value from step 4 is
   the only thing reflected in the rating; the weakness list is
   reflected in the *content* of `## What's wrong` instead.

   The base value already incorporates a critical look at the
   contribution (step 4 explicitly tells you to be honest about a
   small / standard / unoriginal contribution → low base). So if you
   judge the paper has a true fatal flaw, that should already be
   visible in your base value, not bolted on later as a "Major
   deduction."

   Output format for `## Recommendation`:

       Final rating estimate: <N>/10 (= base value). At <venue> as
       currently written, this paper would <accept / borderline /
       reject>. <one sentence on the single most important thing in
       `## What's wrong` for the user to fix>.

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
