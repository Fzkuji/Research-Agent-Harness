from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def polish_natural(text: str, runtime: Runtime) -> str:
    """Polish for naturalness — remove mechanical/AI writing patterns.

    You are a senior editor focused on making academic text sound like
    it was written by a native English-speaking researcher.

    Rules:
    - Replace overused AI words: leverage→use, delve→investigate,
      tapestry→context, conceptualize→design, unveil→show, etc.
    - Remove mechanical connectors: "First and foremost", "It is worth noting".
    - Reduce dashes (—), use commas, parentheses, or clauses.
    - No bold/italic emphasis in body text.
    - Keep LaTeX commands intact.
    - If text is already natural with no AI signatures, output it unchanged
      and note "[检测通过] — natural, no changes needed."

    Output:
    - Part 1 [LaTeX]: Rewritten code (or original if already good).
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: Changes made, or "[检测通过]".
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
