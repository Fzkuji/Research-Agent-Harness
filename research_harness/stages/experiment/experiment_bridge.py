from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def experiment_bridge(plan: str, runtime: Runtime) -> str:
    """Bridge between idea discovery and auto review loop. Takes an experiment plan
    and turns it into running experiments with initial results.

    Pipeline position:
    refine-logs/EXPERIMENT_PLAN.md -> implement code -> cross-model review ->
    deploy -> collect -> initial results ready for auto-review-loop

    Workflow:
    Phase 1 - Parse the experiment plan:
    - Extract run order and milestones (sanity -> baseline -> main -> ablation)
    - For each experiment: dataset/split/task, compared systems, metrics,
      setup details, success criterion, priority (MUST-RUN vs NICE-TO-HAVE)
    - Extract compute budget (total GPU-hours)
    - Read method details from FINAL_PROPOSAL.md

    Phase 2 - Implement experiment code:
    - Check existing code for reusable scripts, model code, data loaders
    - Implement missing pieces: training scripts with argparse, evaluation
      scripts, data loading, baseline implementations, fixed random seeds,
      results saved to JSON/CSV, proper logging (wandb if configured)
    - Follow plan's run order: sanity first, then baselines, then main, then ablations
    - Self-review: all hyperparameters reflected? Seeds fixed? Results parseable?
      Code matches method description?

    Phase 2.5 - Cross-model code review (recommended):
    - Send implementation to external reviewer for correctness check:
      Does code match proposal? All hyperparameters present? Logic bugs?
      Evaluation metric correct? CRITICAL: Does evaluation use actual ground
      truth labels, NOT another model's output as ground truth?
    - Fix CRITICAL issues before deploying (max 2 review rounds)

    Phase 3 - Sanity check:
    - Run smallest/fastest experiment first to catch setup bugs
    - Verify: training loop runs, metrics computed correctly, GPU memory OK,
      output format correct
    - If sanity fails, auto-debug (max 3 attempts): read error, diagnose
      (OOM/ImportError/FileNotFoundError/CUDA/NaN), fix, re-run

    Phase 4 - Deploy full experiments:
    - Deploy in milestone order, parallel up to MAX_PARALLEL_RUNS
    - Monitor progress, collect results as experiments complete

    You have full freedom to write code, install packages, run commands.
    Start with the simplest experiment to validate the setup before scaling.

    Report: what was implemented, code review results, sanity check results,
    deployment status, initial results collected.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Experiment plan to implement:\n{plan}"},
    ])
