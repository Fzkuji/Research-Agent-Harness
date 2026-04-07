from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def search_arxiv(query: str, runtime: Runtime) -> str:
    """Search arXiv for papers matching the query.

    You have full access to run commands. Use the arXiv API to search:

    ```python
    import urllib.request, urllib.parse
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({
        "search_query": "all:<query>",
        "max_results": 10,
        "sortBy": "relevance",
    })
    ```

    For each result, extract:
    - Title, authors, arXiv ID, published date
    - Abstract (first 2 sentences)
    - Categories
    - PDF link

    Optionally download PDFs to papers/ directory if requested.

    Output: Structured list of papers found.
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Search query: {query}"},
    ])
