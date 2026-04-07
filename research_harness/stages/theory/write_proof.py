from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_proof(theorem: str, runtime: Runtime) -> str:
    """Write a rigorous mathematical proof for a theorem/lemma.

    Write a mathematically honest proof, not a polished fake.

    Produce exactly one of:
    1. Complete proof of the original claim
    2. Corrected claim + proof (if original is too strong)
    3. Blockage report (if claim is not currently justified)

    Rules:
    - State the exact interpretation of notation/assumptions used.
    - Every step must follow logically. No hand-waving.
    - If a step requires a lemma, state and prove it.
    - Mark where each assumption is used.
    - If the proof requires extra assumptions, state them clearly.

    Status must be one of:
    - PROVABLE AS STATED
    - PROVABLE AFTER WEAKENING / EXTRA ASSUMPTION
    - NOT CURRENTLY JUSTIFIED

    Output: LaTeX proof with status, assumptions, and complete steps.
    """
    return runtime.exec(content=[
        {"type": "text", "text": theorem},
    ])
