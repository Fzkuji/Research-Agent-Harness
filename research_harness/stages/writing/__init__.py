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
from research_harness.stages.writing.define_core_contribution import define_core_contribution
from research_harness.stages.writing.outline_paper_structure import outline_paper_structure

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
        # Measured results so the paper reports real numbers, not just the
        # plan: the experiment SUMMARY and machine-readable run records the
        # integrity gate audits against.
        ("experiments/SUMMARY.md", 4000),
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
    # Run records carry the exact key_metrics every claimed number must trace
    # to. Fold them in (bounded) so write_section can cite measured values.
    import glob as _glob
    records = []
    used = 0
    for d in ("experiments", "auto_experiment"):
        for rp in sorted(_glob.glob(_os.path.join(root, d, "**", "run_record.json"),
                                    recursive=True)):
            if used >= 6000:
                break
            try:
                with open(rp, encoding="utf-8") as f:
                    snippet = f.read(1500)
            except (UnicodeDecodeError, IOError):
                continue
            used += len(snippet)
            records.append(f"### {_os.path.relpath(rp, root)}\n{snippet}")
    if records:
        parts.append("## Measured run records (cite exact numbers from here)\n"
                     + "\n\n".join(records))
    return "\n\n".join(parts)


# Section name -> LaTeX command. Abstract uses the abstract environment;
# the rest are \section{...}. The model returns the section BODY only
# (write_section's contract), which we wrap here into a real LaTeX paper.
_LATEX_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{textcomp}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage[numbers]{natbib}
\title{%(title)s}
\author{}
\date{}
\begin{document}
\maketitle
"""


def _clean_title(topic: str) -> str:
    """Derive a real paper title from whatever ``topic`` the caller passed.

    The autonomous loop sometimes dispatches write_paper with the whole task
    description as ``topic`` (a paragraph of instructions), which then lands
    verbatim in ``\\title{}``. Prefer a quoted title inside the topic
    ("...": the convention the task uses), else the first sentence, capped to
    a sane length."""
    import re as _re
    if not topic or not topic.strip():
        return "Research Paper"
    t = topic.strip()
    m = _re.search(r'["“]([^"”]{8,200})["”]', t)
    if m:
        return m.group(1).strip()
    # First sentence / line, capped.
    first = _re.split(r'(?<=[.!?])\s|\n', t)[0].strip()
    return (first[:160].rstrip() + ("…" if len(first) > 160 else "")) or "Research Paper"


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences a model wrapped its LaTeX in.

    Some models (e.g. MiniMax) return ```latex ... ``` around the section
    body. Left in, the literal fences break compilation AND push the real
    \\section header off the start so _strip_own_header can't see it (→
    doubled headers). Strip opening ```lang fences and closing ``` anywhere."""
    import re as _re
    t = text
    # Opening fences: ```latex / ```tex / ``` at line start.
    t = _re.sub(r"(?m)^\s*```[a-zA-Z]*\s*$", "", t)
    # Any stray inline ``` left over.
    t = t.replace("```", "")
    return t.strip()


def _strip_own_header(name: str, body: str) -> str:
    """Drop a section/abstract wrapper the model included in its own body.

    write_section's contract is "body only", but models frequently emit a
    leading ``\\section{...}`` (or the whole ``\\begin{abstract}...\\end{abstract}``
    environment), sometimes wrapped in ```latex fences. The assembler also
    wraps, so without this the paper gets doubled headers / literal fences.
    Strip fences first, then a leading matching wrapper, so wrapping happens
    exactly once."""
    import re as _re
    b = _strip_code_fences(body)
    if name.lower() == "abstract":
        # Drop every abstract-environment delimiter the model included
        # (it sometimes nests them); the assembler re-adds exactly one.
        b = _re.sub(r"\\(begin|end)\{abstract\}", "", b)
        return b.strip()
    # Drop ALL leading \section{...} / \section*{...} lines — models sometimes
    # repeat the header, and one re-wrap by the assembler is enough.
    while True:
        nb = _re.sub(r"^\\section\*?\{[^}]*\}\s*", "", b, count=1)
        if nb == b:
            break
        b = nb
    return b.strip()


def write_paper(
    topic: str = "",
    output_dir: str = "auto_paper",
    runtime: Runtime = None,
) -> dict:
    """Write a COMPLETE LaTeX paper end to end and save it to
    ``<output_dir>/main.tex`` (+ a references.bib stub).

    Orchestrator: runs its own internal loop over the standard paper
    sections (Abstract..Conclusion), calling ``write_section`` for each with
    the gathered project materials (literature synthesis, ideas, experiment
    plan) as context. Each section returns LaTeX body only; this assembles
    them under a standard article preamble into a compilable main.tex. One
    call produces the whole paper — do NOT re-call to "continue". Does its
    own file writing (the host has a filesystem; the per-section model calls
    do not need one).
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
            f"% Already-written {name}:\n{body[:1500]}" for name, body in written
        )
        ctx = base_context + (f"\n\n=== Sections written so far ===\n{prior}" if prior else "")
        # One section failing (e.g. an intermittent provider mid-stream
        # break) must not lose the whole paper. Try twice, then record a
        # visible LaTeX-comment gap and keep going so the remaining sections
        # — and the persisted main.tex — still get written.
        body = ""
        for _attempt in (1, 2):
            try:
                body = str(write_section(section=section, context=ctx, runtime=runtime))
                if body.strip():
                    break
            except Exception as e:  # noqa: BLE001 — provider/stream errors vary
                body = f"% [SECTION GAP: '{section}' failed to generate ({e.__class__.__name__}: {str(e)[:120]})]"
        written.append((section, body))

    # Assemble LaTeX: abstract in its environment, the rest as \section{}.
    # Strip any wrapper the model already put in its body so headers aren't
    # doubled, and derive a clean title from the topic.
    parts = [_LATEX_PREAMBLE % {"title": _clean_title(topic)}]
    for name, body in written:
        body = _strip_own_header(name, body)
        if name.lower() == "abstract":
            parts.append("\\begin{abstract}\n" + body + "\n\\end{abstract}\n")
        else:
            parts.append("\\section{" + name + "}\n" + body + "\n")
    parts.append("\\bibliographystyle{plainnat}\n\\bibliography{references}\n\\end{document}\n")
    paper = "\n".join(parts)

    paper_path = _os.path.join(output_dir, "main.tex")
    with open(paper_path, "w", encoding="utf-8") as f:
        f.write(paper)
    # references.bib stub — write_section cites verified keys (it verifies or
    # rephrases, never leaves markers); the citation step fills entries.
    bib_path = _os.path.join(output_dir, "references.bib")
    if not _os.path.exists(bib_path):
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write("% References — verified entries added by citation step.\n")

    return {
        "done": True,
        "paper_path": paper_path,
        "sections": [n for n, _ in written],
        "chars": len(paper),
        "summary": f"Wrote {len(written)}-section LaTeX paper ({len(paper)} chars) to {paper_path}",
    }


__all__ = ['analyze_results', 'check_logic', 'compile_paper', 'compress_text', 'design_architecture_figure', 'expand_text', 'generate_figure_caption', 'generate_mermaid_diagram', 'generate_paper_figures', 'generate_table_caption', 'humanize_text', 'polish_natural', 'polish_rigorous', 'polish_zh', 'recommend_visualization', 'remove_ai_flavor_zh', 'rewrite_zh', 'translate_en2zh', 'translate_zh2en', 'write_section', 'define_core_contribution', 'outline_paper_structure', 'write_paper', 'gather_context']
