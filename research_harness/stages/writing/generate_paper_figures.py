from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_paper_figures(data_description: str, figure_plan: str,
                           runtime: Runtime) -> str:
    """Generate publication-quality figures and tables from experiment results.

    You have full access to write and run Python code.

    Scope - what this skill can and cannot do:
    - CAN auto-generate: line plots (training curves), bar charts (method
      comparison), scatter plots, heatmaps, box/violin plots, multi-panel
      subfigure grids, LaTeX comparison tables
    - CANNOT auto-generate (note in output): architecture/pipeline diagrams
      (use draw.io manually), generated image grids (run model separately),
      screenshots/photographs

    In practice, this handles ~60%% of figures (all data plots + tables).
    The remaining ~40%% (hero figure, architecture diagram, qualitative results)
    need manual creation.

    Auto-select figure type based on data pattern:
    - X=time/steps, Y=metric -> Line plot (0.48\\\\textwidth)
    - Methods x 1 metric -> Bar chart (0.48\\\\textwidth)
    - Methods x multiple metrics -> Grouped bar / radar (0.95\\\\textwidth)
    - Two continuous variables -> Scatter plot (0.48\\\\textwidth)
    - Matrix / grid values -> Heatmap (0.48\\\\textwidth)
    - Distribution comparison -> Box/violin plot (0.48\\\\textwidth)
    - Multi-dataset results -> Multi-panel subfigure (0.95\\\\textwidth)
    - Prior work comparison -> LaTeX table

    Style rules (enforced):
    - DPI = 300, format = PDF (vector)
    - Color palette: tab10 or colorblind-safe (Set2)
    - Font: serif family (Times New Roman / DejaVu Serif), size >= 10pt
      (matches paper body text)
    - No grid lines unless essential
    - Legend inside plot or below, never covering data
    - axes.spines.top = False, axes.spines.right = False
    - savefig.bbox = tight, pad_inches = 0.05
    - Save to figures/ directory

    For each figure, create a standalone Python script, then generate
    LaTeX include snippets saved to figures/latex_includes.tex.

    Output: Python code for each figure + LaTeX snippets + file paths.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Data:\n{data_description}\n\n"
            f"Figure plan:\n{figure_plan}"
        )},
    ])
