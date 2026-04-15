"""Stage: experiment"""

from research_harness.stages.experiment.check_training import check_training
from research_harness.stages.experiment.design_experiments import design_experiments
from research_harness.stages.experiment.experiment_bridge import experiment_bridge
from research_harness.stages.experiment.run_experiment import run_experiment

from agentic.runtime import Runtime


def run_experiments(
    idea: str = "",
    runtime: Runtime = None,
) -> dict:
    """Run the experiment workflow: design plan → bridge to implementation.

    Each function saves its own output to files via the runtime agent.

    Args:
        idea:    Research idea or plan to design experiments for.
        runtime: LLM runtime.

    Returns:
        dict with experiment plan.
    """
    if not idea:
        idea = "Design experiments based on the project context in the current directory."

    plan = design_experiments(idea=idea, runtime=runtime)
    return {"plan": plan}


__all__ = ['check_training', 'design_experiments', 'experiment_bridge', 'run_experiment', 'run_experiments']
