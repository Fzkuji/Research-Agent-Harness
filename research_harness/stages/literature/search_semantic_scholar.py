from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def search_semantic_scholar(query: str, runtime: Runtime) -> str:
    """Search Semantic Scholar API for published venue papers.

    Complements arXiv (preprints) with citation counts, venue metadata,
    and TLDR summaries from published conferences/journals (IEEE, ACM, etc.).

    Use the Semantic Scholar API:
    ```
    GET https://api.semanticscholar.org/graph/v1/paper/search
        ?query=<query>&limit=10
        &fields=title,authors,year,venue,citationCount,tldr,externalIds
    ```

    For each result, extract:
    - Title, authors, venue, year
    - Citation count
    - TLDR summary
    - Whether it's also on arXiv (check externalIds.ArXiv)

    Prioritize: high citation count, top venues, recent work.

    Output: Structured list of papers with citation counts and venues.
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Search query: {query}"},
    ])
