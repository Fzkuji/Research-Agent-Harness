"""Writing principles for academic papers — reference document."""

WRITING_PRINCIPLES = r"""
# Writing Principles for Academic Papers

## The Narrative Principle (Neel Nanda + Andrej Karpathy)

A paper is a short, rigorous, evidence-backed technical story.
By the end of the Introduction, the reader should understand:
- The What: 1-3 specific claims
- The Why: evidence supporting those claims
- The So What: why the community should care

A strong paper "sells" ONE thing. If the core contribution cannot be
stated in one sentence, the framing has not converged.

One-Sentence Contribution Test:
- "We prove that X converges under assumption Y."
- "We show that method A improves B by 15% on benchmark C."
- "We identify failure mode D and propose mechanism E that removes it."

## Time Allocation (Reviewer Reading Order)

Spend roughly equal time on: (1) Abstract, (2) Introduction,
(3) Figures, (4) everything else combined.

Reviewers read: Title → Abstract → Introduction → Figure 1 → the rest.
Put disproportionate effort into the first two pages.

## Abstract: Five-Sentence Formula (Sebastian Farquhar)

1. What you achieved
2. Why the problem is important and difficult
3. How you approached it
4. What evidence supports the claim
5. What number/result the reader should remember

Delete generic openings that fit any ML paper:
- "Large language models have achieved remarkable success..."
- "In recent years, deep learning has..."

## Introduction Structure (~1-1.5 pages)

1. Opening hook — what problem, why now
2. Background/challenge — why hard, what prior work tried
3. Approach overview — what this paper does differently
4. Contribution bullets — 2-4 items, specific and falsifiable
5. Results preview — strongest result early
6. Optional roadmap

Good bullets: "We prove X converges in O(n log n) under assumption Y."
Bad bullets: "We study problem X." / "We perform extensive experiments."

## Sentence-Level Clarity (Gopen & Swan)

1. Keep subject and verb close
2. Put important information near the end
3. Put context at the start
4. Move from old to new information
5. One paragraph = one job
6. Put actions in verbs ("We analyzed" not "We performed an analysis")
7. Set the stage before new material

## Word Choice (Zachary Lipton)

Remove needless hedging (may/can/might/potentially) unless genuine.

Replace vague terms:
- performance → accuracy / F1 / latency
- improves → increases by X%
- large → 1B parameters
- good results → 92% accuracy

Keep terminology consistent — don't mix model/network/architecture.

## Figure Design

- Figure 1 is crucial — explain core method or show strongest comparison
- Captions must be self-contained
- No decorative titles inside figures
- Use vector graphics (PDF/EPS)
- Colorblind-safe palettes, avoid red-green

## Pre-Submission Checklist

Narrative:
- [ ] Contribution stated in one sentence
- [ ] Introduction: What / Why / So What clear
- [ ] Every experiment supports a clear claim

Structure:
- [ ] Abstract follows five-sentence formula
- [ ] Introduction within 1-1.5 pages
- [ ] Method starts by page 2-3
- [ ] 2-4 concrete contribution bullets
- [ ] Limitations clearly stated

Writing:
- [ ] Consistent terminology
- [ ] No generic field-background openings
- [ ] Unnecessary hedging removed
- [ ] All figures have self-contained captions

Technical:
- [ ] Citations verified
- [ ] Error bars and statistical reporting clear
- [ ] Compute resources documented
- [ ] Code/data availability stated
""".strip()
