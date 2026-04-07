from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def design_architecture_figure(method_description: str, runtime: Runtime) -> str:
    """Design a paper architecture/framework diagram.

    Style: flat vector, clean lines (DeepMind/OpenAI style).
    Professional pastels on white background. English labels, minimal text.

    Output: diagram layout description, component list, connections,
    color scheme, and draw.io / TikZ reproduction notes.
    """
    return runtime.exec(content=[
        {"type": "text", "text": method_description},
    ])
