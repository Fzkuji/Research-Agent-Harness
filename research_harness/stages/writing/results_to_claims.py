from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def results_to_claims(results: str, intended_claims: str,
                      runtime: Runtime) -> str:
    """Judge what claims experimental results actually support. Experiments produce
    numbers; this gate decides what those numbers mean.

    For each intended claim, evaluate:
    1. claim_supported: yes | partial | no
    2. what_results_support: what the data actually shows
    3. what_results_dont_support: where the data falls short of the claim
    4. missing_evidence: specific evidence gaps
    5. suggested_claim_revision: if the claim should be strengthened, weakened,
       or reframed
    6. next_experiments_needed: specific experiments to fill gaps (if any)
    7. confidence: high | medium | low

    Routing based on verdict:
    - "no" (claim not supported): record postmortem with what was tested, what
      failed, hypotheses for why. Consider pivoting to next idea.
    - "partial" (partially supported): update working claim to reflect what IS
      supported, design supplementary experiments to fill gaps, re-evaluate after.
      Multiple rounds of "partial" on same claim -> consider narrowing scope.
    - "yes" (claim supported): record confirmed claim. If ablation studies
      incomplete, proceed to ablation planning. If all evidence is in, ready
      for paper writing.

    Rules:
    - Be honest. Do not inflate claims beyond what the data supports.
    - A single positive result on one dataset does not support a general claim.
    - If confidence is low, treat the judgment as inconclusive and add experiments
      rather than committing to a claim.

    Output JSON:
    {{"claims": [{{"claim": "...", "supported": "yes|partial|no",
      "what_results_support": "...", "what_results_dont_support": "...",
      "missing_evidence": "...", "suggested_claim_revision": "...",
      "next_experiments_needed": "...", "confidence": "high|medium|low"}}]}}
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Intended claims:\n{intended_claims}\n\n"
            f"Experimental results:\n{results}"
        )},
    ])
