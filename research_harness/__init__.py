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
    """Print all available research functions and pipeline stages."""
    print("🔬 Research Agent Harness")
    print("=" * 60)

    print("\nPipeline stages:")
    for i, (s, d) in enumerate({
        "init":       "Create project structure, LaTeX scaffold, outline",
        "literature": "Survey papers, identify research gaps",
        "idea":       "Generate ideas, check novelty, rank",
        "experiment": "Design experiments, generate code, run & monitor",
        "analysis":   "Analyze results → LaTeX paragraphs",
        "writing":    "Write sections, polish, translate, de-AI",
        "review":     "Cross-model review loop until pass",
        "submission": "Pre-submission checklist",
    }.items()):
        print(f"  {i}. {s:12s} — {d}")

    print("\nWriting (English):")
    for n, d in {
        "write_section":    "Write a paper section from outline + notes",
        "polish_rigorous":  "Deep polish for academic rigor",
        "polish_natural":   "Polish for naturalness, remove AI patterns",
        "translate_zh2en":  "Chinese draft → English LaTeX",
        "translate_en2zh":  "English LaTeX → Chinese text",
        "compress_text":    "Reduce word count by 5-15 words",
        "expand_text":      "Add 5-15 words with deeper logic",
        "check_logic":      "Final check for fatal errors only",
        "analyze_results":  "Experimental data → LaTeX analysis",
        "results_to_claims":"Judge what claims results support",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nWriting (Chinese 中文):")
    for n, d in {
        "rewrite_zh":         "中转中 — rewrite fragmented draft",
        "polish_zh":          "表达润色 — polish Chinese paper text",
        "remove_ai_flavor_zh":"去AI味 — remove AI patterns from Chinese",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nFigures, Tables & Diagrams:")
    for n, d in {
        "generate_figure_caption":    "Generate English figure caption",
        "generate_table_caption":     "Generate English table caption",
        "recommend_visualization":    "Recommend chart type for data",
        "design_architecture_figure": "Design framework/architecture diagram",
        "generate_paper_figures":     "Generate matplotlib plots from data",
        "generate_mermaid_diagram":   "Generate Mermaid flowchart/diagram",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nCompilation:")
    for n, d in {
        "compile_paper": "Compile LaTeX → PDF, fix errors",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nReview & Rebuttal:")
    for n, d in {
        "review_paper":              "Review paper (as reviewer model)",
        "fix_paper":                 "Fix paper based on review feedback",
        "review_loop":               "Full review-fix cycle until pass",
        "paper_improvement_loop":    "Writing quality improvement loop",
        "parse_reviews":             "Parse reviewer comments into issues",
        "build_rebuttal_strategy":   "Build response strategy",
        "draft_rebuttal":            "Draft venue-compliant rebuttal",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nPresentation:")
    for n, d in {
        "generate_slides":        "Beamer slides for conference talk",
        "generate_poster":        "LaTeX poster for poster session",
        "generate_speaker_notes": "Speaker notes + Q&A prep",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nTheory & Planning:")
    for n, d in {
        "derive_formula":       "Derive formulas from scattered notes",
        "write_proof":          "Write rigorous mathematical proof",
        "plan_ablations":       "Design ablation studies",
        "refine_research":      "Refine vague direction → focused plan",
        "write_grant_proposal": "Draft grant proposal (NSFC/NSF/ERC/...)",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nLiterature & Search:")
    for n, d in {
        "survey_topic":              "Literature survey for a topic",
        "identify_gaps":             "Find research gaps from survey",
        "search_arxiv":              "Search arXiv for papers",
        "search_semantic_scholar":   "Search Semantic Scholar (published venues)",
        "comprehensive_lit_review":  "Deep related work section (LaTeX)",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nIdea & Experiment:")
    for n, d in {
        "generate_ideas":     "Generate ideas from gaps",
        "check_novelty":      "Check if idea is novel",
        "rank_ideas":         "Rank ideas by promise",
        "design_experiments": "Design experiment plan",
        "experiment_bridge":  "Implement plan → running code",
        "run_experiment":     "Execute one experiment step",
        "check_training":     "Check training logs for issues",
        "check_submission":   "Pre-submission checklist",
    }.items():
        print(f"  {n:28s} — {d}")

    print("\nUtilities:")
    print(f"  {'compete':28s} — Prompt competition between functions")
    print(f"  {'init_research':28s} — Initialize project directory")

    print("\nUsage:")
    print('  from research_harness import research_pipeline')
    print('  result = research_pipeline(project_dir="...", topic="...", exec_runtime=rt)')


__all__ = ["research", "research_pipeline", "compete", "STAGES"]
