from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_proof(theorem: str, runtime: Runtime) -> str:
    """Write a mathematically honest proof package, not a polished fake proof.

    Produce exactly one of:
    1. A complete proof of the original claim
    2. A corrected claim plus a proof of the corrected claim
    3. A blockage report explaining why the claim is not currently justified

    Workflow:
    1. Normalize the claim: restate the exact claim, all assumptions separately
       from conclusions, all symbols. Identify hidden assumptions, undefined
       notation, scope ambiguities, and whether the available sketch proves the
       full claim or only a weaker variant.

    2. Feasibility triage: classify the claim as exactly one of:
       - PROVABLE AS STATED
       - PROVABLE AFTER WEAKENING / EXTRA ASSUMPTION
       - NOT CURRENTLY JUSTIFIED
       Check explicitly: does the conclusion follow from the assumptions? Is any
       cited theorem used outside its conditions? Is the claim stronger than what
       the available argument supports? Is there an obvious counterexample?
       If not provable as stated, do NOT fabricate a proof. Do NOT silently
       strengthen assumptions or narrow the theorem's scope.

    3. Build a dependency map: choose a proof strategy (direct, contradiction,
       induction, construction, reduction, coupling, optimization inequality
       chaining). Then list: main claim, required intermediate lemmas, named
       theorems to be cited, which assumptions each nontrivial step depends on,
       boundary cases that must be handled separately.

    4. Write the proof with these mathematical rigor requirements:
       - Never use "clearly", "obviously", "it can be shown", "by standard
         arguments", or "similarly" to hide a gap
       - Define every constant and symbol before use
       - Check quantifier order carefully
       - Handle degenerate and boundary cases explicitly, or state why they
         are excluded
       - If invoking a standard fact, state its name and why its assumptions
         are satisfied here
       - Use $...$ for inline math and $$...$$ for display equations;
         never write math in plain text
       - If the proof uses an equivalent normalization stronger in appearance
         than the original theorem, label it as a proof device and keep the
         original claim separate

    5. Final verification: confirm the theorem statement matches what was shown,
       every assumption used is stated, every nontrivial implication is justified,
       every inequality direction is correct, every cited result is applicable,
       edge cases are handled, and no hidden dependence on an unproved lemma remains.
       If a key step cannot be justified, downgrade the status and write a blockage
       report instead of forcing a proof.

    Status must be one of:
    - PROVABLE AS STATED
    - PROVABLE AFTER WEAKENING / EXTRA ASSUMPTION
    - NOT CURRENTLY JUSTIFIED

    Output: Proof package with exact claim, assumptions, status, proof strategy,
    dependency map, numbered proof steps with justifications, corrections or
    missing assumptions (if needed), and open risks.
    """
    return runtime.exec(content=[
        {"type": "text", "text": theorem},
    ])
