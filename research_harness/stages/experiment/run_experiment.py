from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"subcalls": -1})
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
    # Hand the model REAL execution tools (bash/read/write/edit/apply_patch/
    # glob/grep/...). Without tools, runtime.exec is a pure REASONING call —
    # the model can only DESCRIBE running an experiment, never actually write
    # code, run it, or save run_record.json. That is why "executed" steps
    # produced zero run records. toolset="default" gives the shell + file
    # tools the docstring promises ("write code, run commands, manage files").
    return runtime.exec(
        content=[
            {"type": "text", "text": (
                f"Experiment plan:\n{plan}\n\n"
                f"Current step:\n{step}"
            )},
        ],
        toolset="default",
    )
