from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def check_submission(paper_content: str, venue: str, runtime: Runtime) -> str:
    """Pre-submission checklist for academic paper.

    Run final checks before paper submission. Check for ALL of the
    following:

    1. Anonymity:
       - No author names, affiliations, or institutional info
       - No "our previous work..." or self-identifying references
       - No personal info in code links or supplementary
       - Check for hidden metadata

    2. Format:
       - Page limit compliance (body, references, appendix separately)
       - Correct venue template and meta information
       - Title and abstract match submission system

    3. References:
       - All from Google Scholar (not DBLP or other sources)
       - Published versions preferred over arXiv
       - No duplicate citations (arXiv + published of same paper)
       - Recent baselines (within 2 years)
       - No AI-generated fake references

    4. Figures & Tables:
       - All referenced in text ("Figure X", "Table Y")
       - Order matches first mention in text
       - Vector format (PDF/EPS) for figures, not PNG/JPG
       - Text in figures >= body text size
       - Booktabs style for tables

    5. Writing:
       - Last line of each paragraph has >= 4 words
       - Consistent terminology throughout
       - No absolute claims without hedging (use "generally", "often")
       - Proper label prefixes (sec:, fig:, tab:, equ:, alg:)

    6. Code submission:
       - Anonymous repository link
       - No personal info or hardcoded paths in code
       - No hidden files (.git) with author info

    Output: Checklist with [PASS]/[FAIL]/[WARN] for each item.
    Flag critical issues that could cause desk rejection.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Target venue: {venue}\n\n"
            f"Paper content:\n{paper_content}"
        )},
    ])
