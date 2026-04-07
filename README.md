# 🔬 Research Agent Harness

Autonomous research agent: from topic to submission-ready paper.

Built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming) — Python controls the workflow, LLM reasons at each step via `@agentic_function` docstrings.

## 🚀 Quick Start

### 1. Install

**Via PyPI:**

```bash
pip install research-agent-harness
```

**Via Skills (Claude Code / Cursor):**

```bash
git clone https://github.com/Fzkuji/Research-Agent-Harness.git
mkdir -p ~/.claude/skills/
cp -r Research-Agent-Harness/skills/* ~/.claude/skills/
```

### 2. Set up LLM provider

Any one of:

```bash
# Claude Code CLI (recommended)
npm install -g @anthropic-ai/claude-code && claude login

# Or Anthropic API
export ANTHROPIC_API_KEY=sk-...

# Or OpenAI API
export OPENAI_API_KEY=sk-...
```

### 3. Use

**In Claude Code / Cursor** (via skills):

```
> /research-pipeline "factorized gap in discrete diffusion LMs"    # Full pipeline: literature → idea → experiment → paper
> /paper-write "NeurIPS"                                           # Write paper sections from outline
> /review-loop "paper/"                                            # Cross-model review until pass
> /rebuttal "paper/ + reviews" — venue: ICML, char limit: 5000    # Draft venue-compliant rebuttal
> /paper-slides "paper/" — talk_type: oral, minutes: 15            # Generate Beamer slides
> /paper-poster "paper/" — venue: NeurIPS                          # Generate conference poster
> /polish "paragraph text..."                                      # Polish English LaTeX
> /translate-zh2en "中文草稿..."                                    # Chinese → English LaTeX
> /check-logic "paper section..."                                  # Final logic check
> /analyze-results "experiment data..."                            # Data → LaTeX analysis
> /plan-ablations "method description..."                          # Design ablation studies
> /refine-research "vague research direction"                      # Refine → focused plan
```

**In Python** (via package):

```bash
# See all available functions
python -c "from research_harness import research; research()"

# Run the pipeline
agentic research "your topic" --venue NeurIPS
```

🗑️ **Uninstall skills:**

```bash
cd Research-Agent-Harness && ls skills/ | xargs -I{} rm -rf ~/.claude/skills/{}
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

## All Functions (36)

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

For tasks with multiple approaches (e.g. `polish_rigorous` vs `polish_natural`), the harness can run each and let a different LLM pick the best output. See `research_harness.evaluate.compete()`.

## Project Structure

```
research_harness/
├── __init__.py          # Entry point: research(), research_pipeline()
├── pipeline.py          # 8-stage orchestrator
├── evaluate.py          # Prompt competition between @agentic_functions
├── utils.py             # Shared utilities
└── stages/
    ├── init.py          # Project directory setup
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
