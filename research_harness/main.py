"""
main — entry point for Research Agent Harness.

Two-level autonomous loop:
  Level 1: LLM picks which research STAGE to enter
  Level 2: Within a stage, LLM picks and executes functions sequentially

Each level is a separate @agentic_function (exec() once per call).
"""

from __future__ import annotations

import argparse
import inspect
import sys

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.registry import (
    STAGES, AUTO_PARAMS, HIDDEN_PARAMS,
    get_function, build_stage_list, build_stage_functions,
    stage_functions,
)
from research_harness.utils import parse_json


# ═══════════════════════════════════════════
# Level 1: Pick a stage
# ═══════════════════════════════════════════

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def _pick_stage(task: str, progress: str, runtime: Runtime) -> dict:
    """Given a research task and current progress, decide which stage to work on next.

Reply with ONLY a single JSON object. Do NOT run any commands, do NOT
read any files, do NOT use any tools. Inspect only the text provided
below and output the JSON.

Available stages:
{stages}

Return JSON:
{
  "stage": "stage_name",
  "reasoning": "why this stage is needed now",
  "sub_task": "specific goal for this stage",
  "done": false
}

Set done=true ONLY when the overall task is FULLY complete.

Workspace routing — IMPORTANT:
Every research project writes to a single workspace directory shared across
stages. If the user's task mentions an absolute path (e.g. "/Users/.../X",
"~/...") or a clearly named project folder, COPY that path (or project name)
verbatim into `sub_task`. If the task only names a research direction (no
path), write that direction into `sub_task` so the next level can derive a
workspace from it. The next level (stage dispatcher) needs this information
to construct `output_dir`; do NOT strip it out.

Args:
    task: The overall research task.
    progress: Summary of what has been accomplished so far.
    runtime: LLM runtime instance.
"""
    stages = build_stage_list()
    reply = runtime.exec(content=[
        {"type": "text", "text": (
            f"Task: {task}\n\n"
            f"Progress so far:\n{progress or '(nothing yet)'}\n\n"
            f"Available stages:\n{stages}"
        )},
    ])
    try:
        return parse_json(reply)
    except ValueError:
        return {"stage": None, "reasoning": reply[:200], "done": True}


# ═══════════════════════════════════════════
# Level 2: Execute within a stage
# ═══════════════════════════════════════════

