from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_table_caption(description: str, runtime: Runtime) -> str:
    """Generate an English table caption for a top-tier conference paper.

    Recommended structures: "Comparison of ... on ...",
    "Ablation study on ...", "Results on ... dataset", "Effect of ... on ...".
    Use "show", "compare", "report" — avoid "showcase", "depict".
    Do NOT include "Table X:" prefix.

    Output: English caption text only.
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])
