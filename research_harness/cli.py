"""
CLI entry point for research-agent-harness.

Usage:
    # Simple — just describe what you want (routes to agentic_research)
    research-harness "帮我润色这段话: ..."
    research-harness "survey LLM uncertainty"
    echo "some text" | research-harness "润色这段话"

    # Direct function call (for LLM agents or power users)
    research-harness polish_rigorous --text "some text"
    echo "text" | research-harness polish_rigorous
    research-harness survey_topic --topic "LLM uncertainty"
    research-harness init --name "My Project" --venue NeurIPS

    # Options
    research-harness --list                       # list all functions
    research-harness --provider codex "do stuff"  # choose provider
"""

from __future__ import annotations

import argparse
import inspect
import sys
from typing import get_type_hints

from agentic.providers import create_runtime
from agentic.runtime import Runtime


# ---------------------------------------------------------------------------
# Function registry — maps CLI name -> (import_path, function_name)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, tuple[str, str]] = {
    # Pipeline
    "pipeline":                 ("research_harness.pipeline", "research_pipeline"),
    # Init (not @agentic_function, but useful from CLI)
    "init":                     ("research_harness.stages.init", "init_research"),
    # Literature
    "survey_topic":             ("research_harness.stages.literature", "survey_topic"),
    "identify_gaps":            ("research_harness.stages.literature", "identify_gaps"),
    "search_arxiv":             ("research_harness.stages.literature", "search_arxiv"),
    "search_semantic_scholar":  ("research_harness.stages.literature", "search_semantic_scholar"),
    "comprehensive_lit_review": ("research_harness.stages.literature", "comprehensive_lit_review"),
    # Idea
    "generate_ideas":           ("research_harness.stages.idea", "generate_ideas"),
    "check_novelty":            ("research_harness.stages.idea", "check_novelty"),
    "rank_ideas":               ("research_harness.stages.idea", "rank_ideas"),
    # Experiment
    "design_experiments":       ("research_harness.stages.experiment", "design_experiments"),
    "experiment_bridge":        ("research_harness.stages.experiment", "experiment_bridge"),
    "run_experiment":           ("research_harness.stages.experiment", "run_experiment"),
    "check_training":           ("research_harness.stages.experiment", "check_training"),
    # Writing (English)
    "write_section":            ("research_harness.stages.writing", "write_section"),
    "polish_rigorous":          ("research_harness.stages.writing", "polish_rigorous"),
    "polish_natural":           ("research_harness.stages.writing", "polish_natural"),
    "compress_text":            ("research_harness.stages.writing", "compress_text"),
    "expand_text":              ("research_harness.stages.writing", "expand_text"),
    "check_logic":              ("research_harness.stages.writing", "check_logic"),
    "analyze_results":          ("research_harness.stages.writing", "analyze_results"),
    "results_to_claims":        ("research_harness.stages.writing", "results_to_claims"),
    "translate_zh2en":          ("research_harness.stages.writing", "translate_zh2en"),
    "translate_en2zh":          ("research_harness.stages.writing", "translate_en2zh"),
    "rewrite_zh":               ("research_harness.stages.writing", "rewrite_zh"),
    "polish_zh":                ("research_harness.stages.writing", "polish_zh"),
    "remove_ai_flavor_zh":      ("research_harness.stages.writing", "remove_ai_flavor_zh"),
    # Figures & Tables
    "generate_figure_caption":    ("research_harness.stages.writing", "generate_figure_caption"),
    "generate_table_caption":     ("research_harness.stages.writing", "generate_table_caption"),
    "recommend_visualization":    ("research_harness.stages.writing", "recommend_visualization"),
    "design_architecture_figure": ("research_harness.stages.writing", "design_architecture_figure"),
    "generate_paper_figures":     ("research_harness.stages.writing", "generate_paper_figures"),
    "generate_mermaid_diagram":   ("research_harness.stages.writing", "generate_mermaid_diagram"),
    "compile_paper":              ("research_harness.stages.writing", "compile_paper"),
    # Review
    "review_paper":             ("research_harness.stages.review", "review_paper"),
    "fix_paper":                ("research_harness.stages.review", "fix_paper"),
    # Rebuttal
    "parse_reviews":            ("research_harness.stages.rebuttal", "parse_reviews"),
    "build_rebuttal_strategy":  ("research_harness.stages.rebuttal", "build_rebuttal_strategy"),
    "draft_rebuttal":           ("research_harness.stages.rebuttal", "draft_rebuttal"),
    # Presentation
    "generate_slides":          ("research_harness.stages.presentation", "generate_slides"),
    "generate_poster":          ("research_harness.stages.presentation", "generate_poster"),
    "generate_speaker_notes":   ("research_harness.stages.presentation", "generate_speaker_notes"),
    # Theory
    "derive_formula":           ("research_harness.stages.theory", "derive_formula"),
    "write_proof":              ("research_harness.stages.theory", "write_proof"),
    "refine_research":          ("research_harness.stages.theory", "refine_research"),
    "plan_ablations":           ("research_harness.stages.theory", "plan_ablations"),
    "write_grant_proposal":     ("research_harness.stages.theory", "write_grant_proposal"),
    # Wiki & Meta
    "research_wiki":            ("research_harness.wiki.wiki_agent", "research_wiki"),
    "meta_optimize":            ("research_harness.stages.meta", "meta_optimize"),
}

