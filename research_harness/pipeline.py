"""
pipeline — main research workflow orchestrator.

Chains all stages: init → literature → idea → experiment →
analysis → writing → review → submission.

Each stage can run independently. Supports starting from any stage.

Usage:
    from research_harness.pipeline import research_pipeline

    # Full pipeline
    result = research_pipeline(
        project_dir="~/research/LLM Uncertainty",
        topic="Uncertainty quantification in LLMs",
        venue="NeurIPS",
        exec_runtime=claude_runtime,
        review_runtime=gpt_runtime,
    )

    # Just writing + review
    result = research_pipeline(
        project_dir="~/research/LLM Uncertainty",
        stages=["writing", "review"],
        exec_runtime=claude_runtime,
    )
"""

from __future__ import annotations

import os
from typing import Optional

from openprogram.agentic_programming.runtime import Runtime


STAGES = [
    "init", "literature", "idea", "experiment",
    "analysis", "writing", "review", "submission",
]


def research_pipeline(
    project_dir: str,
    topic: str = None,
    venue: str = None,
    stages: list[str] = None,
    start_from: str = None,
    exec_runtime: Runtime = None,
    review_runtime: Runtime = None,
    callback: Optional[callable] = None,
) -> dict:
    """Run the research pipeline.

    Args:
        project_dir:     Path to research project directory.
        topic:           Research topic (needed for literature/idea stages).
        venue:           Target venue (e.g. "NeurIPS").
        stages:          Specific stages to run (default: all).
        start_from:      Start from this stage.
        exec_runtime:    Runtime for execution tasks.
        review_runtime:  Runtime for review (different model recommended).
        callback:        Progress callback.

    Returns:
        dict with results from each completed stage.
    """
    if exec_runtime is None:
        raise ValueError("exec_runtime is required")

    project_dir = os.path.expanduser(project_dir)

    # Determine stages to run
    if stages is not None:
        run_stages = [s for s in stages if s in STAGES]
    elif start_from is not None:
        idx = STAGES.index(start_from)
        run_stages = STAGES[idx:]
    else:
        run_stages = STAGES

    results = {}
    handlers = {
        "init": lambda: _stage_init(project_dir, venue),
        "literature": lambda: _stage_literature(project_dir, topic, exec_runtime),
        "idea": lambda: _stage_idea(project_dir, topic, exec_runtime),
        "experiment": lambda: _stage_experiment(project_dir, exec_runtime),
        "analysis": lambda: _stage_analysis(project_dir, exec_runtime),
        "writing": lambda: _stage_writing(project_dir, exec_runtime),
        "review": lambda: _stage_review(project_dir, venue, exec_runtime, review_runtime, callback),
        "submission": lambda: _stage_submission(project_dir, venue, exec_runtime),
    }

    for stage in run_stages:
        if stage == "writing":
            # Integrity gate between analysis and writing: audit empirical
            # claims against run records. v1 warns loudly but does not block.
            results["integrity_gate"] = _run_integrity_gate(
                project_dir, exec_runtime)

        if callback:
            callback({"type": "stage_start", "stage": stage})

        handler = handlers.get(stage)
        if handler:
            results[stage] = handler()

        if callback:
            callback({"type": "stage_done", "stage": stage, "result": results.get(stage)})

    return results


# ---------------------------------------------------------------------------
# Stage handlers
# ---------------------------------------------------------------------------

def _stage_init(project_dir, venue):
    from research_harness.stages.init import init_research
    if os.path.exists(project_dir):
        return {"status": "exists", "path": project_dir}
    name = os.path.basename(project_dir)
    base = os.path.dirname(project_dir)
    path = init_research(name=name, venue=venue, base_dir=base)
    return {"status": "created", "path": path}


def _stage_literature(project_dir, topic, runtime):
    from research_harness.stages.literature import run_literature
    if not topic:
        return {"status": "skipped", "reason": "no topic provided"}
    # Dedicated subfolder — writing into project_dir would clobber the
    # project README.md that _stage_init just created.
    return run_literature(direction=topic,
                          output_dir=os.path.join(project_dir, "literature review"),
                          runtime=runtime)


def _stage_idea(project_dir, topic, runtime):
    from research_harness.stages.idea import run_idea
    if not topic:
        return {"status": "skipped", "reason": "no topic provided"}
    return run_idea(topic=topic,
                    output_dir=os.path.join(project_dir, "auto_idea"),
                    runtime=runtime)


