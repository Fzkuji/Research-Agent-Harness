# 🔬 Research Agent Harness

Autonomous research agent: from topic to submission-ready paper.

Built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming) — Python controls the workflow, LLM reasons at each step via `@agentic_function` docstrings.

## Quick Start

### Option 1: As a Python package

```bash
# 1. Install
git clone https://github.com/Fzkuji/Research-Agent-Harness.git
cd Research-Agent-Harness
pip install -e .

# 2. Make sure you have an LLM provider available
# Claude Code CLI (recommended):
npm install -g @anthropic-ai/claude-code && claude login
# Or set API key:
export ANTHROPIC_API_KEY=sk-...
# Or OpenAI:
export OPENAI_API_KEY=sk-...

# 3. Use in Python
python -c "from research_harness import research; research()"
```

```python
from agentic import create_runtime
from research_harness import research_pipeline

runtime = create_runtime()  # auto-detects your LLM provider

# Initialize a research project
from research_harness.stages.init import init_research
init_research(name="LLM Uncertainty", venue="NeurIPS", base_dir="~/research")

# Run the full pipeline
result = research_pipeline(
    project_dir="~/research/LLM Uncertainty",
    topic="Uncertainty quantification in LLMs",
    venue="NeurIPS",
    exec_runtime=runtime,
)

# Or run individual functions
from research_harness.stages.writing import polish_rigorous
polished = polish_rigorous(text="We propose a method...", runtime=runtime)
```

### Option 2: As Claude Code / Cursor skills

Copy the `skills/` directory into your project's `.claude/skills/` or Cursor skills folder:

```bash
# For Claude Code
cp -r skills/* /path/to/your/project/.claude/skills/

# Then use in Claude Code:
# /research-pipeline "your research topic"
# /paper-write "NeurIPS"
# /review-loop "paper/"
# /rebuttal "paper/ + reviews"
```

### Option 3: Just the functions

```python
# Pick any function you need — each one works standalone
from agentic import create_runtime
runtime = create_runtime()

# Polish English text
from research_harness.stages.writing import polish_rigorous
result = polish_rigorous(text="...", runtime=runtime)

# Translate Chinese → English
from research_harness.stages.writing import translate_zh2en
result = translate_zh2en(text="我们提出了一种方法...", runtime=runtime)

# Generate figure caption
from research_harness.stages.writing import generate_figure_caption
caption = generate_figure_caption(description="性能对比柱状图", runtime=runtime)

# Review paper with different model
from research_harness.stages.review import review_loop
result = review_loop(
    paper_dir="paper/",
    venue="NeurIPS",
    exec_runtime=claude_runtime,
    review_runtime=gpt_runtime,
)
```

## Pipeline

```
init → literature → idea → experiment → analysis → writing → review → submission
```

| Stage | What it does |
|-------|-------------|
| **init** | Create project directory, LaTeX scaffold, outline template |
| **literature** | Survey related papers, identify research gaps |
| **idea** | Generate ideas, check novelty, rank by feasibility & impact |
| **experiment** | Design experiments, generate code, run & monitor |
| **analysis** | Analyze results, generate LaTeX analysis paragraphs |
| **writing** | Write paper sections, polish, translate, remove AI flavor |
| **review** | Cross-model review loop (executor + reviewer, different LLMs) |
| **submission** | Pre-submission checklist (anonymity, format, references) |

Run the full pipeline, specific stages, or start from any point:

```python
# Full pipeline
research_pipeline(project_dir="...", topic="...", exec_runtime=rt)

# Just writing + review
research_pipeline(project_dir="...", stages=["writing", "review"], exec_runtime=rt)

# Start from analysis onwards
research_pipeline(project_dir="...", start_from="analysis", exec_runtime=rt)
```

## All Functions

Call `research()` to see everything:

```python
from research_harness import research
research()
```

### Writing (English)
| Function | Description |
|----------|-------------|
| `write_section` | Write a paper section from outline + notes |
| `polish_rigorous` | Deep polish for academic rigor |
| `polish_natural` | Polish for naturalness, remove AI patterns |
| `translate_zh2en` | Chinese draft → English LaTeX |
| `translate_en2zh` | English LaTeX → Chinese text |
| `compress_text` | Reduce word count by 5-15 words |
| `expand_text` | Add 5-15 words with deeper logic |
| `check_logic` | Final check for fatal errors only |
| `analyze_results` | Experimental data → LaTeX analysis |
| `results_to_claims` | Judge what claims results support |

### Writing (Chinese 中文)
| Function | Description |
|----------|-------------|
| `rewrite_zh` | 中转中 — rewrite fragmented draft |
| `polish_zh` | 表达润色 — polish Chinese paper text |
| `remove_ai_flavor_zh` | 去AI味 — remove AI patterns from Chinese |

### Figures & Tables
| Function | Description |
|----------|-------------|
| `generate_figure_caption` | Generate English figure caption |
| `generate_table_caption` | Generate English table caption |
| `recommend_visualization` | Recommend chart type for data |
| `design_architecture_figure` | Design framework/architecture diagram |

### Review & Rebuttal
| Function | Description |
|----------|-------------|
| `review_paper` | Review paper (as reviewer model) |
| `fix_paper` | Fix paper based on review feedback |
| `review_loop` | Full review-fix cycle until pass |
| `parse_reviews` | Parse reviewer comments into issues |
| `build_rebuttal_strategy` | Build response strategy |
| `draft_rebuttal` | Draft venue-compliant rebuttal |

### Presentation
| Function | Description |
|----------|-------------|
| `generate_slides` | Beamer slides for conference talk |
| `generate_poster` | LaTeX poster for poster session |
| `generate_speaker_notes` | Speaker notes + Q&A prep |

### Theory & Planning
| Function | Description |
|----------|-------------|
| `derive_formula` | Derive formulas from scattered notes |
| `write_proof` | Write rigorous mathematical proof |
| `plan_ablations` | Design ablation studies |
| `refine_research` | Refine vague direction → focused plan |

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
├── utils.py             # Shared utilities (parse_json)
└── stages/
    ├── init.py          # init_research — project directory setup
    ├── literature.py    # survey_topic, identify_gaps
    ├── idea.py          # generate_ideas, check_novelty, rank_ideas
    ├── experiment.py    # design_experiments, run_experiment, check_training
    ├── writing.py       # 17 functions: write/polish/translate/analyze/figures
    ├── review.py        # review_paper, fix_paper, review_loop
    ├── rebuttal.py      # parse_reviews, build_strategy, draft_rebuttal
    ├── presentation.py  # generate_slides, generate_poster, speaker_notes
    ├── theory.py        # derive_formula, write_proof, plan_ablations
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
