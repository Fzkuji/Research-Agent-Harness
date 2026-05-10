"""Unified paper-review entry — one function, two modes.

Modes:
  peer    Venue-form peer review of someone else's paper. Internally
          three steps:
            1. codex writes a long, detailed, free-form draft (no
               template constraint, paper-grounded specifics).
            2. extract_judgment compresses the draft into a structured
               judgment dict (numerics + per-field bullets).
            3. generate_review_text rewrites prose under the real-human
               sentence-template constraint, using bullets + paper +
               templates. Numerics from the draft are kept.
          One CLI call. No --draft option (the draft is always produced
          internally, never supplied externally).

  revise  Multi-round ARIS-style review-fix loop on your own paper.
          Multiple personas, optional Area Chair meta-review, optional
          auto-fix. No AI-detector concern, no template humanization.
          Designed to surface real weaknesses before submission.

Library use:
    from research_harness.review import review
    r = review("paper.pdf", venue="NeurIPS")                  # peer
    r = review("paper.pdf", venue="NeurIPS", mode="revise",
               max_rounds=4, auto_fix=True)

CLI:
    research-review paper.pdf --venue "ACM MM 2026"
    research-review paper.pdf --venue NeurIPS --mode revise --max-rounds 4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from openprogram.agentic_programming.runtime import Runtime
from openprogram.providers import create_runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, render_criteria_text,
)
from research_harness.stages.review.load_paper import load_paper
from research_harness.stages.review.review_paper import review_paper
from research_harness.stages.review._extract_judgment import extract_judgment
from research_harness.stages.review._codex_run import run_codex
from research_harness.stages.review import review_loop


def review(
    paper: str,
    venue: str = "NeurIPS",
    *,
    mode: str = "peer",
    exec_runtime: Optional[Runtime] = None,
    review_runtime: Optional[Runtime] = None,
    work_dir: Optional[str] = None,
    provider: str = "auto",
    review_provider: str = "openai-codex",
    review_model: Optional[str] = None,
    # revise mode only
    max_rounds: int = 4,
    auto_fix: bool = False,
    num_reviewers: int = 4,
    difficulty: str = "medium",
    with_grounding: bool = True,
    pass_threshold: int = 6,
) -> dict:
    """Unified paper-review entry.

    Args:
        paper:           File or directory containing the paper.
        venue:           Target venue.
        mode:            "peer" (someone else's paper, three-step write
                         -> extract -> humanize) or "revise" (multi-round
                         self-review).
        exec_runtime:    Author-side runtime (paper conversion).
        review_runtime:  Reviewer-side runtime.
        work_dir:        Runtime work directory. Default: paper's parent.
        provider / review_provider / review_model:
                         used when runtimes are None.
        max_rounds, auto_fix, num_reviewers, difficulty, with_grounding,
        pass_threshold:  revise mode only.

    Returns:
        dict — review JSON for peer mode, or review_loop result dict
        for revise mode.
    """
    if mode not in ("peer", "revise"):
        raise ValueError(
            f"mode must be 'peer' or 'revise', got {mode!r}"
        )

    paper_path = os.path.abspath(os.path.expanduser(paper))
    if not os.path.exists(paper_path):
        raise FileNotFoundError(paper_path)

    if work_dir is None:
        work_dir = (os.path.dirname(paper_path) if os.path.isfile(paper_path)
                    else paper_path)
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if exec_runtime is None:
        exec_runtime = create_runtime(provider=provider)
        exec_runtime.set_workdir(work_dir)
    if review_runtime is None:
        review_runtime = create_runtime(
            provider=review_provider, model=review_model,
        )
        review_runtime.set_workdir(work_dir)

    if mode == "peer":
        return _review_peer(
            paper_path=paper_path, venue=venue,
            exec_runtime=exec_runtime, review_runtime=review_runtime,
        )
    return _review_revise(
        paper_path=paper_path, venue=venue,
        exec_runtime=exec_runtime, review_runtime=review_runtime,
        max_rounds=max_rounds, auto_fix=auto_fix,
        num_reviewers=num_reviewers, difficulty=difficulty,
        with_grounding=with_grounding, pass_threshold=pass_threshold,
    )


def _write_detailed_draft(paper_content: str, venue_spec, venue_criteria: str,
                          model: str = "gpt-5.5",
                          reasoning_effort: str = "medium",
                          timeout_s: int = 600) -> str:
    """Phase 1 of peer mode: codex writes a long, detailed, paper-grounded
    review with NO template constraint and NO AI-detection concern.

    Output is a markdown file with the section headers extract_judgment
    expects (Summary / Strengths / Weaknesses / Review / Fit Justification
    or whatever the venue uses), plus structured numerics at the top.

    Returns the markdown text. Caller decides what to do with it (next
    step extracts the judgment and re-renders prose under templates).
    """
    if shutil.which("codex") is None:
        raise RuntimeError("codex CLI not on PATH; install or fix PATH")

    workdir = Path(tempfile.mkdtemp(prefix="detailed_draft_",
                                    dir=os.getcwd()))
    try:
        out_path = workdir / "draft.md"
        prompt = _build_detailed_draft_prompt(
            paper_content=paper_content,
            venue_spec=venue_spec,
            venue_criteria=venue_criteria,
            output_path=str(out_path),
        )
        prompt = prompt.replace("\x00", "")
        cmd = [
            "codex", "exec",
            "--sandbox", "workspace-write",
            "--skip-git-repo-check",
            "--cd", str(workdir),
            "-c", f'model_reasoning_effort="{reasoning_effort}"',
            "--model", model,
            prompt,
        ]
        result = run_codex(cmd, timeout_s=timeout_s)
        if result.returncode != 0:
            # Even if rc != 0, the file may exist (codex finished writing
            # before the parent process died). Try to read it anyway.
            print(f"[detailed_draft] codex rc={result.returncode}; "
                  f"checking file on disk", file=sys.stderr)
        if not out_path.exists():
            raise RuntimeError(
                f"detailed_draft did not write {out_path}; "
                f"stderr: {result.stderr[-500:]}"
            )
        text = out_path.read_text(encoding="utf-8")
        if len(text) < 500:
            raise RuntimeError(
                f"detailed_draft produced only {len(text)} chars; "
                f"first 200: {text[:200]!r}"
            )
        return text
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _build_detailed_draft_prompt(*, paper_content: str, venue_spec,
                                 venue_criteria: str,
                                 output_path: str) -> str:
    """Build the prompt for the Phase 1 detailed-draft writer.

    Section schema must match what extract_judgment expects (lowercased
    + underscored markdown headings). Numerics live at the top of the
    file in their own `##` sections.
    """
    name = venue_spec.name
    overall = venue_spec.overall_dim
    verdict_options = " | ".join(
        sorted({v for v in overall.meanings.values() if v}, key=str)
    )
    sub_dim_lines = []
    for dim_name, dim in venue_spec.sub_dimensions.items():
        labels = ", ".join(
            f"{int(s) if float(s).is_integer() else s}={lbl}"
            for s, lbl in sorted(dim.meanings.items())
        )
        sub_dim_lines.append(
            f"  - `{dim_name}` (scale {dim.scale[0]:g}-{dim.scale[1]:g}): "
            f"{dim.description} | scale labels: {labels}"
        )
    sub_dim_block = "\n".join(sub_dim_lines) if sub_dim_lines else (
        "  (this venue has no sub-dimensions; omit `## sub_scores`)"
    )
    sub_score_template = "\n".join(
        f"- {dim_name}: <int>"
        for dim_name in venue_spec.sub_dimensions.keys()
    ) or "(omit this section)"

    if venue_spec.confidence_dim is not None:
        c = venue_spec.confidence_dim
        conf_block = (
            f"<integer in [{c.scale[0]:g}, {c.scale[1]:g}]; labels: "
            + ", ".join(
                f"{int(s) if float(s).is_integer() else s}={lbl}"
                for s, lbl in sorted(c.meanings.items())
            )
            + ">"
        )
    else:
        conf_block = "(this venue does not collect confidence; omit)"

    return f"""You are a senior peer reviewer for {name}. Write a thorough, \
