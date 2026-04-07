from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def draft_rebuttal(strategy: str, venue: str, char_limit: int,
                   runtime: Runtime) -> str:
    """Draft a venue-compliant rebuttal response.

    Rules:
    - Stay within character limit (count carefully).
    - Address ALL concerns — reviewers check if you ignored anything.
    - Lead with strongest responses to most damaging concerns.
    - Be respectful but confident. Don't grovel.
    - Every claim in the rebuttal must be backed by evidence from the paper
      or user-confirmed new results. NO fabrication.
    - Use "We clarify that..." / "We have added..." / "We respectfully note..."
    - If a concern is valid and cannot be fully addressed: acknowledge it,
      explain what you've done to mitigate, and describe future plans.

    Safety checks before output:
    1. Every claim maps to paper/review/user-confirmed result?
    2. No overpromises?
    3. Every reviewer concern addressed?

    Output: Plain text rebuttal ready to paste into submission system.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n"
            f"Character limit: {char_limit}\n\n"
            f"Response strategy:\n{strategy}"
        )},
    ])
