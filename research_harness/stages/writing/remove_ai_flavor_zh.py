from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def remove_ai_flavor_zh(text: str, runtime: Runtime) -> str:
    """Remove AI-generated patterns from Chinese text (去AI味中文).

    Eliminate machine-translated, over-rendered language patterns:
    - Remove meaningless emotional words (毋庸置疑, 颠覆性, 深刻, 至关重要).
    - Break up English-style long attributive structures.
    - Reduce passive voice, replace list formats with logical prose.
    - No Markdown formatting in output.

    Output:
    - Part 1 [Text]: Cleaned text (or original if already natural).
    - Part 2 [Log]: Changes made, or "[检测通过] 原文自然，无AI味。"
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
