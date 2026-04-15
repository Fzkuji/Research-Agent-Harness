from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def refine_research(direction: str, runtime: Runtime) -> str:
    """Turn a vague research direction into a problem-anchored, elegant,
    frontier-aware, implementation-oriented method plan.

    Four principles dominate this skill:
    1. Do not lose the original problem. Freeze an immutable Problem Anchor
       and reuse it in every round.
    2. The smallest adequate mechanism wins. Prefer the minimal intervention
       that directly fixes the bottleneck.
    3. One paper, one dominant contribution. Prefer one sharp thesis plus
       at most one supporting contribution.
    4. Modern leverage (LLM/VLM/Diffusion/RL/distillation/inference-time scaling)
       is a prior, not a decoration. Use them concretely when they naturally
       fit the bottleneck. Do not bolt them on as buzzwords.

    Phase 0 - Freeze the Problem Anchor:
    - Bottom-line problem: what technical problem must be solved?
    - Must-solve bottleneck: what specific weakness in current methods is unacceptable?
    - Non-goals: what is explicitly NOT the goal?
    - Constraints: compute, data, time, tooling, venue, deployment limits
    - Success condition: what evidence would make the user say "yes, this works"?

    Phase 1 - Build the Initial Proposal:
    1. Scan grounding material: what mechanism do current methods use? Where do they
       fail? Which frontier techniques are actually relevant?
    2. Identify the technical gap operationally: current pipeline failure point,
       why naive fixes are insufficient, smallest adequate intervention,
       frontier-native alternative, core technical claim, required evidence.
    3. Choose the sharpest route: compare Route A (elegant minimal) vs Route B
       (frontier-native). Pick the one more likely to become a strong paper.
    4. Concretize the method: one-sentence thesis, contribution focus, complexity
       budget (frozen/reused/new), system graph, representation design, training
       recipe, inference path, exact role of any frontier primitive, failure handling,
       novelty and elegance argument.

    Output a focused proposal with:
    - Problem Anchor (immutable)
    - Technical gap identified
    - Proposed method (minimal, elegant, concrete enough to implement)
    - System graph: modules, data flow, inputs, outputs
    - Training recipe and inference path
    - Why this is the sharpest route
    - Minimal validation plan (max 3 core experiment blocks)
    - One-sentence thesis
    - Complexity budget: max 2 new trainable components, max 2 paper-level claims
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": direction},
    ])