detailed, paper-grounded peer review. NO template constraint. NO concern \
for AI-detection at this stage — a later step will rewrite prose under \
real-human sentence templates and check the AI rate.

Audience: a future you who needs material to trim down. Write MORE, not \
less. Specific. Paper-grounded. Cite table numbers, equation numbers, \
section references, exact percentages from the paper. If the paper \
makes a claim, name the table that supports or fails to support it.

## Required structure

Write to `{output_path}` as a single markdown file with these sections \
at top level, in this exact order, using `##` headers (lowercased / \
underscored field names):

```
# Review for {name}

## score
<integer in [{overall.scale[0]:g}, {overall.scale[1]:g}]>

## verdict
<one of: {verdict_options}>

## sub_scores
{sub_score_template}

## confidence
{conf_block}

## best_paper_candidate
<Yes | No>

## summary
<What the paper does, the technical core, the experimental setup, \
the headline numbers.>

## strengths

(Flat list. NO category subsections. AT MOST 6 bullets, ordered by \
importance. Real reviews have 4-6 strengths, not 20. If you cannot \
write 4 substantive strengths, write 3. Padding hurts the review.)

Each bullet MUST be substantive — say WHAT specifically is good and \
WHY, not just a label.

Substantive vs vacuous (use this gut check):
- Vacuous: "the motivation is good", "the experiments are solid", \
"the writing is clear", "the topic is important". A reader cannot \
tell from the bullet what the paper actually did.
- Substantive: "the paper targets unsupervised multimodal intent \
discovery, which matters because existing taxonomies miss the long \
tail of conversational intents in real dialogue data" — names the \
problem AND why it matters. "the experiments compare against six \
clustering baselines including SCCL, CC, USNID and SPILL across three \
multimodal dialogue datasets, which makes the comparison hard to \
dismiss" — names what was done AND why it counts.

You do not have to cite Eq./Table numbers for every bullet, but the \
bullet must contain enough specific content (problem name, component \
name, dataset name, baseline name, the specific design choice, the \
specific number when it matters) that a reader can tell which paper \
this review is for. A bullet that could be pasted into a review of \
any other paper in the venue is not a strength.

Near-duplicates of another bullet collapse into one.

- <bullet>
- <...>

## weaknesses

(Flat list. NO category subsections. AT MOST 8 bullets, ordered by \
importance — strongest objection first. If a bullet would not change \
your verdict even if fully addressed, it is not worth listing.)

Each bullet MUST be substantive — name the specific problem AND its \
concrete consequence.

Substantive vs vacuous:
- Vacuous: "more experiments would help", "the analysis is limited", \
"writing could be improved", "more discussion needed". A reader \
cannot tell which experiment, what analysis, which writing.
- Substantive: "the gain over UMC is small (around 1-2 points on \
average) and the paper reports no standard deviation or significance \
test, so the improvement may not be reliable" — names what is small, \
what evidence is missing, why it matters. "no comparison against a \
text-only LLM-naming baseline that would isolate the contribution of \
the multimodal concept generation" — names the missing baseline AND \
why its absence matters for the claim.

You do not have to cite Eq./Table numbers for every bullet, but the \
bullet must (a) name what specifically is wrong / missing / \
unsupported, and (b) state the concrete consequence for the paper's \
claim. "X is not done" without "this means claim Y is unsupported" \
is half a weakness.

Near-duplicates of another bullet collapse into one.

- <bullet>
- <...>

## review
<Multi-paragraph prose. Cover, in order, the same dimensions that \
appear under strengths and weaknesses, but as connected analysis \
rather than bullets:
  1. What the paper does well, with specifics — paper grounded.
  2. Aspects of contribution that exist in prior work; situate the \
delta against the closest baselines mentioned in the paper or in prior \
work the paper cites.
  3. Methodology concerns: equation correctness, hyperparameter \
sensitivity, ablation completeness, dataset coverage, statistical \
significance.
  4. Experimental concerns: missing baselines, missing significance \
tests, table cells where the proposed method loses, fairness of \
comparison, efficiency reporting.
  5. Presentation concerns: notation issues, undefined symbols, \
inconsistent metrics across tables, missing prompt details, \
missing code link.
  6. Open questions you would want the authors to answer.
Cite specifics throughout. Do not hedge with "more work needed" — \
say WHAT work and WHY it would change the verdict.>

## fit_justification
<Why does the paper align (or not) with {name} topics of interest. \
Be specific about which sub-tracks fit.>
```

