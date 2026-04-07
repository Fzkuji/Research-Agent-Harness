from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def expand_text(text: str, runtime: Runtime) -> str:
    """Add 5-15 words by deepening logic, adding connectors, upgrading expressions.

    Only add content grounded in the original text's reasoning. NEVER fabricate.
    Add logical transitions, methodology details, or result interpretation.

    Output:
    - Part 1 [LaTeX]: Expanded text.
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: What was added.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
