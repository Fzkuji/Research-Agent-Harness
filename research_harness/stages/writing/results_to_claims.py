from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def results_to_claims(results: str, intended_claims: str,
                      runtime: Runtime) -> str:
    """Judge what claims experimental results actually support.

    For each claim: supported? (yes/partial/no), evidence strength,
    gaps, suggested rewording if too strong. Be brutally honest.

    Output JSON: {"claims": [{"claim": "...", "supported": "yes/partial/no",
    "evidence": "...", "gaps": "...", "suggested_wording": "..."}]}
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Intended claims:\n{intended_claims}\n\n"
            f"Experimental results:\n{results}"
        )},
    ])
