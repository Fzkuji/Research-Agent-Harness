"""Stage: idea"""

from research_harness.stages.idea.check_novelty import check_novelty
from research_harness.stages.idea.generate_ideas import generate_ideas
from research_harness.stages.idea.rank_ideas import rank_ideas

from agentic.runtime import Runtime


def run_idea(
    topic: str,
    gaps: str = "",
    runtime: Runtime = None,
) -> dict:
    """Run the full idea generation workflow: generate → novelty check → rank.

    Each function saves its own output to files via the runtime agent.

    Args:
        topic:   Research topic.
        gaps:    Identified research gaps (from literature stage).
        runtime: LLM runtime.

    Returns:
        dict with ideas, novelty, and ranking summaries.
    """
    if not gaps:
        gaps = "No gaps identified yet. Generate ideas based on the topic directly."

    ideas = generate_ideas(topic=topic, gaps=gaps, runtime=runtime)
    novelty = check_novelty(idea=ideas, runtime=runtime)
    ranking = rank_ideas(ideas=ideas, novelty_results=novelty, runtime=runtime)
    return {"ideas": ideas, "novelty": novelty, "ranking": ranking}


__all__ = ['check_novelty', 'generate_ideas', 'rank_ideas', 'run_idea']
