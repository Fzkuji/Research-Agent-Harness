from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def lookup_venue_criteria(venue: str, runtime: Runtime) -> str:
    """You are an expert on academic peer review processes across all major CS/AI conferences and journals.

    Given a venue name (conference or journal), return its EXACT review scoring criteria in a structured format.

    You must provide:
    1. **Overall Assessment / Recommendation**: The exact scale (e.g., 1-5, 1-10, 1-6), with what each score means.
    2. **Sub-dimensions**: All other scored dimensions (e.g., Soundness, Novelty, Presentation, Confidence), with their scales and meanings.
    3. **Acceptance threshold**: What score range typically leads to acceptance at the main conference vs. secondary tracks (e.g., Findings, Workshop).
    4. **Acceptance rate**: Approximate recent acceptance rate if known.

    Important rules:
    - Use your knowledge of the venue's MOST RECENT review form (2024 or 2025 edition preferred).
    - If the venue uses ARR (ACL Rolling Review), describe the ARR review form.
    - If you are NOT confident about a venue's exact scoring system, say so explicitly and provide your best estimate with a caveat.
    - For journals (e.g., TACL, JMLR, TPAMI), describe their review criteria and decision categories (Accept/Minor Revision/Major Revision/Reject).
    - Be precise: "1-5 scale" is different from "1-10 scale". Do not guess.

    Output format (strictly follow this):

    ```
    VENUE: <full venue name>
    YEAR: <most recent year you have info for>

    OVERALL ASSESSMENT:
    Scale: <e.g., 1-5>
    <score>: <meaning>
    <score>: <meaning>
    ...

    SUB-DIMENSIONS:
    <dimension name>:
      Scale: <e.g., 1-4>
      <score>: <meaning>
      ...

    ACCEPTANCE THRESHOLD:
    Main conference: <score range>
    Secondary track: <track name and score range, if applicable>

    ACCEPTANCE RATE: <approximate %>

    CONFIDENCE NOTE: <state your confidence level in this information>
    ```
    

    # Output
    Return your COMPLETE response as text. Do NOT save to a file — the caller handles persistence.
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Venue: {venue}"},
    ])
