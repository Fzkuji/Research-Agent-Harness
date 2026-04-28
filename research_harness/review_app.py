"""Single-shot reviewer app — load paper, generate one humanized review.

Library use:
    from research_harness.review_app import generate_review
    review = generate_review("paper.pdf", venue="ACM Multimedia")

CLI use:
    python -m research_harness.review_app paper.pdf --venue "ACM Multimedia"
    python -m research_harness.review_app paper.pdf --venue NeurIPS -o review.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from openprogram.agentic_programming.runtime import Runtime
from openprogram.providers import create_runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, render_criteria_text,
)
from research_harness.stages.review.load_paper import load_paper
from research_harness.stages.review.review_paper import review_paper
from research_harness.stages.review._extract_judgment import extract_judgment


def generate_review(paper_path: str, *, venue: str = "NeurIPS",
                    runtime: Optional[Runtime] = None,
                    work_dir: Optional[str] = None,
                    provider: str = "auto",
                    model: Optional[str] = None,
                    draft_path: Optional[str] = None) -> dict:
    """Produce one humanized review for a paper.

    Args:
        paper_path: File or directory containing the paper. Accepts
                    .pdf, .docx, .md, .tex, .txt, .html, or a directory
                    of .tex files (legacy LaTeX layout).
        venue:      Target venue (case-insensitive, aliases handled by
                    get_venue_spec).
        runtime:    Optional pre-built Runtime. If None, a new one is
                    created from `provider`/`model`.
        work_dir:   Runtime work directory (codex --cd target). Default:
                    parent of paper_path.
        provider:   Provider name when runtime is None (default: 'auto').
        model:      Model id when runtime is None (default: provider's
                    default).

    Returns:
        Review as a dict (parsed JSON). Field names depend on the venue's
        review form — e.g. ACM MM has `review` + `fit_justification`,
        COLM uses `reasons_to_accept` instead of `strengths`. Numeric
        fields (`score`, `verdict`, `sub_scores`, `confidence`) are
        always present.
    """
    paper_path = os.path.abspath(os.path.expanduser(paper_path))
    if not os.path.exists(paper_path):
        raise FileNotFoundError(paper_path)

    if work_dir is None:
        work_dir = (os.path.dirname(paper_path) if os.path.isfile(paper_path)
                    else paper_path)
    work_dir = os.path.abspath(os.path.expanduser(work_dir))
    os.makedirs(work_dir, exist_ok=True)

    if runtime is None:
        runtime = create_runtime(provider=provider, model=model)
        runtime.set_workdir(work_dir)

    paper_content = load_paper(paper_path, runtime)
    spec = get_venue_spec(venue)
    venue_criteria = render_criteria_text(spec)

    draft_judgment = None
    if draft_path:
        draft_path = os.path.abspath(os.path.expanduser(draft_path))
        if not os.path.exists(draft_path):
            raise FileNotFoundError(draft_path)
        draft_text = open(draft_path).read()
        draft_judgment = extract_judgment(draft_text)

    review_json = review_paper(
        paper_content=paper_content,
        venue=spec.name,
        venue_criteria=venue_criteria,
        runtime=runtime,
        draft_judgment=draft_judgment,
    )
    return json.loads(review_json)


def main() -> int:
    p = argparse.ArgumentParser(
        prog="review_app",
        description="Generate one humanized review for a paper "
                    "(stage 1: codex CLI free-form prose under "
                    "real-human sentence templates; stage 2: structured "
                    "score / verdict via tool-use).",
    )
    p.add_argument("paper", help="Paper file or directory "
                                 "(.pdf/.docx/.md/.tex/.txt/.html or dir).")
    p.add_argument("--venue", default="NeurIPS",
                   help="Target venue (default: NeurIPS).")
    p.add_argument("--output", "-o",
                   help="Write review JSON to this path "
                        "(default: stdout).")
    p.add_argument("--provider", default="auto",
                   help="LLM provider (default: auto).")
    p.add_argument("--model", default=None,
                   help="Model id (default: provider default).")
    p.add_argument("--work-dir", default=None,
                   help="Runtime work directory (default: paper's dir).")
    p.add_argument("--draft", default=None,
                   help="Path to an existing review draft to humanize. "
                        "Triggers humanize mode: draft's score / verdict / "
                        "sub_scores / confidence / per-section bullets are "
                        "extracted as structured judgment, then re-used "
                        "to guide a from-scratch prose generation. The "
                        "draft's prose itself never enters the LLM "
                        "context, so the output prose carries no LLM "
                        "signature from the draft.")
    a = p.parse_args()

    review = generate_review(
        paper_path=a.paper,
        venue=a.venue,
        provider=a.provider,
        model=a.model,
        work_dir=a.work_dir,
        draft_path=a.draft,
    )

    out = json.dumps(review, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, "w") as f:
            f.write(out)
        print(f"[review_app] wrote {a.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
