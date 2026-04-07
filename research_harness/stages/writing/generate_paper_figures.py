from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_paper_figures(data_description: str, figure_plan: str,
                           runtime: Runtime) -> str:
    """Generate publication-quality matplotlib figures from experiment data.

    You have full access to write and run Python code.

    Can auto-generate:
    - Line plots (training curves), bar charts (method comparison)
    - Scatter plots, heatmaps, box/violin plots
    - Multi-panel subfigure grids
    - LaTeX comparison tables

    Cannot auto-generate (note in output):
    - Architecture diagrams (use draw.io manually)
    - Generated image grids (run model separately)
    - Screenshots / photographs

    Style rules:
    - DPI = 300, format = PDF (vector)
    - Color palette: tab10 or colorblind-safe
    - Font size >= paper body text (typically 10pt)
    - No grid lines unless essential
    - Legend inside plot or below, never covering data
    - Save to figures/ directory

    Output: Python code for each figure + file paths.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Data:\n{data_description}\n\n"
            f"Figure plan:\n{figure_plan}"
        )},
    ])
