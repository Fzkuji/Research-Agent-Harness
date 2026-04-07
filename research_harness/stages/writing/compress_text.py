from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def compress_text(text: str, runtime: Runtime) -> str:
    """Reduce word count by 5-15 words through sentence optimization.

    Preserve ALL information, technical details, and experimental parameters.
    Use clause compression, passive-to-active conversion, redundancy removal.

    Output:
    - Part 1 [LaTeX]: Compressed text.
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: What was compressed.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