def _stage_experiment(project_dir, runtime):
    from research_harness.stages.experiment import run_experiments
    idea = ""
    ranking = os.path.join(project_dir, "auto_idea", "ranking.md")
    if os.path.exists(ranking):
        with open(ranking, "r", encoding="utf-8") as f:
            idea = f.read()
    return run_experiments(idea=idea,
                           output_dir=os.path.join(project_dir, "auto_experiment"),
                           runtime=runtime)


def _stage_analysis(project_dir, runtime):
    from research_harness.stages.writing import analyze_results
    exp_dir = os.path.join(project_dir, "experiments")
    if not os.path.isdir(exp_dir):
        return {"status": "no_experiments_dir"}
    data_files = [f for f in os.listdir(exp_dir)
                  if f.endswith((".csv", ".json", ".txt"))]
    if not data_files:
        return {"status": "no_data_files"}
    results = {}
    for fname in data_files:
        with open(os.path.join(exp_dir, fname), "r") as f:
            data = f.read()
        output = analyze_results(data=data, runtime=runtime)
        results[fname] = output[:500]
    return results


def _run_integrity_gate(project_dir, runtime):
    """Audit draft claims against run records before writing (warn, don't block).

    On failure, writes project_dir/INTEGRITY_WARNINGS.md listing the failing
    claims; _stage_writing embeds it into every section's context.
    """
    from research_harness.stages.integrity import integrity_gate
    try:
        result = integrity_gate(project_dir, runtime=runtime)
    except Exception as e:  # the gate must never kill the pipeline in v1
        print(f"[integrity] gate error (continuing): {e}")
        return {"passed": None, "error": str(e)}

    if not result.get("passed", True):
        failures = result.get("failures", [])
        lines = [
            "# INTEGRITY WARNINGS",
            "",
            f"The integrity gate FAILED: {len(failures)} claim(s) lack provenance.",
            f"Full report: {result.get('report_path')}",
            "Do NOT state these claims as established results. Weaken, qualify,",
            "or drop them unless run evidence is added.",
            "",
        ]
        for f in failures:
            lines.append(f"- [{f.get('verdict')}] {f.get('claim')}")
        warn_path = os.path.join(project_dir, "INTEGRITY_WARNINGS.md")
        with open(warn_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"[integrity] GATE FAILED — {len(failures)} claim(s) lack "
              f"provenance. Warnings written to {warn_path}; the writing "
              f"stage will embed them.")
    return result


def _stage_writing(project_dir, runtime):
    from research_harness.stages.writing import write_section, gather_context
    sections = ["introduction", "method", "experiments", "related_work", "conclusion"]
    section_files = {
        "introduction": "1Introduction.tex",
        "method": "2Method.tex",
        "experiments": "3Experiments.tex",
        "related_work": "5RelatedWork.tex",
        "conclusion": "6Conclusion.tex",
    }
    results = {}
    os.makedirs(os.path.join(project_dir, "paper"), exist_ok=True)
    integrity_warnings = ""
    warn_path = os.path.join(project_dir, "INTEGRITY_WARNINGS.md")
    if os.path.exists(warn_path):
        with open(warn_path, "r", encoding="utf-8") as f:
            integrity_warnings = f.read()
    for section in sections:
        ctx = gather_context(project_dir, section)
        if integrity_warnings:
            ctx = (f"## Integrity warnings (claims lacking provenance)\n"
                   f"{integrity_warnings}\n\n{ctx}")
        content = write_section(section=section, context=ctx, runtime=runtime)
        tex_file = section_files[section]
        with open(os.path.join(project_dir, "paper", tex_file), "w", encoding="utf-8") as f:
            f.write(content)
        results[section] = {"status": "written", "length": len(content)}
    return results


def _stage_review(project_dir, venue, exec_runtime, review_runtime, callback):
    from research_harness.stages.review import review_loop
    paper_dir = os.path.join(project_dir, "paper")
    return review_loop(
        paper_dir=paper_dir, venue=venue or "NeurIPS",
        exec_runtime=exec_runtime,
        review_runtime=review_runtime or exec_runtime,
        callback=callback,
    )


def _stage_submission(project_dir, venue, runtime):
    from research_harness.stages.submission import run_submission_check
    return run_submission_check(
        project_dir=project_dir, venue=venue or "NeurIPS", runtime=runtime,
    )
