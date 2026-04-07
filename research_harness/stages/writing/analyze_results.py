from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def analyze_results(data: str, runtime: Runtime) -> str:
    """Analyze experimental data and write LaTeX analysis paragraphs.

    You are a senior data scientist with sharp insight into experimental
    results, writing for a top-tier conference.

    Rules:
    - ALL conclusions must be strictly based on the input data.
      NEVER fabricate data, exaggerate improvements, or invent phenomena.
    - Focus on comparisons and trends, not raw number reporting.
    - Analysis pattern for each finding:
      Observation (B beats A) → Reason (B has X, A lacks it) → Conclusion
      (proves importance of X / necessity of introducing Y).
    - Use \\paragraph{Core Conclusion} + analysis text format (Title Case).
    - No bold/italic, no list environments, pure text paragraphs.
    - Escape special chars: %, _, &.

    Output:
    - Part 1 [LaTeX]: Analysis paragraphs.
    - Part 2 [Translation]: Chinese translation for verification.
    """
    return runtime.exec(content=[
        {"type": "text", "text": data},
    ])
