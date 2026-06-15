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
import os
import sys

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime
from openprogram.agentic_programming.decision import (
    DecisionError,
    render_options,
    extract_action,
    parse_args,
)

from research_harness.registry import (
    STAGES, AUTO_PARAMS, HIDDEN_PARAMS,
    build_stage_available,
)


# ═══════════════════════════════════════════
# Level 1: Pick a stage
# ═══════════════════════════════════════════

_SUB_TASK_FIELD = (
    "if the task mentions an absolute path (/Users/.../X, ~/...) or a "
    "named project folder, copy that string verbatim; otherwise copy "
    "the research direction phrase"
)


def _stage_choices() -> dict:
    """Stage routing options for `exec(choices=...)` (next-step decision).

    Each stage is a schema option — picking it returns
    {"decision": <stage>, "sub_task": ...}. `done` is a value option that
    resolves directly to the loop's terminal dict.
    """
    choices: dict = {
        stage: (desc, {"sub_task": _SUB_TASK_FIELD})
        for stage, desc in STAGES.items()
    }
    choices["done"] = (
        {"stage": None, "reasoning": "LLM signaled done",
         "done": True, "ok": True},
        "Mark the overall task complete. Pick only when every stage has "
        "finished and the final artifact exists.",
    )
    return choices


@agentic_function(render_range={"depth": 0, "siblings": 0})
def _pick_stage(task: str, progress: str, runtime: Runtime) -> dict:
    """Route a research task to its next stage — one next-step decision."""
    try:
        result = runtime.exec(
            content=[{"type": "text", "text": (
                f"User project description:\n{task}\n\n"
                f"Progress so far:\n{progress or '(nothing yet)'}\n\n"
                "Pick the next stage to enter. Read each stage's "
                "description and the progress so far: if the stage that "
                "produces the current progress is not finished, continue "
                "it; once it is, pick the stage that consumes its output. "
                "For a fresh project, start at the earliest stage that "
                "fits unless the task explicitly skips it.\n\n"
                "Typical dependency order — do NOT pick a stage whose "
                "input doesn't exist yet:\n"
                "  literature → idea → experiment → writing → review → "
                "rebuttal/presentation\n"
                "A stage needs its predecessor's output: idea needs gaps "
                "from literature; experiment needs an idea; writing needs "
                "results; review needs a written paper; rebuttal needs "
                "reviews. If 'Progress so far' shows the predecessor "
                "hasn't run, pick the PREDECESSOR, not the consumer. Skip "
                "a stage only when the task explicitly asks for just one "
                "stage (e.g. 'just survey the literature').\n\n"
                "Copy the user's path or research direction into "
                "`sub_task` verbatim — the downstream dispatcher uses it "
                "to locate the project folder, so do not paraphrase."
            )}],
            choices=_stage_choices(),
        )
    except DecisionError as e:
        # The framework already re-asked once; a still-unresolvable pick
        # ends the loop as a failure, never as silent success.
        return {"stage": None, "reasoning": str(e)[:200],
                "done": True, "ok": False}
    if isinstance(result, dict) and "decision" in result:
        return {
            "stage": result["decision"],
            "sub_task": result.get("sub_task", ""),
            "reasoning": "",
            "done": False,
            "ok": True,
        }
    if isinstance(result, dict):
        return result  # the `done` value option resolves to the terminal dict
    return {"stage": None, "reasoning": str(result)[:200],
            "done": True, "ok": False}


# ═══════════════════════════════════════════
# Level 2: Execute within a stage
# ═══════════════════════════════════════════

