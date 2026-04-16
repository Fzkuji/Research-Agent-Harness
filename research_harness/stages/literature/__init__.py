"""Stage: literature"""

import os

from research_harness.stages.literature.comprehensive_lit_review import comprehensive_lit_review
from research_harness.stages.literature.identify_gaps import identify_gaps
from research_harness.stages.literature.search_arxiv import search_arxiv
from research_harness.stages.literature.search_semantic_scholar import search_semantic_scholar
from research_harness.stages.literature.survey_topic import survey_topic

from agentic.runtime import Runtime


def run_literature(
    topic: str,
    output_dir: str = "auto_literature",
    runtime: Runtime = None,
) -> dict:
    """Run the full literature survey workflow: survey → identify gaps → save.

    Args:
        topic:      Research topic/direction.
        output_dir: Directory to save outputs (default: auto_literature/).
        runtime:    LLM runtime.

    Returns:
        dict with summary string.
    """
    os.makedirs(output_dir, exist_ok=True)

    survey = survey_topic(topic=topic, runtime=runtime)
    with open(os.path.join(output_dir, "survey.md"), "w") as f:
        f.write(survey)

    gaps = identify_gaps(survey=survey, runtime=runtime)
    with open(os.path.join(output_dir, "gaps.md"), "w") as f:
        f.write(gaps)

    summary = (
        f"# Literature Survey Summary\n\n"
        f"- **Topic**: {topic}\n"
        f"- **Survey**: `{output_dir}/survey.md`\n"
        f"- **Gaps**: `{output_dir}/gaps.md`\n"
    )
    with open(os.path.join(output_dir, "SUMMARY.md"), "w") as f:
        f.write(summary)

    return {"summary": summary, "survey": survey, "gaps": gaps}


__all__ = ['comprehensive_lit_review', 'identify_gaps', 'search_arxiv', 'search_semantic_scholar', 'survey_topic', 'run_literature']
