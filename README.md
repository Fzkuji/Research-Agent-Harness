# 🔬 Research Agent Harness

Autonomous research agent: from topic to submission-ready paper.

Built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming) — Python controls the workflow, LLM reasons at each step via `@agentic_function` docstrings.

## Pipeline

```
init → literature → idea → experiment → analysis → writing → review → submission
```

| Stage | What it does |
|-------|-------------|
| **init** | Create project directory structure, LaTeX scaffold, outline template |
| **literature** | Survey related papers, identify research gaps |
| **idea** | Generate ideas, check novelty, rank by feasibility & impact |
| **experiment** | Design experiments, generate code, run & monitor |
| **analysis** | Analyze results, generate LaTeX analysis paragraphs |
| **writing** | Write paper sections, polish, translate, remove AI flavor |
| **review** | Cross-model review loop (executor + reviewer, different LLMs) |
| **submission** | Pre-submission checklist (anonymity, format, references) |

## Quick Start

```bash
pip install agentic-programming
```

```python
from research_harness import research_pipeline

# Full pipeline
result = research_pipeline(
    project_dir="~/research/LLM Uncertainty",
    topic="Uncertainty quantification in LLMs",
    venue="NeurIPS",
    exec_runtime=claude_runtime,
    review_runtime=gpt_runtime,  # different model for review
)

# Just writing + review
result = research_pipeline(
    project_dir="~/research/LLM Uncertainty",
    stages=["writing", "review"],
    exec_runtime=claude_runtime,
)

# Start from a specific stage
result = research_pipeline(
    project_dir="~/research/LLM Uncertainty",
    start_from="analysis",
    exec_runtime=claude_runtime,
)
```

## Individual Functions

Every function's docstring IS the prompt. No external prompt files.

### Writing

```python
from research_harness.stages.writing import (
    write_section,       # Write a paper section from outline + notes
    polish_rigorous,     # Polish for academic rigor (top-venue standard)
    polish_natural,      # Polish for naturalness (remove AI patterns)
    translate_zh2en,     # Chinese draft → English LaTeX
    translate_en2zh,     # English LaTeX → Chinese text
    compress_text,       # Reduce word count by 5-15 words
    expand_text,         # Add 5-15 words with deeper logic
    check_logic,         # Final check for fatal errors only
    analyze_results,     # Experimental data → LaTeX analysis paragraphs
)
```

### Review (Cross-Model)

```python
from research_harness.stages.review import review_loop

# Claude writes, GPT reviews — avoids self-play blind spots
result = review_loop(
    paper_dir="~/research/project/paper",
    venue="NeurIPS",
    exec_runtime=claude_runtime,    # fixes paper
    review_runtime=gpt_runtime,     # reviews paper
    max_rounds=4,
    pass_threshold=7,               # score >= 7/10 to pass
)
```

### Prompt Competition

When multiple approaches exist for the same task, compete them:

```python
from research_harness.evaluate import compete
from research_harness.stages.writing import polish_rigorous, polish_natural

best = compete(
    functions=[polish_rigorous, polish_natural],
    kwargs={"text": latex_text, "runtime": exec_runtime},
    eval_runtime=gpt_runtime,  # different model evaluates
    task="Polish LaTeX for NeurIPS",
)
print(best["winner_name"], best["reasoning"])
```

## Project Structure

```
research_harness/
├── __init__.py          # Entry point: research(), research_pipeline()
├── pipeline.py          # 8-stage orchestrator
├── evaluate.py          # Prompt competition between @agentic_functions
└── stages/
    ├── literature.py    # survey_topic, identify_gaps
    ├── idea.py          # generate_ideas, check_novelty, rank_ideas
    ├── experiment.py    # design_experiments, run_experiment, check_training
    ├── writing.py       # write/polish/translate/analyze (9 functions)
    ├── review.py        # review_paper, fix_paper, review_loop
    └── submission.py    # check_submission
```

## Design Principles

1. **Python controls flow, LLM reasons** — workflow is deterministic Python; each step's intelligence comes from `@agentic_function` docstrings
2. **Prompt = docstring** — no external prompt files; the function's docstring IS the instruction to the LLM
3. **Cross-model review** — executor and reviewer use different LLMs to avoid self-play blind spots
4. **Prompt competition** — for tasks with multiple approaches, generate from each and let another LLM pick the best
5. **Stage independence** — run any stage alone or chain them into a pipeline

## References

Prompt engineering informed by:
- [awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing) — battle-tested writing prompts from top research labs
- [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) — autonomous research pipeline with cross-model review