_PERSISTENCE_REMINDER = (
    "\n\nIMPORTANT: All results must be saved to files — nothing should be lost. "
    "Orchestrator functions (run_literature, run_idea, run_experiments, review_loop, paper_improvement_loop, etc.) already save results. "
    "For individual functions, save the output yourself."
)

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def _stage_step(stage: str, sub_task: str, context: str,
                runtime: Runtime, review_runtime: Runtime = None) -> dict:
    """Within a research stage, pick and execute the best function for the sub-task.

Reply with ONLY a single JSON object. Do NOT run any commands, do NOT
read any files, do NOT use any tools, do NOT do the work yourself —
your ONLY job is to pick a function name and its arguments from the
list below.

Current stage: [{stage}]

Available functions in this stage:
{functions}

Return JSON:
{
  "call": "function_name",
  "args": {"param": "value"},
  "reasoning": "why this function",
  "stage_done": false
}

Rules:
- You MUST pick a function from the list above. Do NOT attempt to do the work yourself.
- `stage_done` describes the state of PREVIOUS steps (seen in the context above), NOT this call.
  - Set stage_done=true ONLY when previous steps have already completed this stage and no further call is needed. In that case, omit `call` (set to null).
  - If you are requesting a call this turn, ALWAYS set stage_done=false. The stage cannot be done before this call has executed.
- Do NOT include `runtime`, `exec_runtime`, `review_runtime`, or `project_dir` in args — they are auto-injected.
- Do NOT include `max_iters`, `max_outer`, `max_inner`, or any similar
  iteration/retry caps — those are system-controlled defaults. You decide
  WHEN to stop (by choosing not to call the orchestrator again once its
  result shows the work is done), not HOW MANY steps it gets per call.
- Prefer orchestrator functions (run_literature, run_idea, run_experiments, review_loop, paper_improvement_loop, etc.) for complete workflows. They chain multiple steps internally.
- If an orchestrator returns `done: false` (or similar incomplete signal) in
  its result, call it AGAIN on the next turn so it can continue. Do NOT mark
  the stage done just because an orchestrator was called once — check the
  returned `done` flag.

Workspace path — when calling an orchestrator that accepts `output_dir`
(run_literature, run_idea, run_experiments, review_loop, ...), YOU MUST
construct and pass `output_dir` as an ABSOLUTE path in this shape:

    output_dir = <base> / <project_name> / <stage_folder>

Where:
  base          — if the task/sub_task/context mentions an absolute path
                  (e.g. "/Users/.../LLM Distillation", "~/..."), treat the
                  DIRECTORY CONTAINING that path as `base`, and reuse the
                  LAST COMPONENT as `project_name`.
                  Example: user said "/Users/X/Documents/LLM Distillation"
                           → base="/Users/X/Documents",
                             project_name="LLM Distillation".
                  If no path is mentioned, default `base` to
                  "<HOME>/Documents" (the absolute HOME is given in the
                  runtime-provided "HOME: ..." line below).
  project_name  — human-readable name for the overall research project,
                  derived from the task. Use the SAME project_name across
                  every stage of the same project (literature → idea →
                  experiment → writing all share one folder).
                  Example: "LLM Distillation", "Retrieval-Augmented Generation".
  stage_folder  — readable folder for THIS stage:
                    literature   → "literature review"
                    idea         → "ideas"
                    experiment   → "experiments"
                    writing      → "paper"
                    review       → "review"
                    rebuttal     → "rebuttal"
                    presentation → "presentation"
                    theory       → "theory"
                    knowledge    → "knowledge"
                    project      → "" (write directly under the project root)

Examples (replace <HOME> with the actual path given below):
  Task: "调研 LLM 蒸馏"  (no path given, stage=literature)
    → output_dir = "<HOME>/Documents/LLM Distillation/literature review"
  Task: "研究 retrieval，存到 ~/Documents/RAG"  (stage=idea)
    → output_dir = "<HOME>/Documents/RAG/ideas"
  Task: "继续之前在 <HOME>/Documents/LLM Distillation 的调研"
        (stage=literature)
    → output_dir = "<HOME>/Documents/LLM Distillation/literature review"
    (If this directory already has material from a prior run, the orchestrator
    will pick up where it left off — do NOT invent a fresh folder.)

Always pass ABSOLUTE paths. Do not pass relative paths like "auto_literature".
Never invent a sibling folder like "auto_xxx" — use the readable stage folder
name from the list above.

Args:
    stage: Current research stage name.
    sub_task: What to accomplish in this step.
    context: Results from previous steps in this stage.
    runtime: LLM runtime instance.
    review_runtime: Separate runtime for review tasks (different model).
"""
    import os as _os
    functions = build_stage_functions(stage)
    home = _os.path.expanduser("~")
    reply = runtime.exec(content=[
        {"type": "text", "text": (
            f"Sub-task: {sub_task}\n\n"
            f"Context from previous steps:\n{context or '(first step)'}\n\n"
            f"HOME: {home}\n"
            f"(Use this absolute path wherever the dispatcher prompt references <HOME>.)\n\n"
            f"{functions}"
            f"{_PERSISTENCE_REMINDER}"
        )},
    ])
    try:
        decision = parse_json(reply)
    except ValueError:
        # Parse failure is a real failure — do NOT mark the stage as done.
        return {"call": None, "result": f"JSON parse failed: {reply[:500]}",
                "success": False, "stage_done": False}

    call_target = decision.get("call") or ""
    args = decision.get("args") or {}
    stage_done_flag = bool(decision.get("stage_done") or decision.get("done"))

    # No call requested — only then honor stage_done as "stage already finished".
    if not call_target:
        return {
            "call": None,
            "result": decision.get("reasoning", "stage complete" if stage_done_flag else "no function selected"),
            "success": True,
            "stage_done": stage_done_flag,
        }

    func = get_function(call_target)
    if func is None:
        return {"call": call_target, "result": f"Unknown function: {call_target}",
                "success": False, "stage_done": False}

    # Drop any system-controlled params the LLM tried to set (iteration caps,
    # retry limits, etc.). These are not LLM's decision.
    args = {k: v for k, v in args.items() if k not in HIDDEN_PARAMS}

    # Inject auto-params: review_runtime gets the dedicated reviewer,
    # runtime/exec_runtime get the main executor
    sig = inspect.signature(func)
    for p_name in sig.parameters:
        if p_name in AUTO_PARAMS and p_name not in args:
            if p_name == "review_runtime" and review_runtime is not None:
                args[p_name] = review_runtime
            else:
                args[p_name] = runtime

    try:
        result = func(**args)
        result_str = str(result) if result is not None else "(no output)"
        return {
            "call": call_target,
            "args_summary": ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items() if k not in AUTO_PARAMS),
            "result": result_str[:3000],
            "success": True,
            # Only propagate stage_done after the call actually executed.
            "stage_done": stage_done_flag,
        }
    except Exception as e:
        return {
            "call": call_target,
            "result": f"{e.__class__.__name__}: {e}",
            "success": False,
            "stage_done": False,
        }


