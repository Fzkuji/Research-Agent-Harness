from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def fetch_external_review(paper_path: str, provider: str, venue: str,
                          email: str, review_url: str,
                          runtime: Runtime) -> str:
    """Fetch a review from an external review service and return it in the
    same format as a local LLM reviewer (so it can drop into AC meta-review's
    individual_reviews list).

    # Inputs
    - paper_path:  Absolute path to the paper PDF / Markdown / etc. The user
                   will need to upload this file to the external service.
    - provider:    "paperreview_ai" (Stanford Agentic Reviewer at
                   paperreview.ai). Other providers may be added later.
    - venue:       Target venue (used to fill the venue dropdown on the
                   external site, e.g. "NeurIPS", "ICLR", "ACL").
    - email:       Email to use for notifications. Defaults are stored in
                   user memory; if empty, ask the user.
    - review_url:  If the user has already submitted to the external service
                   and has a result URL (e.g. "https://paperreview.ai/review?id=xxx"),
                   pass it here. If empty/None, this function emits a manual
                   instruction block and the caller should pause for the user.

    # Behavior

    ## Branch A: review_url is empty
    Emit a clear, copy-pasteable instruction block telling the user exactly
    how to obtain the URL. Do NOT attempt to wait or poll. Return a JSON
    block with status="needs_manual_step" and the instructions.

    For provider == "paperreview_ai", the instructions must include:
      1. Open https://paperreview.ai/
      2. Drag <paper_path> into the upload field. (Note: paperreview.ai limits
         to 10MB / first 15 pages — flag if the PDF exceeds this.)
      3. Email: <email>
      4. Target venue: <venue>   (or "Other" + venue name if not in dropdown)
      5. Click submit. Wait for the email notification (typically 5-30 minutes).
      6. Open the link in the email. Copy the URL of the resulting review page.
      7. Paste that URL back to me to continue.

    Output format for Branch A (strict JSON, no extra prose):
    ```json
    {
      "status": "needs_manual_step",
      "provider": "paperreview_ai",
      "instructions": "<the numbered steps above as plain text>",
      "expected_input_format": "URL like https://paperreview.ai/review?id=xxx"
    }
    ```

    ## Branch B: review_url is provided
    1. Sanity-check the URL: must start with https://paperreview.ai/ for
       provider="paperreview_ai". If domain doesn't match, return an error JSON.
    2. Use shell tools to fetch the review page HTML:
       ```bash
       curl -sL -A "Mozilla/5.0 (research-harness)" "$URL" -o /tmp/review.html
       ```
    3. Parse the HTML to extract:
       - The 7-dimension scores (Originality, Importance, Claims supported,
         Soundness of experiments, Clarity, Community value, Contextualization)
         if present (they may be ICLR-only).
       - The composite 1-10 score if present.
       - The full review text (Summary / Strengths / Weaknesses / Questions /
         Suggestions sections).
       - Any cited prior work (paperreview.ai grounds in arXiv).

       The HTML structure may evolve. Robust strategy: after curl, run
       `python3 -c "from html.parser import HTMLParser; ..."` or use a
       small inline BeautifulSoup script if available. If extraction fails,
       fall back to dumping the visible text via:
       ```bash
       python3 -c "
       import re, html
       with open('/tmp/review.html') as f: raw = f.read()
       # Strip script/style
       raw = re.sub(r'<(script|style)[^>]*>.*?</\\1>', '', raw, flags=re.DOTALL|re.I)
       text = re.sub(r'<[^>]+>', ' ', raw)
       text = html.unescape(text)
       text = re.sub(r'\\s+', ' ', text)
       print(text)
       "
       ```

    4. Reformat into the same shape our local reviewers produce (so AC
       meta-review can ingest it uniformly):

    Output format for Branch B (Markdown + trailing JSON block):

    ```markdown
    # External Review (paperreview.ai)

    Source: <review_url>
    Fetched: <ISO timestamp>

    ## Summary
    <paperreview.ai's summary>

    ## Strengths
    <bullet list>

    ## Weaknesses
    <bullet list, ranked>

    ## 7-Dimension Scores (if available)
    | Dimension | Score |
    |-----------|-------|
    | Originality | X |
    | Importance | X |
    | Claims supported | X |
    | Soundness of experiments | X |
    | Clarity | X |
    | Community value | X |
    | Contextualization | X |

    ## Final Score
    X / 10  (composite via Stanford's regression on ICLR 2025)

    ## Cited Prior Work
    [paperreview.ai grounded its review in these papers]
    - arXiv:xxxx — Title
    - ...

    ## Suggestions
    <copy verbatim>
    ```

    Then a JSON block matching the local reviewer schema:
    ```json
    {
      "score": <number>,
      "score_scale": "1-10",
      "venue": "<venue>",
      "passed": <bool, true if score >= venue threshold>,
      "weaknesses": ["..."],
      "strengths": ["..."],
      "confidence": null,
      "verdict": "external_paperreview_ai: <one-line summary>",
      "external_provider": "paperreview_ai",
      "external_url": "<review_url>",
      "seven_dim_scores": {"originality": X, "importance": X, ...}
    }
    ```

    # Constraints
    1. Do NOT poll / sleep / loop waiting for the URL — paperreview.ai takes
       5-30 minutes, the caller (review_loop) handles asynchrony by saving
       state and resuming when the user provides the URL.
    2. Do NOT fabricate scores or weaknesses. If HTML parsing produces empty
       fields, leave them empty (null) rather than guessing.
    3. Strip paperreview.ai-specific UI text ("Submit Paper", "Tech Overview"
       nav items, footer disclaimers) — keep only the review content.
    4. If the URL returns 404 / "review not ready yet" / queued status, return
       a JSON with status="not_ready" so the caller can ask the user to wait.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"provider: {provider}\n"
            f"paper_path: {paper_path}\n"
            f"venue: {venue}\n"
            f"email: {email}\n"
            f"review_url: {review_url or '[NONE — emit manual step instructions]'}"
        )},
    ])
