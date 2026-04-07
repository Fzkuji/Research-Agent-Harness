from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


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