# ═══════════════════════════════════════════
# research_agent — top-level entry
# ═══════════════════════════════════════════

_MAX_STAGES = 10
_MAX_STEPS_PER_STAGE = 20


@agentic_function(
    compress=True,
    summarize={"siblings": -1},
    input={
        "task": {
            "source": "llm",
            "description": "Research task (natural language)",
            "placeholder": "e.g. Survey recent work on LLM uncertainty",
            "multiline": True,
        },
        "runtime": {"hidden": True},
    },
)
def research_agent(
    task: str,
    runtime: Runtime = None,
    review_runtime: Runtime = None,
) -> dict:
    """Autonomous research agent with two-level control.

Level 1: LLM decides which research stage to enter (literature, idea, writing, etc.)
Level 2: Within a stage, LLM sequentially picks and executes functions.

Cross-model review: when review_runtime is provided, review functions use a
different model (e.g. GPT) from the executor (e.g. Claude). This follows the
ARIS design where the reviewer and author are adversarial by being different models.

Args:
    task: What the user wants to accomplish.
    runtime: LLM runtime instance (executor).
    review_runtime: Separate LLM runtime for review (different model recommended).

Returns:
    dict with: task, success, stages_completed, history
"""
    if runtime is None:
        raise ValueError("research_agent() requires a runtime argument")

    # Init log
    history = []
    progress_parts = []

    for stage_num in range(1, _MAX_STAGES + 1):
        # Level 1: Pick stage
        progress = "\n".join(progress_parts) if progress_parts else ""
        stage_decision = _pick_stage(task=task, progress=progress, runtime=runtime)

        if stage_decision.get("done"):
            reasoning = stage_decision.get('reasoning', '')[:80]
            print(f"  [stage {stage_num}] DONE: {reasoning}", file=sys.stderr)

            history.append({"stage_num": stage_num, "stage": "done", "decision": stage_decision})
            break

        stage = stage_decision.get("stage", "")
        sub_task = stage_decision.get("sub_task", task)
        reasoning = stage_decision.get("reasoning", "")

        if stage not in STAGES:
            print(f"  [stage {stage_num}] Unknown stage: {stage}", file=sys.stderr)
            history.append({"stage_num": stage_num, "stage": stage, "error": "unknown stage"})
            continue

        print(f"  [stage {stage_num}] → {stage}: {reasoning[:80]}", file=sys.stderr)


        # Level 2: Execute within stage
        stage_context_parts = []
        stage_history = []

        for step_num in range(1, _MAX_STEPS_PER_STAGE + 1):
            context = "\n".join(stage_context_parts) if stage_context_parts else ""
            step_result = _stage_step(
                stage=stage, sub_task=sub_task, context=context,
                runtime=runtime, review_runtime=review_runtime,
            )

            call = step_result.get("call", "?")
            success = step_result.get("success", False)
            result_preview = step_result.get("result", "")[:200]
            args_summary = step_result.get("args_summary", "")

            print(f"    [{stage}/{step_num}] {call}: {'OK' if success else 'FAIL'}", file=sys.stderr)


            stage_history.append(step_result)
            stage_context_parts.append(f"  {call} → {result_preview}")

            # Stage is done if: no function call resolved, or LLM signals stage_done
            if step_result.get("call") is None or step_result.get("stage_done"):
                break

        # Summarize stage progress
        stage_summary = f"[{stage}] {sub_task}: " + "; ".join(
            f"{h.get('call', '?')}={'OK' if h.get('success') else 'FAIL'}"
            for h in stage_history
        )
        progress_parts.append(stage_summary)
        history.append({
            "stage_num": stage_num,
            "stage": stage,
            "sub_task": sub_task,
            "steps": stage_history,
        })

    completed = any(
        h.get("stage") == "done" or h.get("decision", {}).get("done")
        for h in history
    )

    return {
        "task": task,
        "success": completed,
        "stages_completed": len(history),
        "history": history,
    }


