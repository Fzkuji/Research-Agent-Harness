"""Stage: literature"""

from research_harness.stages.literature.comprehensive_lit_review import comprehensive_lit_review
from research_harness.stages.literature.identify_gaps import identify_gaps
from research_harness.stages.literature.search_arxiv import search_arxiv
from research_harness.stages.literature.search_semantic_scholar import search_semantic_scholar
from research_harness.stages.literature.survey_topic import survey_topic

import os
from typing import Optional
from agentic.runtime import Runtime


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


__all__ = ['comprehensive_lit_review', 'identify_gaps', 'search_arxiv', 'search_semantic_scholar', 'survey_topic', 'run_literature']
