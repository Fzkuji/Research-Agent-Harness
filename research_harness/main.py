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
from openprogram.programs.functions.buildin.build_catalog import build_catalog
from openprogram.programs.functions.buildin.parse_action import parse_action
from openprogram.programs.functions.buildin.prepare_args import prepare_args

from research_harness.registry import (
    STAGES, AUTO_PARAMS, HIDDEN_PARAMS,
    get_function,
    build_stages_available, build_stage_available,
)


# ═══════════════════════════════════════════
# Level 1: Pick a stage
# ═══════════════════════════════════════════

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def _pick_stage(task: str, progress: str, runtime: Runtime) -> dict:
    """Route a research task to the next stage. Single-step classification.

Pick one entry from the Stages catalog below. Reply in the standard
openprogram dispatch action format:

    {"call": "<stage_name>", "args": {"sub_task": "..."}}

Picking `call`:
Read each stage's description in the catalog. Look at Progress so far. If
the stage that naturally produces that progress isn't complete, continue
there. If it is complete, pick the stage that consumes its output. For a
fresh project, start with the earliest stage that fits unless the task
explicitly skips it.

`sub_task` guidance is in the catalog. The downstream stage dispatcher
reads it to locate the project workspace folder, so copy the user's path
or research direction verbatim — do not paraphrase.

Pick `"call": "done"` (no args) only when every stage has finished and
the final artifact exists.

Args:
    task: The user's research project description.
    progress: Summary of what prior stages produced.
    runtime: LLM runtime instance.
"""
    available = build_stages_available()
    catalog = build_catalog(available)
    reply = runtime.exec(content=[
        {"type": "text", "text": (
            f"User project description:\n{task}\n\n"
            f"Progress so far:\n{progress or '(nothing yet)'}\n\n"
            f"== Stages ==\n{catalog}"
        )},
    ])
    action = parse_action(reply)
    if action is None:
        return {"stage": None, "reasoning": str(reply)[:200], "done": True}
    call = action.get("call") or ""
    if call == "done":
        return {"stage": None, "reasoning": "LLM signaled done", "done": True}
    if call not in available:
        return {"stage": None, "reasoning": f"unknown call: {call!r}; reply: {str(reply)[:200]}",
                "done": True}
    args = action.get("args") or {}
    return {
        "stage": call,
        "sub_task": args.get("sub_task", ""),
        "reasoning": "",
        "done": False,
    }


# ═══════════════════════════════════════════
# Level 2: Execute within a stage
# ═══════════════════════════════════════════

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def _stage_step(stage: str, sub_task: str, context: str,
                runtime: Runtime, review_runtime: Runtime = None) -> dict:
    """Pick ONE function from this stage's catalog and return the action
to execute. This is a routing step — the chosen function does the work.

Reply in the standard openprogram dispatch action format:

    {"call": "<function_name>", "args": { ... }}

Pick `"call": "stage_done"` (no args) only when previous steps have
already completed this stage and no further call is needed this turn.

Orchestrator preference:
If the catalog lists a "run_*" / "*_loop" orchestrator for this stage
(e.g. run_literature, run_idea, run_experiments, review_loop,
paper_improvement_loop), prefer it over calling individual leaf
functions yourself — the orchestrator chains steps internally and
persists state. If it returns done=false (or an equivalent incomplete
signal), call it AGAIN next turn. Do not mark the stage done just
because an orchestrator was called once — check the returned flag.

All results must be saved to files. Orchestrators save automatically;
for individual leaves, save the output yourself.

Workspace path (for orchestrators taking `output_dir`):
Pass `output_dir` as an absolute path in this shape:

    output_dir = <base> / <project_name> / <stage_folder>

- base: if the task/sub_task/context mentions an absolute path
  (e.g. "/Users/.../LLM Distillation", "~/..."), reuse the directory
  CONTAINING that path. Otherwise use "<HOME>/Documents" (HOME is
  given in the input below).
- project_name: the last component of the mentioned path, or a readable
  name derived from the research direction. Use the SAME project_name
  across every stage of the same project.
- stage_folder: "literature review" | "ideas" | "experiments" | "paper"
  | "review" | "rebuttal" | "presentation" | "theory" | "knowledge" | ""
  (the "project" stage writes directly under the project root — empty
  stage_folder).

Example: user said "/Users/X/Documents/LLM Distillation", stage=literature
    → output_dir = "/Users/X/Documents/LLM Distillation/literature review"

If the computed directory already has material from a prior run, the
orchestrator resumes — do NOT invent a fresh folder. Never pass relative
paths like "auto_xxx".

Args:
    stage: Current research stage name.
    sub_task: What to accomplish in this step.
    context: Results from previous steps in this stage.
    runtime: LLM runtime instance.
    review_runtime: Separate runtime for review tasks.
"""
    import os as _os
    available = build_stage_available(stage)
    catalog = build_catalog(available)
    home = _os.path.expanduser("~")
    reply = runtime.exec(content=[
        {"type": "text", "text": (
            f"Current stage: [{stage}]\n\n"
            f"Sub-task: {sub_task}\n\n"
            f"Context from previous steps:\n{context or '(first step)'}\n\n"
            f"HOME: {home}\n\n"
            f"== Functions ==\n{catalog}"
        )},
    ])
    action = parse_action(reply)
    if action is None:
        return {"call": None, "result": f"JSON parse failed: {str(reply)[:500]}",
                "success": False, "stage_done": False}

    call = action.get("call") or ""
    if call == "stage_done":
        return {
            "call": None,
            "result": "LLM signaled stage_done",
            "success": True,
            "stage_done": True,
        }
    if call not in available:
        return {"call": call, "result": f"Unknown function: {call}",
                "success": False, "stage_done": False}

    # Drop system-controlled params the LLM may have set
    raw_args = {k: v for k, v in (action.get("args") or {}).items()
                if k not in HIDDEN_PARAMS}
    cleaned_action = {"call": call, "args": raw_args}

    try:
        args = prepare_args(cleaned_action, available, runtime)
    except ValueError as e:
        return {"call": call, "result": str(e), "success": False, "stage_done": False}

    # prepare_args wires `runtime` into every AUTO_PARAM slot the function
    # exposes, but stage_step routes review tasks to a separate reviewer
    # runtime when one is configured — override after the fact.
    func = available[call]["function"]
    func_sig = inspect.signature(func)
    if "review_runtime" in func_sig.parameters and review_runtime is not None:
        args["review_runtime"] = review_runtime

    try:
        result = func(**args)
        result_str = str(result) if result is not None else "(no output)"
        return {
            "call": call,
            "args_summary": ", ".join(
                f"{k}={str(v)[:30]}" for k, v in args.items() if k not in AUTO_PARAMS
            ),
            "result": result_str[:3000],
            "success": True,
            "stage_done": False,
        }
    except Exception as e:
        return {
            "call": call,
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
