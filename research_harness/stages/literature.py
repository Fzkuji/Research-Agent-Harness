"""
literature — literature survey stage.

Searches for related papers, reads abstracts, and generates
categorized survey notes organized by topic.
"""

from __future__ import annotations

import os
from typing import Optional

from agentic.function import agentic_function
from agentic.runtime import Runtime
from research_harness.utils import parse_json


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def survey_topic(topic: str, runtime: Runtime) -> str:
    """Survey the literature for a given research topic.

    You are a senior ML researcher conducting a thorough literature review.
    Search for and organize the most relevant and recent papers.

    For each paper found:
    - Title, authors, venue, year
    - Core contribution (1-2 sentences)
    - Methodology summary
    - Limitations / gaps

    Organize papers into logical categories/subtopics.
    Prioritize recent work (within 2 years) and top venues.
    Use published versions over arXiv when available.
    Do NOT fabricate papers — only cite real, verifiable work.

    Output: A structured markdown survey organized by subtopic.
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Research topic: {topic}"},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def identify_gaps(survey: str, runtime: Runtime) -> str:
    """Identify research gaps from a literature survey.

    Analyze the survey and identify:
    1. What problems remain unsolved or underexplored?
    2. What assumptions in existing work are questionable?
    3. Where do methods fail or underperform?
    4. What combinations of approaches haven't been tried?

    Be specific: don't say "more research needed", say exactly what's missing.

    Output: Numbered list of specific, actionable research gaps.
    """
    return runtime.exec(content=[
        {"type": "text", "text": survey},
    ])


def run_literature(
    topic: str,
    project_dir: str,
    runtime: Runtime,
) -> dict:
    """Run the literature survey stage.

    Args:
        topic:        Research topic/direction.
        project_dir:  Project directory path.
        runtime:      LLM runtime.

    Returns:
        dict with survey text and identified gaps.
    """
    project_dir = os.path.expanduser(project_dir)

    survey = survey_topic(topic=topic, runtime=runtime)
    gaps = identify_gaps(survey=survey, runtime=runtime)

    # Save to project
    rw_dir = os.path.join(project_dir, "related_work")
    os.makedirs(rw_dir, exist_ok=True)

    with open(os.path.join(rw_dir, "survey.md"), "w") as f:
        f.write(f"# Literature Survey: {topic}\n\n{survey}")

    with open(os.path.join(rw_dir, "gaps.md"), "w") as f:
        f.write(f"# Research Gaps\n\n{gaps}")

    return {"survey": survey, "gaps": gaps}


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


@agentic_function(compress=True, summarize={"siblings": -1})
def comprehensive_lit_review(topic: str, subtopics: str,
                             runtime: Runtime) -> str:
    """Write a comprehensive, publication-ready related work section.

    Deeper than survey_topic — this produces a full Related Work section
    suitable for direct inclusion in a paper.

    Structure per subsection (choose progression or parallel style):

    Progression style:
    - Start with foundational concept, list existing works, end with limitations.

    Parallel style:
    - Overview sentence → subtopic 1 works → subtopic 2 works → our novelty.

    Rules:
    - End each subsection discussing limitations vs our method.
    - Use \\citep{} for parenthetical, \\citet{} for textual.
    - Never use citations as sentence subjects.
    - Cite published versions over arXiv when available.
    - Include recent work (within 2 years) for baselines.

    Output: LaTeX related work section with proper citations.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Topic: {topic}\n\n"
            f"Subtopics to cover:\n{subtopics}"
        )},
    ])
