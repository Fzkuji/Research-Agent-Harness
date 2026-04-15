"""Operation log — append-only trace of research_agent actions.

If a log_file path is provided, every function call is recorded.
Otherwise logging is silently skipped.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone


def append(log_file: str | None, text: str):
    """Append a line to the log file. No-op if log_file is None."""
    if not log_file:
        return
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    with open(log_file, "a") as f:
        f.write(text)


def log_session(log_file: str | None, task: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    append(log_file, f"\n---\n# {ts} — {task}\n\n")


def log_stage(log_file: str | None, stage_num: int, stage: str, sub_task: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    append(log_file, f"## [{stage}] Stage {stage_num} ({ts})\n{sub_task}\n\n")


def log_step(log_file: str | None, call: str, args_summary: str,
             success: bool, result_preview: str):
    status = "OK" if success else "FAIL"
    append(log_file, f"- `{call}({args_summary})` **{status}**: {result_preview}\n")


def log_done(log_file: str | None, reasoning: str):
    append(log_file, f"\n**DONE**: {reasoning}\n")
