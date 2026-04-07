"""Stage: idea"""

from research_harness.stages.idea.check_novelty import check_novelty
from research_harness.stages.idea.generate_ideas import generate_ideas
from research_harness.stages.idea.rank_ideas import rank_ideas

import os
from typing import Optional
from agentic.runtime import Runtime


def run_idea(
    topic: str,
    project_dir: str,
    runtime: Runtime,
) -> dict:
    """Run idea generation stage.

    Reads gaps from literature stage, generates and ranks ideas.

    Args:
        topic:        Research topic.
        project_dir:  Project directory.
        runtime:      LLM runtime.

    Returns:
        dict with ideas, novelty checks, and ranking.
    """
    project_dir = os.path.expanduser(project_dir)

    # Read gaps from literature stage
    gaps_path = os.path.join(project_dir, "related_work", "gaps.md")
    if os.path.exists(gaps_path):
        with open(gaps_path, "r") as f:
            gaps = f.read()
    else:
        gaps = "No gaps identified yet. Generate ideas based on the topic directly."

    ideas = generate_ideas(topic=topic, gaps=gaps, runtime=runtime)

    # Check novelty for each idea
    novelty = check_novelty(idea=ideas, runtime=runtime)

    # Rank
    ranking = rank_ideas(ideas=ideas, novelty_results=novelty, runtime=runtime)

    # Save
    with open(os.path.join(project_dir, "IDEA_REPORT.md"), "w") as f:
        f.write(f"# Idea Report: {topic}\n\n")
        f.write(f"## Generated Ideas\n{ideas}\n\n")
        f.write(f"## Novelty Assessment\n{novelty}\n\n")
        f.write(f"## Ranking\n{ranking}\n")

    return {"ideas": ideas, "novelty": novelty, "ranking": ranking}


__all__ = ['check_novelty', 'generate_ideas', 'rank_ideas', 'run_idea']
