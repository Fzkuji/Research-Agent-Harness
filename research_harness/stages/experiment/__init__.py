"""Stage: experiment"""

import os

from research_harness.stages.experiment.check_training import check_training
from research_harness.stages.experiment.design_experiments import design_experiments
from research_harness.stages.experiment.experiment_bridge import experiment_bridge
from research_harness.stages.experiment.run_experiment import run_experiment

from openprogram.agentic_programming.runtime import Runtime


_MAX_EXPERIMENT_STEPS = 8


def run_experiments(
    idea: str = "",
    output_dir: str = "auto_experiment",
    runtime: Runtime = None,
    max_steps: int = _MAX_EXPERIMENT_STEPS,
    execute: bool = True,
) -> dict:
    """Design AND RUN the experiment plan: design → execute steps → summarize.

    Previously this only DESIGNED a plan and stopped — the autonomous loop
    then "succeeded" without ever running anything, so papers got written and
    reviewed with zero measured results. Now it closes the loop: after
    designing the plan it executes it step by step via ``run_experiment``
    (each step writes a machine-readable ``run_record.json`` with key
    metrics), then writes a SUMMARY that points at those records. The writer
    and integrity gate read run records, so real numbers flow into the paper.

    Args:
        idea:       Research idea or plan to design experiments for.
        output_dir: Directory to save outputs (plan.md, run records, SUMMARY).
        runtime:    LLM runtime (must have a working directory / shell to run).
        max_steps:  Hard cap on execution steps (default 8) so a single call
                    can't spin forever — the autonomous loop's own budgets
                    still apply on top.
        execute:    When False, only design the plan (the old behaviour), for
                    callers that explicitly want plan-only.

    Returns:
        dict with summary, plan, steps_run, and done.
    """
    os.makedirs(output_dir, exist_ok=True)

    if runtime is None:
        raise ValueError("Runtime parameter is required for experiment module")

    if not idea:
        idea = "Design experiments based on the project context in the current directory."

    plan = design_experiments(idea=idea, runtime=runtime)
    with open(os.path.join(output_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write(plan)

    if not execute:
        summary = (f"# Experiment Plan Summary\n\n- **Plan**: `{output_dir}/plan.md`\n"
                   "- **Status**: plan only (execute=False)\n")
        with open(os.path.join(output_dir, "SUMMARY.md"), "w", encoding="utf-8") as f:
            f.write(summary)
        return {"summary": summary, "plan": plan, "steps_run": 0, "done": True}

    # Execute the plan step by step. Each run_experiment call sees the plan
    # plus a running log of what already ran (its reports + result files), so
    # it picks the next concrete step, runs code, and writes run_record.json.
    # Stop when the model signals completion or the step cap is hit.
    from research_harness.stop import stop_requested

    reports: list[str] = []
    steps_run = 0
    done = False
    from research_harness.steering import pending_current as _steer_pending
    for i in range(1, max_steps + 1):
        # Graceful stop: a run-level stop (Ctrl-C / stop button) lands here
        # too, not just the outer loop — finish nothing new, summarize what ran.
        if stop_requested():
            break
        # Mid-run steering: yield to research_agent so a course-correction is
        # absorbed promptly instead of after all steps run.
        if _steer_pending():
            break
        prior = "\n\n".join(reports[-3:]) if reports else "(nothing run yet)"
        step_instruction = (
            f"Execute the NEXT not-yet-done step of the experiment plan and "
            f"write its run_record.json into {output_dir}. If every step in "
            f"the plan has already been executed (see the log), reply with a "
            f"single line: DONE — and do nothing else.\n\n"
            f"=== Output dir for records/results ===\n{output_dir}\n\n"
            f"=== Steps already executed (most recent) ===\n{prior}"
        )
        report = str(run_experiment(plan=plan, step=step_instruction, runtime=runtime))
        steps_run = i
        if report.strip().upper().startswith("DONE") or "\nDONE" in report.strip().upper()[:200]:
            done = True
            break
        reports.append(f"### Step {i}\n{report[:2000]}")

    # Aggregate run records into the SUMMARY (what the writer/integrity gate read).
    import glob as _glob
    import json as _json
    records = []
    for rp in sorted(_glob.glob(os.path.join(output_dir, "**", "run_record.json"),
                                recursive=True)):
        try:
            with open(rp, encoding="utf-8") as f:
                rec = _json.load(f)
            metrics = rec.get("key_metrics", {})
            records.append(f"- `{os.path.relpath(rp, output_dir)}` — "
                           f"exit={rec.get('exit_status','?')}, "
                           f"metrics={_json.dumps(metrics, ensure_ascii=False)[:300]}")
        except (OSError, ValueError):
            records.append(f"- `{os.path.relpath(rp, output_dir)}` — (unreadable run_record)")

    summary = (
        f"# Experiment Summary\n\n"
        f"- **Plan**: `{output_dir}/plan.md`\n"
        f"- **Steps executed**: {steps_run}"
        f"{' (completed)' if done else ' (hit step cap — may be partial)'}\n"
        f"- **Run records found**: {len(records)}\n\n"
        f"## Measured runs\n"
        + ("\n".join(records) if records else
           "(no run_record.json produced — steps may have only set up environment "
           "or failed to execute; the paper must keep results illustrative.)")
        + "\n"
    )
    with open(os.path.join(output_dir, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write(summary)

    return {"summary": summary, "plan": plan, "steps_run": steps_run, "done": done}


__all__ = ['check_training', 'design_experiments', 'experiment_bridge', 'run_experiment', 'run_experiments']
