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

from agentic.function import agentic_function
from agentic.runtime import Runtime

from research_harness.registry import (
    STAGES, AUTO_PARAMS,
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

You are a senior ML researcher managing a research project.
Based on the task and what has been done so far, pick the next stage.

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

You are a dispatcher. Your ONLY job is to pick a function and its arguments. Do NOT do the work yourself.

You are working in the [{stage}] stage.

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
- Set stage_done=true ONLY when all necessary work in this stage has been completed by previous function calls.
- Do NOT include `runtime`, `exec_runtime`, `review_runtime`, or `project_dir` in args — they are auto-injected.
- Prefer orchestrator functions (run_literature, run_idea, run_experiments, review_loop, paper_improvement_loop, etc.) for complete workflows. They chain multiple steps internally.

Args:
    stage: Current research stage name.
    sub_task: What to accomplish in this step.
    context: Results from previous steps in this stage.
    runtime: LLM runtime instance.
    review_runtime: Separate runtime for review tasks (different model).
"""
    functions = build_stage_functions(stage)
    reply = runtime.exec(content=[
        {"type": "text", "text": (
            f"Sub-task: {sub_task}\n\n"
            f"Context from previous steps:\n{context or '(first step)'}\n\n"
            f"{functions}"
            f"{_PERSISTENCE_REMINDER}"
        )},
    ])
    try:
        decision = parse_json(reply)
    except ValueError:
        return {"call": None, "result": reply[:500], "success": True, "stage_done": True}

    # Check if LLM signals stage completion
    if decision.get("stage_done") or decision.get("done"):
        return {"call": None, "result": decision.get("reasoning", "stage complete"), "success": True, "stage_done": True}

    call_target = decision.get("call", "")
    args = decision.get("args", {})

    func = get_function(call_target)
    if func is None:
        return {"call": call_target, "result": f"Unknown function: {call_target}", "success": False}

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
        }
    except Exception as e:
        return {
            "call": call_target,
            "result": f"{e.__class__.__name__}: {e}",
            "success": False,
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
# Runtime factory
# ═══════════════════════════════════════════

def _create_runtime(provider: str = None, model: str = None):
    """Auto-detect and create an LLM runtime from available providers.

    Providers:
        claude-code: Claude Code CLI (default, full file system access)
        codex:       OpenAI Codex CLI (session continuity, repo access)
        openai:      OpenAI API (stateless, needs OPENAI_API_KEY)
        anthropic:   Anthropic API (stateless, needs ANTHROPIC_API_KEY)
    """
    import os

    if provider == "codex":
        from agentic.providers import CodexRuntime
        return CodexRuntime(model=model or "gpt-5.4-mini", session_id="auto")

    if provider == "openai" or (provider is None and os.environ.get("OPENAI_API_KEY")):
        from agentic.providers import OpenAIRuntime
        return OpenAIRuntime(model=model or "gpt-4o")

    if provider == "anthropic" or (provider is None and os.environ.get("ANTHROPIC_API_KEY")):
        from agentic.providers import AnthropicRuntime
        return AnthropicRuntime(model=model or "claude-sonnet-4-20250514")

    if provider == "claude-code" or provider is None:
        from agentic.providers import ClaudeCodeRuntime
        return ClaudeCodeRuntime()

    raise RuntimeError(
        "No LLM provider available. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
        "or use --provider claude-code / --provider codex."
    )


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

    rt = _create_runtime(provider=args.provider, model=args.model)

    # Create separate review runtime for cross-model review
    review_rt = None
    if args.review_provider or args.review_model:
        review_rt = _create_runtime(
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