## Venue-specific sub-dimensions

{name} uses these sub-dimensions:

{sub_dim_block}

Use these exact dimension names in `## sub_scores`.

## Style

- Third-person about the paper ("the paper", "the authors"). NEVER "we".
- Specific. If you're tempted to write "the experiments are limited", \
write WHICH experiment is limited and what specifically is missing.
- Honest. The job is to find real issues, not to be polite. The \
downstream humanize step will add appropriate hedges; you write the \
substance.
- Plain markdown. No LaTeX equations, no curly quotes, no em dashes.
- Paper-grounded. Every concrete claim about the paper must trace to \
the paper text below.

## Venue scoring criteria (informational)

{venue_criteria}

## Paper under review

{paper_content}

Write the file at `{output_path}` and stop.
"""


def _review_peer(*, paper_path: str, venue: str,
                 exec_runtime: Runtime, review_runtime: Runtime) -> dict:
    """peer mode — fixed three-step pipeline:
        1. codex writes a long detailed free-form draft
        2. extract_judgment compresses the draft into a judgment dict
        3. generate_review_text rewrites prose under templates,
           numerics from the draft

    No external draft input. The draft is always generated internally.
    Phase 1 and Phase 2 intermediates are persisted alongside the paper
    for inspection (`<stem>_phase1_draft.md` and
    `<stem>_phase2_judgment.json`).
    """
    paper_content = load_paper(paper_path, exec_runtime)
    spec = get_venue_spec(venue)
    venue_criteria = render_criteria_text(spec)

    paper_p = Path(paper_path)
    if paper_p.is_file():
        stem = paper_p.stem
        intermediate_dir = paper_p.parent
    else:
        stem = "review"
        intermediate_dir = paper_p
    phase1_path = intermediate_dir / f"{stem}_phase1_draft.md"
    phase2_path = intermediate_dir / f"{stem}_phase2_judgment.json"

    # Phase 1: detailed draft, no template constraint
    print(f"[peer] phase 1: writing detailed draft", file=sys.stderr)
    detailed_draft = _write_detailed_draft(
        paper_content=paper_content,
        venue_spec=spec,
        venue_criteria=venue_criteria,
    )
    phase1_path.write_text(detailed_draft, encoding="utf-8")
    print(f"[peer]   saved {phase1_path}", file=sys.stderr)

    # Phase 2: extract structured judgment from the draft
    print(f"[peer] phase 2: extracting judgment", file=sys.stderr)
    draft_judgment = extract_judgment(detailed_draft)
    phase2_path.write_text(
        json.dumps(draft_judgment, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[peer]   saved {phase2_path}", file=sys.stderr)

    # Phase 3: regenerate prose under templates; numerics from judgment
    print(f"[peer] phase 3: regenerating prose under templates",
          file=sys.stderr)
    review_json = review_paper(
        paper_content=paper_content,
        venue=spec.name,
        venue_criteria=venue_criteria,
        runtime=review_runtime,
        draft_judgment=draft_judgment,
    )
    return json.loads(review_json)


def _review_revise(*, paper_path: str, venue: str,
                   exec_runtime: Runtime, review_runtime: Runtime,
                   max_rounds: int, auto_fix: bool,
                   num_reviewers: int, difficulty: str,
                   with_grounding: bool, pass_threshold: int) -> dict:
    """Multi-round ARIS-style review-fix loop on the user's own paper."""
    return review_loop(
        paper_dir=paper_path, venue=venue,
        exec_runtime=exec_runtime, review_runtime=review_runtime,
        num_reviewers=num_reviewers, max_rounds=max_rounds,
        pass_threshold=pass_threshold,
        difficulty=difficulty, auto_fix=auto_fix,
        with_grounding=with_grounding,
    )


