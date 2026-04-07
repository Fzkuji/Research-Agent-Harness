"""Stage: experiment"""

from research_harness.stages.experiment.check_training import check_training
from research_harness.stages.experiment.design_experiments import design_experiments
from research_harness.stages.experiment.experiment_bridge import experiment_bridge
from research_harness.stages.experiment.run_experiment import run_experiment

import os
from typing import Optional
from agentic.runtime import Runtime


def run_experiments(
    project_dir: str,
    runtime: Runtime,
) -> dict:
    """Run the experiment stage.

    Reads the idea report, designs experiments, and starts execution.

    Args:
        project_dir:  Project directory.
        runtime:      LLM runtime.

    Returns:
        dict with experiment plan and execution status.
    """
    project_dir = os.path.expanduser(project_dir)

    # Read idea
    idea_path = os.path.join(project_dir, "IDEA_REPORT.md")
    if os.path.exists(idea_path):
        with open(idea_path, "r") as f:
            idea = f.read()
    else:
        idea = "No idea report found. Design experiments based on project context."
        # Try outline
        outline_path = os.path.join(project_dir, "outline", "outline.md")
        if os.path.exists(outline_path):
            with open(outline_path, "r") as f:
                idea = f.read()

    # Design
    plan = design_experiments(idea=idea, runtime=runtime)

    # Save plan
    exp_dir = os.path.join(project_dir, "experiments")
    os.makedirs(exp_dir, exist_ok=True)
    with open(os.path.join(exp_dir, "EXPERIMENT_PLAN.md"), "w") as f:
        f.write(f"# Experiment Plan\n\n{plan}")

    return {"plan": plan, "status": "planned"}


__all__ = ['check_training', 'design_experiments', 'experiment_bridge', 'run_experiment', 'run_experiments']