# Parameters that are auto-injected (not taken from CLI)
_AUTO_PARAMS = {"runtime", "exec_runtime", "review_runtime"}


def _import_function(cli_name: str):
    """Lazily import and return the function."""
    import importlib
    module_path, func_name = _REGISTRY[cli_name]
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)


def _get_params(func) -> dict[str, inspect.Parameter]:
    """Get function parameters excluding auto-injected ones."""
    sig = inspect.signature(func)
    return {
        name: param
        for name, param in sig.parameters.items()
        if name not in _AUTO_PARAMS
    }


def _list_functions():
    """Print all available CLI functions."""
    print("research-harness: available functions")
    print("=" * 60)
    print("\nDefault mode: research-harness \"your task description\"")
    print("  Routes to agentic_research — LLM decides what to do.\n")

    categories = {}
    for name, (mod_path, _) in sorted(_REGISTRY.items()):
        if "pipeline" in mod_path:
            cat = "Pipeline"
        elif "init" in mod_path:
            cat = "Project"
        elif "literature" in mod_path:
            cat = "Literature"
        elif "idea" in mod_path:
            cat = "Idea"
        elif "experiment" in mod_path:
            cat = "Experiment"
        elif "writing" in mod_path:
            cat = "Writing"
        elif "review" in mod_path:
            cat = "Review"
        elif "rebuttal" in mod_path:
            cat = "Rebuttal"
        elif "presentation" in mod_path:
            cat = "Presentation"
        elif "theory" in mod_path:
            cat = "Theory"
        elif "wiki" in mod_path:
            cat = "Knowledge"
        elif "meta" in mod_path:
            cat = "Meta"
        else:
            cat = "Other"
        categories.setdefault(cat, []).append(name)

    print("Direct function calls (for LLM agents / power users):")
    for cat, names in categories.items():
        print(f"\n  {cat}:")
        for name in names:
            func = _import_function(name)
            params = _get_params(func)
            param_str = ", ".join(
                f"--{p.replace('_', '-')}"
                for p in params
            )
            print(f"    {name:30s} {param_str}")


def _read_stdin_if_available() -> str | None:
    """Read from stdin if it's piped (not a TTY)."""
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None


def _run_task(task: str, provider: str = None, model: str = None):
    """Default mode: pass a task string to agentic_research."""
    from research_harness.main import agentic_research

    rt = create_runtime(provider=provider, model=model)

    # Prepend stdin if available
    stdin_data = _read_stdin_if_available()
    if stdin_data is not None:
        task = f"{task}\n\n{stdin_data.strip()}"

    result = agentic_research(task=task, runtime=rt)
    if result is not None:
        print(result)