def main() -> int:
    p = argparse.ArgumentParser(
        prog="research-review",
        description=(
            "Paper review.\n\n"
            "Common usage:\n"
            "  research-review paper.pdf --venue NeurIPS\n"
            "  research-review paper.pdf --venue NeurIPS --mode revise --auto-fix\n\n"
            "peer mode runs three steps internally: (1) codex writes a "
            "detailed free-form draft, (2) extract_judgment compresses "
            "it, (3) prose is regenerated under real-human sentence "
            "templates with numerics preserved from step 1."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("paper",
                   help="Paper file (.pdf/.docx/.md/.tex/.txt/.html) or dir.")
    p.add_argument("--venue", default="NeurIPS",
                   help="Target venue (default: NeurIPS).")
    p.add_argument("--mode", choices=["peer", "revise"], default="peer",
                   help="peer (default): three-step humanized review of "
                        "someone else's paper. revise: multi-round "
                        "ARIS-style loop on your own paper.")
    p.add_argument("--output", "-o",
                   help="Write review JSON here (default: stdout).")
    p.add_argument("--auto-fix", action="store_true",
                   help="[revise] Auto-fix the paper after each round.")
    p.add_argument("--max-rounds", type=int, default=4,
                   help="[revise] Max review-fix cycles (default 4).")
    # Advanced — hidden from main help, still settable.
    p.add_argument("--provider", default="auto", help=argparse.SUPPRESS)
    p.add_argument("--review-provider", default="openai-codex",
                   help=argparse.SUPPRESS)
    p.add_argument("--review-model", help=argparse.SUPPRESS)
    p.add_argument("--work-dir", help=argparse.SUPPRESS)
    p.add_argument("--num-reviewers", type=int, default=4,
                   help=argparse.SUPPRESS)
    p.add_argument("--difficulty",
                   choices=["medium", "hard", "nightmare"],
                   default="medium", help=argparse.SUPPRESS)
    p.add_argument("--no-grounding", action="store_true",
                   help=argparse.SUPPRESS)
    a = p.parse_args()

    result = review(
        paper=a.paper, venue=a.venue, mode=a.mode,
        provider=a.provider,
        review_provider=a.review_provider, review_model=a.review_model,
        work_dir=a.work_dir,
        max_rounds=a.max_rounds, auto_fix=a.auto_fix,
        num_reviewers=a.num_reviewers, difficulty=a.difficulty,
        with_grounding=not a.no_grounding,
    )

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, "w") as f:
            f.write(out)
        print(f"[research-review] wrote {a.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
