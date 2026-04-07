from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def derive_formula(notes: str, runtime: Runtime) -> str:
    """Structure and derive research formulas from scattered notes.

    Build an honest derivation package, not a fake polished story.

    For each derivation:
    1. State assumptions explicitly
    2. Define notation precisely
    3. Show every step (no "it is easy to see that...")
    4. Mark approximations clearly (≈ vs =)
    5. Note where assumptions are used

    Status must be one of:
    - COHERENT AS STATED
    - COHERENT AFTER REFRAMING / EXTRA ASSUMPTION
    - NOT YET COHERENT (with blocker explanation)

    Output: LaTeX derivation with assumptions, steps, and status.
    """
    return runtime.exec(content=[
        {"type": "text", "text": notes},
    ])