def _run_function(func_name: str, remaining: list[str],
                  provider: str = None, model: str = None):
    """Direct function call mode."""
    func = _import_function(func_name)
    params = _get_params(func)

    stdin_data = _read_stdin_if_available()

    # Which param can stdin fill?
    _STDIN_PARAMS = [
        "text", "topic", "query", "task", "data", "notes",
        "direction", "idea", "survey", "log", "theorem",
        "description", "paper_content", "reviews_text",
        "strategy", "slides_content", "method_description",
        "data_description",
    ]
    stdin_target = None
    if stdin_data is not None:
        for tp in _STDIN_PARAMS:
            if tp in params:
                stdin_target = tp
                break

    # Build sub-parser
    sub_parser = argparse.ArgumentParser(
        prog=f"research-harness {func_name}",
    )
    for pname, param in params.items():
        cli_flag = f"--{pname.replace('_', '-')}"
        ptype = str
        try:
            hints = get_type_hints(func)
            if pname in hints:
                h = hints[pname]
                if h is int or h == int:
                    ptype = int
        except Exception:
            pass

        required = param.default is inspect.Parameter.empty
        if pname == stdin_target:
            required = False
            sub_parser.add_argument(cli_flag, type=ptype, default=None)
        elif required:
            sub_parser.add_argument(cli_flag, type=ptype, required=True)
        else:
            sub_parser.add_argument(cli_flag, type=ptype, default=param.default)

    func_args = sub_parser.parse_args(remaining)
    kwargs = vars(func_args)

    # Fill from stdin
    if stdin_target and kwargs.get(stdin_target) is None:
        kwargs[stdin_target] = stdin_data.strip()

    # Inject runtime
    sig = inspect.signature(func)
    if "runtime" in sig.parameters or "exec_runtime" in sig.parameters:
        rt = create_runtime(provider=provider, model=model)
        if "runtime" in sig.parameters:
            kwargs["runtime"] = rt
        if "exec_runtime" in sig.parameters:
            kwargs["exec_runtime"] = rt
        if "review_runtime" in sig.parameters:
            kwargs["review_runtime"] = rt

    result = func(**kwargs)
    if result is not None:
        print(result)


def main(argv: list[str] | None = None):
    # Custom parsing: detect whether first positional arg is a function name or a task
    raw_args = argv if argv is not None else sys.argv[1:]

    # Extract global flags first
    provider = None
    model = None
    filtered = []
    i = 0
    while i < len(raw_args):
        if raw_args[i] == "--list":
            _list_functions()
            return
        elif raw_args[i] == "--help" or raw_args[i] == "-h":
            print("Usage: research-harness [OPTIONS] [TASK or FUNCTION ...]")
            print()
            print("  research-harness \"your task\"              Natural language task")
            print("  research-harness polish_rigorous --text .. Direct function call")
            print("  echo text | research-harness \"润色\"        Pipe + task")
            print("  echo text | research-harness polish_rigorous  Pipe + function")
            print()
            print("Options:")
            print("  --list              List all available functions")
            print("  --provider NAME     LLM provider (auto-detected if not set)")
            print("  --model NAME        Model name override")
            print("  -h, --help          Show this help")
            return
        elif raw_args[i] == "--provider" and i + 1 < len(raw_args):
            provider = raw_args[i + 1]
            i += 2
        elif raw_args[i] == "--model" and i + 1 < len(raw_args):
            model = raw_args[i + 1]
            i += 2
        else:
            filtered.append(raw_args[i])
            i += 1

    if not filtered:
        # No args — check stdin
        stdin_data = _read_stdin_if_available()
        if stdin_data:
            _run_task(stdin_data.strip(), provider=provider, model=model)
        else:
            main(["--help"])
        return

    first = filtered[0]

    if first in _REGISTRY:
        # Direct function call
        _run_function(first, filtered[1:], provider=provider, model=model)
    else:
        # Everything is a task description
        task = " ".join(filtered)
        _run_task(task, provider=provider, model=model)


if __name__ == "__main__":
    main()
