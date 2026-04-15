from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def search_semantic_scholar(query: str, runtime: Runtime) -> str:
    """Search published venue papers (IEEE, ACM, Springer, etc.) via Semantic Scholar
    API. Complements arXiv (preprints) with citation counts, venue metadata, and TLDR.

    This is the published venue counterpart to search_arxiv:
    - search_arxiv: latest preprints, cutting-edge unrefereed work
    - search_semantic_scholar: published journal/conference papers with citation
      counts, venue info, TLDR

    Workflow:
    1. Parse arguments: query or paper ID (DOI, S2 ID, ARXIV:..., CorpusId:...),
       max results (default 10), publication type filter, min citations, year range,
       fields of study, sort order.

    2. Search via Semantic Scholar API:
       Standard search (relevance-ranked):
       GET https://api.semanticscholar.org/graph/v1/paper/search
           ?query={{query}}&limit=10
           &fields=title,authors,year,venue,citationCount,tldr,externalIds,
                   abstract,openAccessPdf,publicationVenue,fieldsOfStudy
           &fieldsOfStudy=Computer Science,Engineering
           &publicationTypes=JournalArticle,Conference

       Bulk search (when sorting by citations or >100 results):
       Use search-bulk endpoint with sort=citationCount:desc

    3. Default filters (applied unless overridden):
       - fieldsOfStudy: Computer Science, Engineering
       - publicationTypes: JournalArticle, Conference

    4. De-duplicate against arXiv: check externalIds.ArXiv for each result.
       If present, note it but do NOT re-fetch via arXiv.

    5. For each result, extract:
       - Title, authors, venue, year, citation count
       - DOI link (canonical for IEEE/ACM papers)
       - TLDR summary (may be null for IEEE papers; fall back to first sentence
         of abstract)
       - Open access PDF URL (may be empty for closed access; provide DOI as fallback)
       - Whether also on arXiv

    6. Present results as table:
       | # | Title | Venue | Year | Citations | Authors | Type |

    Key rules:
    - Citation count is gold: always show citationCount prominently, use it to
      rank/prioritize
    - Venue metadata matters: show venue and publication type (journal vs conference)
    - DOI is the canonical ID for published papers: always show DOI links
    - Rate limiting: S2 API without key is heavily rate-limited (~1 req/s).
      Recommend users set SEMANTIC_SCHOLAR_API_KEY env var.
    - Do NOT duplicate arXiv's job: if paper has ArXiv ID, note but don't re-fetch

    Output: Structured list of papers with citation counts, venues, and DOI links.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Search query: {query}"},
    ])
