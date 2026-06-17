from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def seed_surveys(query: str, k: int, existing_titles: str,
                 papers_dir: str,
                 runtime: Runtime) -> str:
    """Search for survey papers (via web search) and extract their metadata.

    Actually search the web / arXiv / Semantic Scholar with the web_search
    tool — do NOT fabricate results.

    Workflow:
    1. Search for SURVEY / REVIEW papers on `query` using web search.
       - Prefer: recent (<=5 yrs), high-cited, reputable venues.
       - Sources: arXiv (filter by "survey"/"review" in title/abstract),
         Semantic Scholar, Google Scholar.
       - Target up to `k` NEW surveys. Skip any whose title appears in
         `existing_titles` — already in state.

    2. PDF download is OPTIONAL and depends on your tools. If — and ONLY if —
       you have a working filesystem/shell tool, you MAY download each PDF to
       `papers_dir` (filename `<arxiv_id>.pdf`; verify it starts with "%PDF";
       reuse an existing file) and set `pdf_path`. If you do NOT have file
       access (e.g. you only have web_search), that is fine: set
       `pdf_path: null` and move on. NEVER fabricate a path, and NEVER refuse
       the whole task just because you cannot download — the metadata below is
       what matters.

    3. For each survey, extract (from search results / the arXiv abstract page
       / the arXiv HTML version `arxiv.org/html/<id>`):
       - `id` (arXiv id / DOI / S2 id)
       - `title`, `authors` (first 4 + et al.), `year`, `venue`
       - `abstract` (<= 400 chars)
       - `toc`: list of section/subsection titles if visible (else []).
       - `key_claims`: 3–6 bullets on how this survey partitions the field,
                        open problems it flags, and the main methodological
                        camps it identifies.
       - `pdf_path`: absolute path to a downloaded PDF, or null.

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
    - Output ONLY the JSON object (no markdown fence, no prose, no
      preamble like "Found 2 papers..."). The VERY FIRST character of your
      reply must be `{`.
    - Do NOT discuss whether you can write files. PDF download is optional;
      if you can't, just set every `pdf_path` to null and proceed.
    - If you cannot find any new surveys, return {"surveys": [], "notes": "..."}.
    - Never fabricate a paper or a file path.

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
            f"PDF dir: {papers_dir}\n\n"
            f"Surveys already in state (skip these):\n{existing_titles or '(none)'}\n\n"
            "Find real surveys: query the arXiv API "
            "(http://export.arxiv.org/api/query, follow the https redirect) "
            "and/or Semantic Scholar using your shell/file tools — actually "
            "run code, don't just describe. (codex may also use web_search.) "
            "Reply with ONLY the JSON object specified in your instructions — "
            "first character `{`, no prose, no preamble, no caveats."
        )},
    ], web_search=True)
