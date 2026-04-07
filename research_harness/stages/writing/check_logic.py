from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def check_logic(text: str, runtime: Runtime) -> str:
    """Final manuscript check — only flag fatal errors.

    You are an experienced CS paper reviewer doing a final pass.

    Check ONLY for showstoppers:
    - Logical contradictions between statements
    - Terminology inconsistency (same concept, different names)
    - Severe grammar errors that affect comprehension
    - Data inconsistency (numbers in text vs tables/figures)

    High tolerance: style preferences and minor wording are NOT in scope.
    If nothing serious found, output: "[检测通过，无实质性问题]"
    Otherwise: brief Chinese bullet points with location and issue.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])
