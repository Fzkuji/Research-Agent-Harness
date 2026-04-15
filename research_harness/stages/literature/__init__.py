"""Stage: literature"""

from research_harness.stages.literature.comprehensive_lit_review import comprehensive_lit_review
from research_harness.stages.literature.identify_gaps import identify_gaps
from research_harness.stages.literature.search_arxiv import search_arxiv
from research_harness.stages.literature.search_semantic_scholar import search_semantic_scholar
from research_harness.stages.literature.survey_topic import survey_topic

from agentic.runtime import Runtime


def run_literature(
    topic: str,
    runtime: Runtime = None,
) -> dict:
    """Run the full literature survey workflow: survey → identify gaps.

    Each function saves its own output to files via the runtime agent.
    This orchestrator just chains the calls in the right order.

    Args:
        topic:   Research topic/direction.
        runtime: LLM runtime.

    Returns:
        dict with survey and gaps summaries.
    """
    survey = survey_topic(topic=topic, runtime=runtime)
    gaps = identify_gaps(survey=survey, runtime=runtime)
    return {"survey": survey, "gaps": gaps}


__all__ = ['comprehensive_lit_review', 'identify_gaps', 'search_arxiv', 'search_semantic_scholar', 'survey_topic', 'run_literature']