@agentic_function(render_range={"depth": 0, "siblings": 0})
def _stage_step(stage: str, sub_task: str, context: str,
                runtime: Runtime, review_runtime: Runtime = None,
                blocked: frozenset = frozenset()) -> dict:
    """Pick and dispatch one function within a research stage — one routing step.

    ``blocked`` is the set of function names that have failed too many
    times this run; they are removed from the catalog so the LLM cannot
    keep re-selecting a broken function (the loop's failure backstop).
    """
    import os as _os
    available = build_stage_available(stage)
    if blocked:
        available = {n: e for n, e in available.items() if n not in blocked}
    catalog = render_options(available)
    home = _os.path.expanduser("~")
    reply = runtime.exec(content=[
        {"type": "text", "text": (
            f"Current stage: [{stage}]\n\n"
            f"Sub-task: {sub_task}\n\n"
            f"Context from previous steps:\n{context or '(first step)'}\n\n"
            f"HOME: {home}\n\n"
            f"== Functions ==\n{catalog}\n\n"
            "Pick ONE function from the catalog to run this turn.\n\n"
            'If the catalog lists a "run_*" / "*_loop" orchestrator '
            "(run_literature, run_idea, run_experiments, review_loop, "
            "paper_improvement_loop ...), prefer it over individual leaf "
            "functions. An orchestrator runs its OWN internal loop to "
            "completion in a single call — it iterates as many rounds as "
            "the work needs and persists state. Call it ONCE; do NOT "
            "re-call it to 'continue' — it already finished its rounds. "
            "After it returns, the stage's deliverable exists: do any "
            "leftover leaf work, otherwise reply stage_done. (Only re-call "
            "an orchestrator if its result explicitly says it was "
            "interrupted and must resume.) "
            "All results must be saved to files: orchestrators save "
            "automatically, for leaf functions save the output "
            "yourself.\n\n"
            "For an orchestrator taking `output_dir`, pass an absolute "
            "path shaped <base>/<project_name>/<stage_folder>:\n"
            "- base: if the task/sub_task/context names an absolute "
            'path ("/Users/.../LLM Distillation", "~/..."), reuse the '
            "directory CONTAINING it; otherwise use <HOME>/Documents.\n"
            "- project_name: the last component of that path, or a "
            "readable name from the research direction — keep it the "
            "SAME across every stage of one project.\n"
            '- stage_folder: one of "literature review", "ideas", '
            '"experiments", "paper", "review", "rebuttal", '
            '"presentation", "theory", "knowledge", or "" (the '
            '"project" stage writes at the project root).\n'
            "If that directory already holds material from a prior run, "
            "the orchestrator resumes — do not invent a fresh folder. "
            'Never pass relative paths like "auto_xxx".\n\n'
            "Reply with this exact JSON and nothing else:\n"
            '  {"call": "<function_name>", "args": { ... }}\n'
            'Reply {"call": "stage_done"} (no args) only when previous '
            "steps already completed this stage."
        )},
    ])
    action = extract_action(reply)
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

    # parse_args takes the RAW reply, locates the chosen function in the
    # stage registry, validates + binds its args (runtime auto-injected,
    # non-signature / hidden args dropped) and returns (callable, kwargs).
    try:
        func, args = parse_args(reply, available, runtime)
    except ValueError as e:
        return {"call": call, "result": str(e), "success": False, "stage_done": False}

    # parse_args retries internally on arg-validation failure and the
    # re-pick may bind a DIFFERENT function than the first reply named —
    # trust the callable it returns and re-derive the name for history.
    call = next(
        (n for n, ent in available.items() if ent["function"] is func), call
    )
    if call == "stage_done":
        return {
            "call": None,
            "result": "LLM signaled stage_done",
            "success": True,
            "stage_done": True,
        }

    # parse_args wires `runtime` into every AUTO_PARAM slot the function
    # exposes, but stage_step routes review tasks to a separate reviewer
    # runtime when one is configured — override after the fact.
    func_sig = inspect.signature(func)
    if "review_runtime" in func_sig.parameters and review_runtime is not None:
        args["review_runtime"] = review_runtime

    # Self-closing iteration: an orchestrator that exposes `auto_fix`
    # (review_loop) defaults it to False, which makes it run ONE review
    # round and stop — pushing the review→fix→re-review loop onto the LLM
    # to drive by re-calling. That mechanical re-calling is exactly what
    # spins. Inside the agent loop we want the orchestrator to close its
    # own loop in a single call, so default auto_fix to True unless the
    # LLM explicitly set it. (CLI / pipeline callers pass it explicitly
    # and are unaffected.)
    if "auto_fix" in func_sig.parameters and "auto_fix" not in args:
        args["auto_fix"] = True

    try:
        result = func(**args)
        result_str = str(result) if result is not None else "(no output)"
        # Normalize the orchestrator's completion signal in ONE place so the
        # loop doesn't depend on the LLM parsing str(result). Stage
        # orchestrators are inconsistent: run_literature returns `done`,
        # review_loop returns `passed`, several single-shot ones
        # (run_idea / run_experiments / run_rebuttal / run_slides / ...)
        # return no flag at all. Map all of them to one `func_done` bool:
        #   - dict with `done`   -> use it (the iterating orchestrators)
        #   - dict with `passed` -> map it (review_loop: passed==accepted)
        #   - dict without a flag, or a non-dict (str / None) -> True
        #     (a single-shot function that ran is, by definition, done)
        if isinstance(result, dict) and "done" in result:
            func_done = bool(result.get("done"))
        elif isinstance(result, dict) and "passed" in result:
            func_done = bool(result.get("passed"))
        else:
            func_done = True
        return {
            "call": call,
            "args_summary": ", ".join(
                f"{k}={str(v)[:30]}" for k, v in args.items() if k not in AUTO_PARAMS
            ),
            "result": result_str[:3000],
            "success": True,
            # Did the function itself report it has nothing left to do this
            # turn? The loop uses this (not str(result)) to decide whether a
            # re-call of an iterating orchestrator is warranted.
            "func_done": func_done,
            # An LLM may attach stage_done=true alongside a call — execute
            # the call first, then honor the flag.
            "stage_done": bool(action.get("stage_done")),
        }
    except Exception as e:
        return {
            "call": call,
            "result": f"{e.__class__.__name__}: {e}",
            "success": False,
            "func_done": False,
            "stage_done": False,
        }


