from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def derive_formula(notes: str, runtime: Runtime) -> str:
    """Build an honest derivation package from scattered notes, not a fake polished
    theorem story.

    Produce exactly one of:
    1. A coherent derivation package for the original target
    2. A reframed derivation package with corrected object / assumptions / scope
    3. A blocker report explaining why the current notes cannot yet support a
       coherent derivation

    Workflow:
    1. Freeze the target: state explicitly what is being explained, derived, or
       supported, and whether the goal is identity/algebra, proposition,
       approximation, or interpretation. Do not start symbolic manipulation
       before this is fixed.

    2. Choose the invariant object: identify the single quantity or conceptual
       object that should organize the derivation (objective/loss, total cost/energy,
       conserved quantity, expected metric). Do not let a convenient proxy silently
       replace the actual conceptual object.

    3. Normalize assumptions and notation: restate all assumptions, symbols, regime
       boundaries. Identify hidden assumptions, undefined notation, scope ambiguities,
       and whether the formula chain already mixes exact steps with approximations.

    4. Classify each derivation step as one of:
       - identity: exact algebraic reformulation
       - proposition: a claim requiring conditions
       - approximation: model simplification or surrogate
       - interpretation: prose-level meaning of a formula
       Never merge these categories without signaling the transition.

    5. Build a derivation map: target formula, required intermediate identities or
       lemmas, which assumptions each nontrivial step uses, where approximations enter,
       where special-case and general-case regimes diverge.

    6. Write the derivation with these rules:
       - Do not hide gaps with "clearly", "obviously", or "similarly"
       - Define every symbol before use
       - Mark approximations explicitly
       - Separate derivation body from remarks
       - If the true object is dynamic but a simpler slice is analyzed, say so explicitly

    7. Final verification: confirm the target is explicit, the invariant object is
       stable, every assumption used is stated, each step is correctly labeled,
       the derivation does not silently switch objects, and boundaries/non-claims
       are stated.

    Status must be one of:
    - COHERENT AS STATED
    - COHERENT AFTER REFRAMING / EXTRA ASSUMPTION
    - NOT YET COHERENT (with blocker explanation)

    Output: Derivation package with target, status, invariant object, assumptions,
    notation, derivation strategy, derivation map, main steps, remarks, and
    boundaries/non-claims.
    """
    return runtime.exec(content=[
        {"type": "text", "text": notes},
    ])
