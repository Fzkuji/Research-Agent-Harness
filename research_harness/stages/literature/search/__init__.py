"""Search backends used by `search_papers_for_topic`.

Each backend is an `@agentic_function` that returns a JSON list of
candidate papers from one source (arXiv, Semantic Scholar). The
orchestrator never picks these directly — the topic-search leaf does.
"""
from research_harness.stages.literature.search.arxiv import search_arxiv
from research_harness.stages.literature.search.semantic_scholar import (
    search_semantic_scholar,
)

__all__ = ["search_arxiv", "search_semantic_scholar"]
