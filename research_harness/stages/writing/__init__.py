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
from research_harness.stages.writing.results_to_claims import results_to_claims
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
        with open(outline_path, "r") as f:
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
                    with open(fpath, "r") as f:
                        parts.append(f"## Notes: {fname}\n{f.read()[:2000]}")
                except (UnicodeDecodeError, IOError):
                    pass

    return "\n\n".join(parts) if parts else "No context available yet."


__all__ = ['analyze_results', 'check_logic', 'compile_paper', 'compress_text', 'design_architecture_figure', 'expand_text', 'generate_figure_caption', 'generate_mermaid_diagram', 'generate_paper_figures', 'generate_table_caption', 'humanize_text', 'polish_natural', 'polish_rigorous', 'polish_zh', 'recommend_visualization', 'remove_ai_flavor_zh', 'results_to_claims', 'rewrite_zh', 'translate_en2zh', 'translate_zh2en', 'write_section', 'gather_context']
