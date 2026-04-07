from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def translate_en2zh(text: str, runtime: Runtime) -> str:
    """Translate English LaTeX to readable Chinese text.

    You are a senior CS academic translator helping researchers
    quickly understand complex English paper paragraphs.

    Rules:
    - Remove all \\cite{}, \\ref{}, \\label{} commands.
    - Extract text from \\textbf{}, \\emph{} — ignore formatting.
    - Convert LaTeX math to natural language (e.g. $\\alpha$ → alpha).
    - Strict literal translation, preserve original sentence structure.
    - Do NOT polish or reorganize — reflect the original faithfully.

    Output: Pure Chinese text only, no LaTeX code.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
