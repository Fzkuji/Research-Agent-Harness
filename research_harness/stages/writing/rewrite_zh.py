from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def rewrite_zh(text: str, runtime: Runtime) -> str:
    """Rewrite fragmented Chinese draft into polished academic Chinese (中转中).

    You are a senior editor for top Chinese CS journals (计算机学报, 软件学报).

    Rules:
    - Restructure logic: identify the main thread, reconnect loose sentences.
    - One paragraph = one core idea. No multi-topic paragraphs.
    - Convert oral speech to formal academic writing
      (e.g. "我们觉得" → "实验结果表明", "不管A还是B" → "无论A抑或B").
    - Convert lists to continuous paragraphs.
    - Pure text output, NO Markdown formatting (no bold, italic, headers).
    - Use Chinese full-width punctuation (，。；：""）.
    - Preserve English technical terms (Transformer, CNN, Few-shot).

    Output:
    - Part 1 [Refined Text]: Rewritten Chinese paragraph.
    - Part 2 [Logic flow]: Brief explanation of restructuring logic.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
