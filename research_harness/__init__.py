"""
Research Agent Harness — autonomous research from topic to submission.

Built on Agentic Programming. Python controls flow, LLM reasons via docstrings.

Quick start:
    from research_harness import research

    research()  # prints all available functions and stages
"""

from research_harness.pipeline import research_pipeline, STAGES
from research_harness.evaluate import compete


def research():
    """Print all available research functions and pipeline stages.

    Call this to see everything the harness can do.
    """
    print("🔬 Research Agent Harness")
    print("=" * 60)
    print()

    print("Pipeline stages:")
    stage_desc = {
        "init":       "Create project structure, LaTeX scaffold, outline",
        "literature": "Survey papers, identify research gaps",
        "idea":       "Generate ideas, check novelty, rank",
        "experiment": "Design experiments, generate code, run & monitor",
        "analysis":   "Analyze results → LaTeX paragraphs",
        "writing":    "Write sections, polish, translate, de-AI",
        "review":     "Cross-model review loop until pass",
        "submission": "Pre-submission checklist",
    }
    for i, s in enumerate(STAGES):
        print(f"  {i}. {s:12s} — {stage_desc.get(s, '')}")

    print()
    print("Writing functions:")
    writing_fns = {
        "write_section":    "Write a paper section from outline + notes",
        "polish_rigorous":  "Deep polish for academic rigor",
        "polish_natural":   "Polish for naturalness, remove AI patterns",
        "translate_zh2en":  "Chinese draft → English LaTeX",
        "translate_en2zh":  "English LaTeX → Chinese text",
        "compress_text":    "Reduce word count by 5-15 words",
        "expand_text":      "Add 5-15 words with deeper logic",
        "check_logic":      "Final check for fatal errors only",
        "analyze_results":  "Experimental data → LaTeX analysis",
    }
    for name, desc in writing_fns.items():
        print(f"  {name:20s} — {desc}")

    print()
    print("Review functions:")
    review_fns = {
        "review_paper":  "Review paper (as reviewer model)",
        "fix_paper":     "Fix paper based on review feedback",
        "review_loop":   "Full review-fix cycle until pass",
    }
    for name, desc in review_fns.items():
        print(f"  {name:20s} — {desc}")

    print()
    print("Research functions:")
    research_fns = {
        "survey_topic":       "Literature survey for a topic",
        "identify_gaps":      "Find research gaps from survey",
        "generate_ideas":     "Generate ideas from gaps",
        "check_novelty":      "Check if idea is novel",
        "rank_ideas":         "Rank ideas by promise",
        "design_experiments": "Design experiment plan",
        "run_experiment":     "Execute one experiment step",
        "check_training":     "Check training logs for issues",
        "check_submission":   "Pre-submission checklist",
    }
    for name, desc in research_fns.items():
        print(f"  {name:20s} — {desc}")

    print()
    print("Utilities:")
    print(f"  {'compete':20s} — Run prompt competition between functions")
    print(f"  {'init_research':20s} — Initialize project directory structure")

    print()
    print("Usage:")
    print('  from research_harness import research_pipeline')
    print('  result = research_pipeline(')
    print('      project_dir="~/research/My Project",')
    print('      topic="my research topic",')
    print('      venue="NeurIPS",')
    print('      exec_runtime=runtime,')
    print('  )')


__all__ = ["research", "research_pipeline", "compete", "STAGES"]
