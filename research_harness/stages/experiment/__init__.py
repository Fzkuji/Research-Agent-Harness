"""Stage: experiment"""

import os

from research_harness.stages.experiment.check_training import check_training
from research_harness.stages.experiment.design_experiments import design_experiments
from research_harness.stages.experiment.experiment_bridge import experiment_bridge
from research_harness.stages.experiment.run_experiment import run_experiment

from openprogram.agentic_programming.runtime import Runtime


def run_experiments(
    idea: str = "",
    output_dir: str = "auto_experiment",
    runtime: Runtime = None,
) -> dict:
    """Run the experiment workflow: design plan → save.

    Args:
        idea:       Research idea or plan to design experiments for.
        output_dir: Directory to save outputs (default: auto_experiment/).
        runtime:    LLM runtime.

    Returns:
        dict with summary string.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not idea:
        idea = "Design experiments based on the project context in the current directory."

    plan = design_experiments(idea=idea, runtime=runtime)
    with open(os.path.join(output_dir, "plan.md"), "w") as f:
        f.write(plan)

    summary = (
        f"# Experiment Plan Summary\n\n"
        f"- **Plan**: `{output_dir}/plan.md`\n"
    )
    with open(os.path.join(output_dir, "SUMMARY.md"), "w") as f:
        f.write(summary)

    return {"summary": summary, "plan": plan}


__all__ = ['check_training', 'design_experiments', 'experiment_bridge', 'run_experiment', 'run_experiments']
