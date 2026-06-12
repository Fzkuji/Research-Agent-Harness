from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"siblings": -1})
def run_experiment(plan: str, step: str, runtime: Runtime) -> str:
    """Execute one step of the experiment plan.

    You have full freedom to write code, run commands, install packages,
    and manage files. Do whatever is needed to execute this step.

    After execution, report:
    - What you did
    - Results obtained (exact numbers)
    - Any issues encountered
    - What to do next

    Output: Execution report with results.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."

    ALSO write a machine-readable run_record.json NEXT TO your report file:
    {"run_id": "<short unique id for this run>",
     "command": "<exact command(s) executed>",
     "config_summary": "<key hyperparameters / config used>",
     "exit_status": "<exit code, or 'ok'/'failed'>",
     "result_files": ["<paths of result files this run produced>"],
     "key_metrics": {"<metric name>": <value>},
     "seeds": [<random seeds used, [] if none>],
     "timestamp_note": "<when the run happened>"}
    Every number you report in the text MUST appear in key_metrics or in a
    listed result file — the integrity gate later audits paper claims
    against these run records. If the step ran nothing (e.g. setup only),
    still write the record with key_metrics: {} and exit_status noted.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Experiment plan:\n{plan}\n\n"
            f"Current step:\n{step}"
        )},
    ])