# ═══════════════════════════════════════════
# research_agent — top-level entry
# ═══════════════════════════════════════════

_MAX_STAGES = 10
_MAX_STEPS_PER_STAGE = 20
# Repetition guard: an LLM that re-picks the SAME function with the SAME
# args is spinning (e.g. a chat-only runtime that cannot save files keeps
# "retrying" a save). Warn it once, then cut the stage off.
_REPEAT_WARN = 3
_REPEAT_BREAK = 5

# Global run budget — a hard ceiling on TOTAL Level-2 steps across all
# stages, independent of per-stage / per-stage-count caps. Without this a
# run can ping-pong between two stages (e.g. review <-> writing), each
# under its own limits, yet burn hundreds of steps overall. This is the
# backstop the per-stage guards can't provide.
_MAX_TOTAL_STEPS = 60
# A stage that is RE-ENTERED this many times without the run advancing
# (no new successful step since the last visit) is stuck — stop re-routing
# back into it. Catches the cross-stage ping-pong the per-stage repeat
# guard is blind to.
_MAX_STAGE_REVISITS = 3
# A single function that FAILS this many times across the whole run is
# broken for this run (bad env, missing dependency, a model that won't
# call its submit tool). Drop it from the catalog so the loop stops
# retrying it and the LLM must route around it.
_MAX_FUNC_FAILURES = 3


# ═══════════════════════════════════════════
# conclusion — LLM reports what the research run accomplished
# ═══════════════════════════════════════════

def _conclusion(task: str, history: list, completed: bool, runtime: Runtime) -> str:
    """Have the LLM write a short report of what the research run did.

    Reads the per-stage history (which functions ran in which stage) and
    answers the user's task: what was done, what was produced, where the
    artifacts are. Returns a plain-text report.
    """
    from research_harness.utils import parse_json

    lines = []
    for h in history:
        stage = h.get("stage", "?")
        if stage == "done":
            continue
        sub = h.get("sub_task", "")
        calls = "; ".join(
            f"{s.get('call', '?')}={'OK' if s.get('success') else 'FAIL'}"
            for s in h.get("steps", [])
        )
        lines.append(f"- [{stage}] {sub}: {calls}")
    trace = "\n".join(lines) if lines else "(no stages executed)"

    status = "completed" if completed else "stopped before an explicit done signal"
    context = (
        f"<original_user_task>{task}</original_user_task>\n\n"
        f"(Internal run status — DO NOT mention raw status words in the report: "
        f"{status})\n\n"
        f"Stages executed and the functions each ran:\n{trace}\n\n"
        "Your job: write a `summary` that reports what this research run "
        "ACCOMPLISHED for the user's task. Cover: which stages ran, what "
        "concrete artifacts were produced (files, drafts, search results), "
        "and where they live (cite paths if the trace shows file writes). "
        "If the run produced a deliverable, name it. Be specific and "
        "grounded in the trace — do not invent results that aren't there.\n\n"
        "Reply with ONLY this JSON object:\n"
        '{"summary": "<what the run accomplished>", '
        '"success": true, "issues": "any problems, or null"}'
    )

    reply = runtime.exec(content=[{"type": "text", "text": context}])
    try:
        parsed = parse_json(reply)
        return parsed.get("summary", reply)
    except Exception:
        return reply[:1000]


