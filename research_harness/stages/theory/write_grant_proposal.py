from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_grant_proposal(direction: str, grant_type: str,
                         runtime: Runtime) -> str:
    """Draft a structured grant proposal from research ideas.

    Supports: NSFC (面上/青年/优青/杰青/海外优青/重点), NSF (US),
    KAKENHI (Japan), ERC (EU), DFG (Germany), ARC (Australia), generic.

    Structure:
    1. Research significance and background
    2. Research objectives and key questions
    3. Research plan and methodology
    4. Expected outcomes and impact
    5. Feasibility: team, resources, timeline
    6. Budget justification (if applicable)

    Rules:
    - Ground every claim in literature or preliminary results.
    - Be specific about methodology — reviewers hate vague plans.
    - One clear thesis, not a laundry list of ideas.
    - Match tone/structure to the specific grant agency's expectations.
    - Include preliminary results if available to demonstrate feasibility.

    Output: Structured grant proposal document.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research direction:\n{direction}\n\n"
            f"Grant type: {grant_type}"
        )},
    ])
