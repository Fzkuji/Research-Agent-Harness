from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def build_rebuttal_strategy(parsed_reviews: str, paper_summary: str,
                            runtime: Runtime) -> str:
    """Build a response strategy for each reviewer concern.

    For each concern:
    1. Can we address it? (yes with evidence / yes with clarification / no)
    2. What evidence do we have? (existing results, new experiments needed)
    3. Priority: address fatal/major issues first
    4. Shared concerns across reviewers (address once, reference in others)

    Strategy principles:
    - NEVER fabricate results or promise things you can't deliver
    - Acknowledge valid criticisms honestly
    - Point to existing evidence when possible
    - For experiments we can't run: explain constraints, offer alternatives

    Output: Structured strategy document with response plan per concern.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Parsed reviews:\n{parsed_reviews}\n\n"
            f"Paper summary:\n{paper_summary}"
        )},
    ])
