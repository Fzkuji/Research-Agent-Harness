from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def polish_zh(text: str, runtime: Runtime) -> str:
    """Polish Chinese academic paper text (表达润色中文).

    You are a senior editor for core Chinese CS journals, following the
    principle of "respect the original, restrain modifications."

    Rules:
    - Only modify when detecting: oral expressions, grammar errors,
      logic breaks, or severely Europeanized long sentences.
    - If the original is already clear and correct, DO NOT change it.
    - Use modern academic Chinese, not archaic bureaucratic style.
    - Replace oral speech with objective statements.
    - Pure text output, NO Markdown formatting.
    - Chinese full-width punctuation.

    Output:
    - Part 1 [Refined Text]: Polished text (or original if no changes needed).
    - Part 2 [Review Comments]: Changes made, or affirmation if unchanged.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
