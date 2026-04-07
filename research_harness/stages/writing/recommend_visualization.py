from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def recommend_visualization(data_description: str, runtime: Runtime) -> str:
    """Recommend chart types for experimental data visualization.

    Available types: grouped bar, horizontal bar, stacked bar,
    line with CI, Pareto front, radar, scatter, heatmap, bubble,
    violin, box, ROC/PR, dual-axis, facet grid, inset zoom.

    Consider: data scale (broken axes, log scale), color-blind palettes,
    vector format (PDF/EPS), text size >= body text.

    Output: Recommended chart type + rationale + design specs.
    """
    return runtime.exec(content=[
        {"type": "text", "text": data_description},
    ])
