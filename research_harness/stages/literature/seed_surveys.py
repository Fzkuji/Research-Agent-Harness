from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def seed_surveys(query: str, k: int, existing_titles: str,
                 papers_dir: str,
                 runtime: Runtime) -> str:
    """Search for survey papers and DOWNLOAD their PDFs for deeper analysis.

    You are a senior researcher bootstrapping a literature review. You must
    actually search the web / arXiv / Semantic Scholar — do NOT fabricate.

    Workflow:
    1. Search for SURVEY / REVIEW papers on `query`.
       - Prefer: recent (<=5 yrs), high-cited, reputable venues.
       - Sources (in order): Semantic Scholar, arXiv (filter by "survey" or
         "review" in title/abstract), Google Scholar as fallback.
       - Target up to `k` NEW surveys. Skip any whose title appears in
         `existing_titles` — already in state.

    2. For EACH new survey, ALWAYS download the PDF:
       - `papers_dir` (absolute path) is the download destination.
       - Create `papers_dir` if it does not exist.
       - Filename: `<arxiv_id>.pdf` (e.g. `2402.13116.pdf`) or a slugified
         DOI if not on arXiv. Never overwrite an existing file of the same
         name — if it exists, reuse it.
       - Verify the file is a real PDF (> 20 KB, starts with "%PDF"). If not,
         retry once after 5 s. If still broken, record `pdf_path: null` and
         move on — don't fabricate the path.
       - Respect rate limits: 1 s between downloads; retry once on HTTP 429.

    3. For each survey, extract:
       - `id` (arXiv id / DOI / S2 id)
       - `title`, `authors` (first 4 + et al.), `year`, `venue`
       - `abstract` (<= 400 chars)
       - `toc`: list of section/subsection titles (read from arXiv HTML
                version `arxiv.org/html/<id>` if available, else from the
                downloaded PDF's TOC/bookmarks or first pages).
       - `key_claims`: 3–6 bullets on how this survey partitions the field,
                        open problems it flags, and the main methodological
                        camps it identifies.
       - `pdf_path`: absolute path to the downloaded PDF (or null on failure).

    4. Return ONE JSON object, nothing else:
    ```json
    {
      "surveys": [
        {
          "id": "arXiv:2310.01234",
          "title": "...",
          "authors": ["A", "B", "et al."],
          "year": 2024,
          "venue": "ACM Comput. Surv.",
          "abstract": "...",
          "toc": ["1 Introduction", "2 Foundations", ...],
          "key_claims": ["...", "..."],
          "pdf_path": "/abs/path/to/papers/2310.01234.pdf"
        }
      ],
      "notes": "what was searched, failed downloads, caveats"
    }
    ```

    Rules:
    - Output ONLY the JSON (no markdown fence, no commentary).
    - If you cannot find any new surveys, return {"surveys": [], "notes": "..."}.
    - Never fabricate a paper or a file path. If pdf download failed, set
      `pdf_path: null` and explain in `notes`.

    Args:
        query:            Search query (direction or topic path).
        k:                Max new surveys to add.
        existing_titles:  Newline-joined titles already in state (skip these).
        papers_dir:       Absolute dir to save PDFs (create if missing).
        runtime:          LLM runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Search query: {query}\n"
            f"Max new surveys: {k}\n"
            f"Download destination (papers_dir): {papers_dir}\n\n"
            f"Surveys already in state (skip these):\n{existing_titles or '(none)'}"
        )},
    ])