# Backwards compatibility
agentic_research = research_agent


# ═══════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Research Agent — autonomous research task execution"
    )
    parser.add_argument("task", nargs="?", help="What to do (natural language)")
    parser.add_argument("--provider", help="LLM provider: claude-code, codex, openai, anthropic")
    parser.add_argument("--model", help="Model name override")
    parser.add_argument("--review-provider", help="Review model provider (default: codex for cross-model review)")
    parser.add_argument("--review-model", help="Review model name (default: gpt-5.4-mini)")
    parser.add_argument("--list", action="store_true", help="List all available functions")
    args = parser.parse_args()

    if args.list:
        from research_harness.registry import build_function_list
        print("research-harness: available functions")
        print("=" * 60)
        print(build_function_list())
        return

    task = args.task
    if task is None:
        if not sys.stdin.isatty():
            task = sys.stdin.read().strip()
        else:
            parser.print_help()
            return

    from openprogram.providers import create_runtime

    rt = create_runtime(provider=args.provider or "auto", model=args.model)

    # Create separate review runtime for cross-model review
    review_rt = None
    if args.review_provider or args.review_model:
        review_rt = create_runtime(
            provider=args.review_provider or "openai",
            model=args.review_model,
        )

    print(f"Task: {task}")
    print(f"Executor: {args.provider or 'auto'}/{args.model or 'default'}")
    if review_rt:
        print(f"Reviewer: {args.review_provider or 'openai'}/{args.review_model or 'default'}")
    print()

    result = research_agent(
        task=task,
        runtime=rt,
        review_runtime=review_rt,
    )

    # Report
    print()
    print("=" * 60)
    success = result.get("success", False)
    print(f"{'OK' if success else 'FAIL'} | Task: {result.get('task', task)}")
    print(f"Stages: {result.get('stages_completed', '?')}")
    print()
    for h in result.get("history", []):
        stage = h.get("stage", "?")
        sub = h.get("sub_task", "")
        print(f"  Stage {h.get('stage_num', '?')}: [{stage}] {sub[:60]}")
        for s in h.get("steps", []):
            call = s.get("call", "?")
            ok = "OK" if s.get("success") else "FAIL"
            print(f"    - {call} [{ok}]: {s.get('result', '')[:60]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
