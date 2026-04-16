"""Stage: idea"""

import os

from research_harness.stages.idea.check_novelty import check_novelty
from research_harness.stages.idea.generate_ideas import generate_ideas
from research_harness.stages.idea.rank_ideas import rank_ideas

from agentic.runtime import Runtime


def run_idea(
    topic: str,
    gaps: str = "",
    output_dir: str = "auto_idea",
    runtime: Runtime = None,
) -> dict:
    """Run the full idea generation workflow: generate → novelty check → rank → save.

    Args:
        topic:      Research topic.
        gaps:       Identified research gaps (from literature stage).
        output_dir: Directory to save outputs (default: auto_idea/).
        runtime:    LLM runtime.

    Returns:
        dict with summary string.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not gaps:
        gaps = "No gaps identified yet. Generate ideas based on the topic directly."

    ideas = generate_ideas(topic=topic, gaps=gaps, runtime=runtime)
    with open(os.path.join(output_dir, "ideas.md"), "w") as f:
        f.write(ideas)

    novelty = check_novelty(idea=ideas, runtime=runtime)
    with open(os.path.join(output_dir, "novelty.md"), "w") as f:
        f.write(novelty)

    ranking = rank_ideas(ideas=ideas, novelty_results=novelty, runtime=runtime)
    with open(os.path.join(output_dir, "ranking.md"), "w") as f:
        f.write(ranking)

    summary = (
        f"# Idea Generation Summary\n\n"
        f"- **Topic**: {topic}\n"
        f"- **Ideas**: `{output_dir}/ideas.md`\n"
        f"- **Novelty check**: `{output_dir}/novelty.md`\n"
        f"- **Ranking**: `{output_dir}/ranking.md`\n"
    )
    with open(os.path.join(output_dir, "SUMMARY.md"), "w") as f:
        f.write(summary)

    return {"summary": summary, "ideas": ideas, "novelty": novelty, "ranking": ranking}


__all__ = ['check_novelty', 'generate_ideas', 'rank_ideas', 'run_idea']
