from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def search_arxiv(query: str, runtime: Runtime) -> str:
    """Search, download, and summarize academic papers from arXiv.

    You have full access to run commands. Use the arXiv API or the fetch script
    (tools/arxiv_fetch.py) to search.

    Workflow:
    1. Parse arguments: extract query or arXiv ID (YYMM.NNNNN or category/NNNNNNN),
       max results (default 10), paper directory (default papers/), download flag.

    2. Search arXiv via API:
       ```python
       import urllib.request, urllib.parse, xml.etree.ElementTree as ET
       url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({{
           "search_query": query,
           "start": 0, "max_results": 10,
           "sortBy": "relevance", "sortOrder": "descending",
       }})
       ```

    3. For each result, extract:
       - arXiv ID, title, authors, published date
       - Abstract (full text)
       - Categories
       - PDF link: https://arxiv.org/pdf/{{id}}.pdf
       - Key contributions (extracted from abstract)

    4. Present results as a table:
       | # | arXiv ID | Title | Authors | Date | Category |

    5. Download PDFs (when requested):
       - Save to papers/{{arXiv_ID}}.pdf
       - Verify file size > 10 KB (smaller = likely error HTML page)
       - 1-second delay between consecutive downloads to avoid rate limiting
       - Retry once after 5 seconds on HTTP 429
       - Never overwrite existing PDF at same path (skip and report "already exists")

    6. For each paper, provide structured summary:
       - arXiv ID and URL, authors, date, categories
       - Full abstract
       - Key contributions (bullet points)
       - Local PDF path (if downloaded)

    Key rules:
    - Always show arXiv ID prominently (needed for citations)
    - Verify downloaded PDFs: must be > 10 KB; warn and delete if smaller
    - Rate limit: 1 second between downloads; retry on 429

    Output: Structured list of papers found + download status.
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Search query: {query}"},
    ])
