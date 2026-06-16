"""Stage: writing"""

from research_harness.stages.writing.analyze_results import analyze_results
from research_harness.stages.writing.check_logic import check_logic
from research_harness.stages.writing.compile_paper import compile_paper
from research_harness.stages.writing.compress_text import compress_text
from research_harness.stages.writing.design_architecture_figure import design_architecture_figure
from research_harness.stages.writing.expand_text import expand_text
from research_harness.stages.writing.generate_figure_caption import generate_figure_caption
from research_harness.stages.writing.generate_mermaid_diagram import generate_mermaid_diagram
from research_harness.stages.writing.generate_paper_figures import generate_paper_figures
from research_harness.stages.writing.generate_table_caption import generate_table_caption
from research_harness.stages.writing.humanize_text import humanize_text
from research_harness.stages.writing.polish_natural import polish_natural
from research_harness.stages.writing.polish_rigorous import polish_rigorous
from research_harness.stages.writing.polish_zh import polish_zh
from research_harness.stages.writing.recommend_visualization import recommend_visualization
from research_harness.stages.writing.remove_ai_flavor_zh import remove_ai_flavor_zh
from research_harness.stages.writing.rewrite_zh import rewrite_zh
from research_harness.stages.writing.translate_en2zh import translate_en2zh
from research_harness.stages.writing.translate_zh2en import translate_zh2en
from research_harness.stages.writing.write_section import write_section

import os
from typing import Optional
from openprogram.agentic_programming.runtime import Runtime


def gather_context(project_dir: str, section: str) -> str:
    """Gather context from project directory for writing a section."""
    project_dir = os.path.expanduser(project_dir)
    parts = []

    # Outline
    outline_path = os.path.join(project_dir, "outline", "outline.md")
    if os.path.exists(outline_path):
        with open(outline_path, "r", encoding="utf-8") as f:
            parts.append(f"## Outline\n{f.read()[:3000]}")

    # Section-specific notes
    section_dir = os.path.join(project_dir, section)
    if os.path.isdir(section_dir):
        for fname in sorted(os.listdir(section_dir)):
            if fname == "README.md":
                continue
            fpath = os.path.join(section_dir, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        parts.append(f"## Notes: {fname}\n{f.read()[:2000]}")
                except (UnicodeDecodeError, IOError):
                    pass

    return "\n\n".join(parts) if parts else "No context available yet."


# Standard paper structure written by write_paper, in order.
_PAPER_SECTIONS = [
    "Abstract",
    "Introduction",
    "Related Work",
    "Method",
    "Experiments",
    "Results",
    "Discussion",
    "Limitations",
    "Conclusion",
]


def _gather_project_materials(output_dir: str) -> str:
    """Collect everything earlier stages wrote (literature synthesis, ideas,
    experiment plan) into one context blob for paper writing. Best-effort:
    on a runtime/host with no such files, returns whatever is present (maybe
    nothing) and the caller still passes the task context through."""
    import os as _os
    root = _os.path.dirname(output_dir.rstrip("/")) or output_dir
    picks = [
        ("literature review/synthesis/review.md", 6000),
        ("ideas/ranking.md", 4000),
        ("ideas/ideas.md", 3000),
        ("experiments/plan.md", 6000),
    ]
    parts = []
    for rel, cap in picks:
        p = _os.path.join(root, rel)
        if _os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    parts.append(f"## {rel}\n{f.read()[:cap]}")
            except (UnicodeDecodeError, IOError):
                pass
    return "\n\n".join(parts)


def write_paper(
    topic: str = "",
    output_dir: str = "auto_paper",
    runtime: Runtime = None,
) -> dict:
    """Write a COMPLETE paper end to end and save it to ``<output_dir>/PAPER.md``.

    Orchestrator: runs its own internal loop over the standard paper
    sections (Abstract..Conclusion), calling ``write_section`` for each with
    the gathered project materials (literature synthesis, ideas, experiment
    plan) as context, then concatenates them into one markdown paper and
    persists it. One call produces the whole paper — do NOT re-call to
    "continue". Does its own file writing (the caller's host has a
    filesystem; the per-section model calls do not need one).
    """
    import os as _os
    if runtime is None:
        raise ValueError("write_paper() requires a runtime argument")
    output_dir = _os.path.expanduser(output_dir)
    _os.makedirs(output_dir, exist_ok=True)

    materials = _gather_project_materials(output_dir)
    base_context = (
        f"Paper topic: {topic}\n\n"
        f"Project materials gathered from earlier stages:\n"
        f"{materials or '(none on disk — rely on the topic and your reasoning)'}"
    )

    written: list[tuple[str, str]] = []
    for section in _PAPER_SECTIONS:
        prior = "\n\n".join(
            f"### Already-written {name}\n{body[:1500]}" for name, body in written
        )
        ctx = base_context + (f"\n\n=== Sections written so far ===\n{prior}" if prior else "")
        # One section failing (e.g. an intermittent provider mid-stream
        # break) must not lose the whole paper. Try once, retry once, then
        # record a visible gap and keep going so the remaining sections —
        # and the persisted PAPER.md — still get written.
        body = ""
        for _attempt in (1, 2):
            try:
                body = str(write_section(section=section, context=ctx, runtime=runtime))
                if body.strip():
                    break
            except Exception as e:  # noqa: BLE001 — provider/stream errors vary
                body = f"[SECTION GAP: '{section}' failed to generate ({e.__class__.__name__}: {str(e)[:120]})]"
        written.append((section, body))

    paper = "\n\n".join(f"# {name}\n\n{body}" for name, body in written)
    paper_path = _os.path.join(output_dir, "PAPER.md")
    with open(paper_path, "w", encoding="utf-8") as f:
        f.write(paper)

    return {
        "done": True,
        "paper_path": paper_path,
        "sections": [n for n, _ in written],
        "chars": len(paper),
        "summary": f"Wrote {len(written)}-section paper ({len(paper)} chars) to {paper_path}",
    }


__all__ = ['analyze_results', 'check_logic', 'compile_paper', 'compress_text', 'design_architecture_figure', 'expand_text', 'generate_figure_caption', 'generate_mermaid_diagram', 'generate_paper_figures', 'generate_table_caption', 'humanize_text', 'polish_natural', 'polish_rigorous', 'polish_zh', 'recommend_visualization', 'remove_ai_flavor_zh', 'rewrite_zh', 'translate_en2zh', 'translate_zh2en', 'write_section', 'write_paper', 'gather_context']