@agentic_function(
    as_tool=True,
    toolset=("harness",),
    render_range={"siblings": -1},
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

    Level 1: the LLM picks which research stage to enter (literature,
    idea, writing, ...). Level 2: within a stage, the LLM sequentially
    picks and runs functions. When review_runtime is provided, review
    functions run on a different model from the executor (ARIS-style
    adversarial reviewer). The runtime's working directory must be set
    before calling — every shell command and file write runs with that
    as cwd. Returns a dict with task, success, summary,
    stages_completed, history.
    """
    if runtime is None:
        raise ValueError("research_agent() requires a runtime argument")

    history = []
    progress_parts = []
    # Run-wide guards (cross-stage; the per-stage repeat guard can't see these):
    total_steps = 0                       # against _MAX_TOTAL_STEPS
    func_failures: dict[str, int] = {}    # function name -> failure count
    blocked_funcs: set[str] = set()       # funcs dropped after too many failures
    stage_visits: dict[str, int] = {}     # stage -> times entered
    successes_at_last_visit: dict[str, int] = {}  # stage -> total_successes seen last time
    total_successes = 0
    stop_reason = None

    for stage_num in range(1, _MAX_STAGES + 1):
        if total_steps >= _MAX_TOTAL_STEPS:
            stop_reason = f"global step budget reached ({_MAX_TOTAL_STEPS})"
            print(f"  [budget] {stop_reason} — ending run.", file=sys.stderr)
            break

        # Level 1: Pick stage
        progress = "\n".join(progress_parts) if progress_parts else ""
        stage_decision = _pick_stage(task=task, progress=progress, runtime=runtime)

        if stage_decision.get("done"):
            reasoning = stage_decision.get('reasoning', '')[:80]
            print(f"  [stage {stage_num}] DONE: {reasoning}", file=sys.stderr)
            history.append({"stage_num": stage_num, "stage": "done", "decision": stage_decision})
            break

        stage = stage_decision.get("stage", "")
        sub_task = stage_decision.get("sub_task") or task
        reasoning = stage_decision.get("reasoning", "")

        if stage not in STAGES:
            print(f"  [stage {stage_num}] Unknown stage: {stage}", file=sys.stderr)
            history.append({"stage_num": stage_num, "stage": stage, "error": "unknown stage"})
            continue

        # Cross-stage ping-pong guard: if we keep re-entering a stage that
        # isn't moving the run forward (no new successful step since the
        # last time we were here), it's stuck — refuse to route back in.
        stage_visits[stage] = stage_visits.get(stage, 0) + 1
        if stage_visits[stage] > _MAX_STAGE_REVISITS:
            prev = successes_at_last_visit.get(stage, -1)
            if total_successes == prev:
                stop_reason = (
                    f"stage '{stage}' re-entered {stage_visits[stage]}x with no "
                    f"progress — stuck"
                )
                print(f"  [stuck] {stop_reason} — ending run.", file=sys.stderr)
                history.append({"stage_num": stage_num, "stage": stage,
                                "error": "stuck — no progress on re-entry"})
                break
        successes_at_last_visit[stage] = total_successes

        print(f"  [stage {stage_num}] → {stage}: {reasoning[:80]}", file=sys.stderr)

        # Level 2: Execute within stage
        stage_context_parts = []
        stage_history = []
        last_repeat_id = None
        repeat_count = 0

        for step_num in range(1, _MAX_STEPS_PER_STAGE + 1):
            if total_steps >= _MAX_TOTAL_STEPS:
                stop_reason = f"global step budget reached ({_MAX_TOTAL_STEPS})"
                print(f"    [budget] {stop_reason} — ending stage.", file=sys.stderr)
                break

            context = "\n".join(stage_context_parts) if stage_context_parts else ""
            step_result = _stage_step(
                stage=stage, sub_task=sub_task, context=context,
                runtime=runtime, review_runtime=review_runtime,
                blocked=frozenset(blocked_funcs),
            )
            total_steps += 1

            call = step_result.get("call", "?")
            success = step_result.get("success", False)
            func_done = step_result.get("func_done", False)
            result_preview = step_result.get("result", "")[:200]
            args_summary = step_result.get("args_summary", "")

            print(f"    [{stage}/{step_num}] {call}: {'OK' if success else 'FAIL'}", file=sys.stderr)

            stage_history.append(step_result)
            stage_context_parts.append(f"  {call} → {result_preview}")

            # Failure backstop: a function that fails repeatedly across the
            # WHOLE run is broken (bad env, a model that won't call its
            # submit tool, …). Count failures and, past the cap, drop it
            # from the catalog so it can't be re-selected.
            if call and call != "?":
                if success:
                    total_successes += 1
                else:
                    func_failures[call] = func_failures.get(call, 0) + 1
                    if (func_failures[call] >= _MAX_FUNC_FAILURES
                            and call not in blocked_funcs):
                        blocked_funcs.add(call)
                        print(
                            f"    [block] {call} failed {func_failures[call]}x "
                            f"this run — removed from the catalog.",
                            file=sys.stderr,
                        )
                        stage_context_parts.append(
                            f"  NOTE: {call} failed repeatedly and is now "
                            "DISABLED for this run. Use a different function "
                            "or stage_done."
                        )

            # Stage is done if: no function call resolved, or LLM signals stage_done
            if step_result.get("call") is None or step_result.get("stage_done"):
                break

            # An iterating orchestrator that reports it finished its work
            # (func_done) signals the stage's core deliverable is in place.
            # Tell the model explicitly — it no longer has to infer "done"
            # by parsing str(result), the failure mode that caused spinning.
            if success and func_done:
                stage_context_parts.append(
                    f"  NOTE: {call} reported it COMPLETED its work "
                    "(done=true). The stage's main deliverable exists — "
                    "do remaining cleanup or reply stage_done."
                )

            # Repetition guard: identical (function, args) calls in a row.
            repeat_id = (call, args_summary)
            if repeat_id == last_repeat_id:
                repeat_count += 1
            else:
                last_repeat_id, repeat_count = repeat_id, 1
            if repeat_count == _REPEAT_WARN:
                stage_context_parts.append(
                    f"  NOTE: {call} has now run with identical arguments "
                    f"{_REPEAT_WARN} times — repeating it will not change "
                    "the result. Pick a DIFFERENT function, or stage_done."
                )
            elif repeat_count >= _REPEAT_BREAK:
                print(
                    f"    [{stage}] repetition guard: {call} ran with "
                    f"identical args {repeat_count} times — ending stage.",
                    file=sys.stderr,
                )
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

        if stop_reason:
            break

    # Only an explicit, well-formed LLM "done" counts as success —
    # parse failures and unknown stage names also end the loop (done=True)
    # but carry ok=False and must not be reported as task completion.
    completed = any(
        h.get("stage") == "done" and h.get("decision", {}).get("ok", False)
        for h in history
    )

    try:
        summary = _conclusion(task, history, completed, runtime)
    except Exception as e:
        print(f"  [conclusion] ERROR: {e}", file=sys.stderr)
        summary = ""

    return {
        "task": task,
        "success": completed,
        "summary": summary,
        "stages_completed": len(history),
        # Why the loop ended when it wasn't an explicit LLM "done":
        # "global step budget reached" / "stage '...' ... stuck" / None.
        # Lets the caller tell a clean finish from a guard-triggered stop.
        "stop_reason": stop_reason,
        "total_steps": total_steps,
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
    parser.add_argument("--work-dir",
                        help="Absolute path for all research artifacts. Runtime's codex --cd target.")
    parser.add_argument("--provider", help="LLM provider: claude-code, openai-codex, anthropic, openai")
    parser.add_argument("--model", help="Model name override")
    parser.add_argument("--review-provider", help="Review model provider (default: openai)")
    parser.add_argument("--review-model", help="Review model name (default: provider default)")
    parser.add_argument("--list", action="store_true", help="List all available functions")
    parser.add_argument("--chat", action="store_true",
                        help="Start with an attended Socratic planning dialogue; "
                             "afterwards you can hand the refined brief to the autonomous run")
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

    if not args.work_dir:
        parser.error("--work-dir is required to run a task")

    from openprogram.providers import create_runtime

    work_dir = os.path.abspath(os.path.expanduser(args.work_dir))
    os.makedirs(work_dir, exist_ok=True)

    rt = create_runtime(provider=args.provider or "auto", model=args.model)
    rt.set_workdir(work_dir)

    # Create separate review runtime for cross-model review
    review_rt = None
    if args.review_provider or args.review_model:
        review_rt = create_runtime(
            provider=args.review_provider or "openai",
            model=args.review_model,
        )
        review_rt.set_workdir(work_dir)

    print(f"Task: {task}")
    print(f"Executor: {args.provider or 'auto'}/{args.model or 'default'}")
    if review_rt:
        print(f"Reviewer: {args.review_provider or 'openai'}/{args.review_model or 'default'}")
    print()

    if args.chat:
        from research_harness.stages.interactive import socratic_plan
        print("— Socratic planning dialogue (answer in the terminal; "
              "type 'done' to finish early) —\n")
        chat_result = socratic_plan(topic=task, output_dir=work_dir, runtime=rt)
        print(f"\n{chat_result}\n")
        brief_path = os.path.join(work_dir, "RESEARCH_BRIEF.md")
        if not os.path.exists(brief_path):
            return
        try:
            go = input("Hand the brief to the autonomous run now? [y/N] ")
        except EOFError:
            go = ""
        if go.strip().lower() not in ("y", "yes"):
            print(f"Brief saved — rerun without --chat to start the "
                  f"autonomous run from {brief_path}.")
            return
        task = (f"{task}\n\nA confirmed research brief exists at "
                f"{brief_path} — follow it.")

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
