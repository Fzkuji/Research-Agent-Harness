"""
registry — single source of truth for all callable functions.

Two-level structure:
  STAGES — high-level research phases (LLM picks one)
  _ENTRIES — all functions with their stage membership (LLM picks within stage)

Lazy-loads functions to avoid importing 48+ modules at startup.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Optional


# ---------------------------------------------------------------------------
# Stages: name -> description (for top-level LLM decision)
# ---------------------------------------------------------------------------

STAGES: dict[str, str] = {
    "literature":    "Survey papers, search arXiv/Semantic Scholar, identify research gaps",
    "idea":          "Generate research ideas, check novelty, rank by promise, refine direction",
    "experiment":    "Design experiments, implement, run, monitor training",
    "writing":       "Write sections, polish, translate, compress/expand, figures, compile LaTeX",
    "review":        "Review paper, fix based on feedback, review-fix loop",
    "rebuttal":      "Parse reviewer comments, build strategy, draft rebuttal",
    "presentation":  "Generate slides, poster, speaker notes",
    "theory":        "Derive formulas, write proofs, plan ablations, grant proposals",
    "knowledge":     "Research wiki, meta-optimize harness",
    "project":       "Initialize project, run full pipeline",
}


# ---------------------------------------------------------------------------
# Registry: name -> (module_path, function_name, stage)
# ---------------------------------------------------------------------------

_ENTRIES: dict[str, tuple[str, str, str]] = {
    # Literature — single-step loop driven by run_literature; leaves used internally
    "run_literature":           ("research_harness.stages.literature", "run_literature", "literature"),
    "seed_surveys":             ("research_harness.stages.literature", "seed_surveys", "literature"),
    "extract_framework":        ("research_harness.stages.literature", "extract_framework", "literature"),
    "search_papers_for_topic":  ("research_harness.stages.literature", "search_papers_for_topic", "literature"),
    "annotate_papers":          ("research_harness.stages.literature", "annotate_papers", "literature"),
    "evolve_framework":         ("research_harness.stages.literature", "evolve_framework", "literature"),
    "synthesize_literature":    ("research_harness.stages.literature", "synthesize_literature", "literature"),
    # Legacy / complementary leaves (still available; run_literature does not chain them)
    "survey_topic":             ("research_harness.stages.literature", "survey_topic", "literature"),
    "identify_gaps":            ("research_harness.stages.literature", "identify_gaps", "literature"),
    "search_arxiv":             ("research_harness.stages.literature", "search_arxiv", "literature"),
    "search_semantic_scholar":  ("research_harness.stages.literature", "search_semantic_scholar", "literature"),
    "comprehensive_lit_review": ("research_harness.stages.literature", "comprehensive_lit_review", "literature"),
    # Idea — individual functions + orchestrator
    "generate_ideas":           ("research_harness.stages.idea", "generate_ideas", "idea"),
    "check_novelty":            ("research_harness.stages.idea", "check_novelty", "idea"),
    "rank_ideas":               ("research_harness.stages.idea", "rank_ideas", "idea"),
    "refine_research":          ("research_harness.stages.theory", "refine_research", "idea"),
    "run_idea":                 ("research_harness.stages.idea", "run_idea", "idea"),
    # Experiment — individual functions + orchestrator
    "design_experiments":       ("research_harness.stages.experiment", "design_experiments", "experiment"),
    "experiment_bridge":        ("research_harness.stages.experiment", "experiment_bridge", "experiment"),
    "run_experiment":           ("research_harness.stages.experiment", "run_experiment", "experiment"),
    "check_training":           ("research_harness.stages.experiment", "check_training", "experiment"),
    "plan_ablations":           ("research_harness.stages.theory", "plan_ablations", "experiment"),
    "run_experiments":          ("research_harness.stages.experiment", "run_experiments", "experiment"),
    # Writing
    "write_section":            ("research_harness.stages.writing", "write_section", "writing"),
    "polish_rigorous":          ("research_harness.stages.writing", "polish_rigorous", "writing"),
    "polish_natural":           ("research_harness.stages.writing", "polish_natural", "writing"),
    "compress_text":            ("research_harness.stages.writing", "compress_text", "writing"),
    "expand_text":              ("research_harness.stages.writing", "expand_text", "writing"),
    "check_logic":              ("research_harness.stages.writing", "check_logic", "writing"),
    "analyze_results":          ("research_harness.stages.writing", "analyze_results", "writing"),
    "results_to_claims":        ("research_harness.stages.writing", "results_to_claims", "writing"),
    "translate_zh2en":          ("research_harness.stages.writing", "translate_zh2en", "writing"),
    "translate_en2zh":          ("research_harness.stages.writing", "translate_en2zh", "writing"),
    "rewrite_zh":               ("research_harness.stages.writing", "rewrite_zh", "writing"),
    "polish_zh":                ("research_harness.stages.writing", "polish_zh", "writing"),
    "remove_ai_flavor_zh":      ("research_harness.stages.writing", "remove_ai_flavor_zh", "writing"),
    "generate_figure_caption":    ("research_harness.stages.writing", "generate_figure_caption", "writing"),
    "generate_table_caption":     ("research_harness.stages.writing", "generate_table_caption", "writing"),
    "recommend_visualization":    ("research_harness.stages.writing", "recommend_visualization", "writing"),
    "design_architecture_figure": ("research_harness.stages.writing", "design_architecture_figure", "writing"),
    "generate_paper_figures":     ("research_harness.stages.writing", "generate_paper_figures", "writing"),
    "generate_mermaid_diagram":   ("research_harness.stages.writing", "generate_mermaid_diagram", "writing"),
    "compile_paper":              ("research_harness.stages.writing", "compile_paper", "writing"),
    # Review — individual functions + orchestrators
    "review_paper":             ("research_harness.stages.review", "review_paper", "review"),
    "fix_paper":                ("research_harness.stages.review", "fix_paper", "review"),
    "review_loop":              ("research_harness.stages.review", "review_loop", "review"),
    "paper_improvement_loop":   ("research_harness.stages.review", "paper_improvement_loop", "review"),
    # Rebuttal
    "parse_reviews":            ("research_harness.stages.rebuttal", "parse_reviews", "rebuttal"),
    "build_rebuttal_strategy":  ("research_harness.stages.rebuttal", "build_rebuttal_strategy", "rebuttal"),
    "draft_rebuttal":           ("research_harness.stages.rebuttal", "draft_rebuttal", "rebuttal"),
    # Presentation
    "generate_slides":          ("research_harness.stages.presentation", "generate_slides", "presentation"),
    "generate_poster":          ("research_harness.stages.presentation", "generate_poster", "presentation"),
    "generate_speaker_notes":   ("research_harness.stages.presentation", "generate_speaker_notes", "presentation"),
    # Theory
    "derive_formula":           ("research_harness.stages.theory", "derive_formula", "theory"),
    "write_proof":              ("research_harness.stages.theory", "write_proof", "theory"),
    "write_grant_proposal":     ("research_harness.stages.theory", "write_grant_proposal", "theory"),
    # Knowledge & Meta
    "research_wiki":            ("research_harness.wiki.wiki_agent", "research_wiki", "knowledge"),
    "meta_optimize":            ("research_harness.stages.meta", "meta_optimize", "knowledge"),
    # Project
    "research_pipeline":        ("research_harness.pipeline", "research_pipeline", "project"),
    "init_research":            ("research_harness.stages.init", "init_research", "project"),
}

# Parameters auto-injected by the framework (hidden from LLM and CLI)
AUTO_PARAMS = {"runtime", "exec_runtime", "review_runtime"}

# Parameters hidden from LLM view (system-controlled knobs — iteration caps,
# retry limits, debugging switches). Unlike AUTO_PARAMS these are NOT
# auto-injected; orchestrators use their own defaults. Programmatic callers
# (pipeline.py, tests) can still pass them directly.
HIDDEN_PARAMS = {"max_iters"}


# ---------------------------------------------------------------------------
# Lazy loading
# ---------------------------------------------------------------------------

_cache: dict[str, callable] = {}


def get_function(name: str) -> Optional[callable]:
    """Lazily import and return a function by registry name."""
    if name in _cache:
        return _cache[name]
    entry = _ENTRIES.get(name)
    if entry is None:
        return None
    module_path, func_name, _ = entry
    mod = importlib.import_module(module_path)
    func = getattr(mod, func_name)
    _cache[name] = func
    return func


def get_signature(name: str) -> str:
    """Get function signature string, excluding auto-injected + hidden params."""
    func = get_function(name)
    if func is None:
        return f"{name}(?)"
    sig = inspect.signature(func)
    params = []
    for p in sig.parameters.values():
        if p.name in AUTO_PARAMS or p.name in HIDDEN_PARAMS:
            continue
        ann = p.annotation
        type_name = ann.__name__ if hasattr(ann, '__name__') else str(ann)
        params.append(f"{p.name}: {type_name}")
    return f"{name}({', '.join(params)})"


def get_user_params(func) -> dict[str, inspect.Parameter]:
    """Get function parameters excluding auto-injected ones."""
    sig = inspect.signature(func)
    return {
        name: param
        for name, param in sig.parameters.items()
        if name not in AUTO_PARAMS
    }


def get_stage(name: str) -> Optional[str]:
    """Get the stage a function belongs to."""
    entry = _ENTRIES.get(name)
    return entry[2] if entry else None


def all_names() -> list[str]:
    """Return all registered function names."""
    return list(_ENTRIES.keys())


def stage_functions(stage: str) -> list[str]:
    """Return all function names in a given stage."""
    return [name for name, (_, _, s) in _ENTRIES.items() if s == stage]


def build_stage_list() -> str:
    """Build a compact stage list for the top-level LLM decision."""
    lines = []
    for stage, desc in STAGES.items():
        count = len(stage_functions(stage))
        lines.append(f"  {stage} ({count} functions) — {desc}")
    return "\n".join(lines)


def build_stage_functions(stage: str) -> str:
    """Build a function list for a specific stage."""
    names = stage_functions(stage)
    if not names:
        return f"(no functions in stage '{stage}')"
    lines = [f"[{stage}] functions:"]
    for name in names:
        lines.append(f"  {get_signature(name)}")
    return "\n".join(lines)


def build_function_list() -> str:
    """Build full function list grouped by stage (for --list)."""
    lines = []
    for stage, desc in STAGES.items():
        names = stage_functions(stage)
        if not names:
            continue
        lines.append(f"\n[{stage}] — {desc}")
        for name in names:
            lines.append(f"  {get_signature(name)}")
    return "\n".join(lines)
