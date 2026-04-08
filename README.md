# Agentic Research

Autonomous research agent: from topic to submission-ready paper.

Built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming) — Python controls the workflow, LLM reasons at each step via `@agentic_function` docstrings.

## Quick Start

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
> /agentic-research "Survey recent work on LLM uncertainty and identify gaps"
> /agentic-research "Generate 5 research ideas from related_work/gaps.md"
> /agentic-research "Write the introduction section based on outline/outline.md"
> /agentic-research "Review paper/ as a NeurIPS reviewer with difficulty: nightmare"
> /agentic-research "Polish this paragraph for NeurIPS: <text>"
> /agentic-research "Run the full pipeline for topic 'LLM Uncertainty', venue NeurIPS"
```

**In Python** (via package):

```python
# See all available functions
from research_harness import show_capabilities
show_capabilities()

# LLM entry point (used by Agentic-Programming runtime)
from research_harness import agentic_research
result = agentic_research(task="your task", runtime=my_runtime)

# Or run the pipeline programmatically
from research_harness import research_pipeline
result = research_pipeline(project_dir="...", topic="...", exec_runtime=rt)
```

## Pipeline

```
init -> literature -> idea -> experiment -> analysis -> writing -> review -> submission
```

| Stage | What it does |
|-------|-------------|
| **init** | Create project directory, LaTeX scaffold, outline template |
| **literature** | Survey related papers, identify research gaps |
| **idea** | Generate ideas, check novelty, rank by feasibility & impact |
| **experiment** | Design experiments, generate code, run & monitor |
| **analysis** | Analyze results, generate LaTeX analysis paragraphs |
| **writing** | Write paper sections, polish, translate, remove AI flavor |
| **review** | Cross-model review loop (3 difficulty levels: medium/hard/nightmare) |
| **submission** | Pre-submission checklist (anonymity, format, references) |

## All Functions (48+)

### Writing (English)
| Function | Description |
|----------|-------------|
| `write_section` | Write a paper section from outline + notes |
| `polish_rigorous` | Deep polish for academic rigor |
| `polish_natural` | Polish for naturalness, remove AI patterns |
| `translate_zh2en` | Chinese draft -> English LaTeX |
| `translate_en2zh` | English LaTeX -> Chinese text |
| `compress_text` | Reduce word count by 5-15 words |
| `expand_text` | Add 5-15 words with deeper logic |
| `check_logic` | Final check for fatal errors only |
| `analyze_results` | Experimental data -> LaTeX analysis |
| `results_to_claims` | Judge what claims results support |

### Writing (Chinese)
| Function | Description |
|----------|-------------|
| `rewrite_zh` | Rewrite fragmented draft |
| `polish_zh` | Polish Chinese paper text |
| `remove_ai_flavor_zh` | Remove AI patterns from Chinese |

### Figures & Tables
| Function | Description |
|----------|-------------|
| `generate_figure_caption` | Generate English figure caption |
| `generate_table_caption` | Generate English table caption |
| `recommend_visualization` | Recommend chart type for data |
| `design_architecture_figure` | Design framework/architecture diagram |
| `generate_paper_figures` | Generate matplotlib plots |
| `generate_mermaid_diagram` | Generate Mermaid diagram code |
| `compile_paper` | Compile LaTeX -> PDF, fix errors |

### Review & Rebuttal
| Function | Description |
|----------|-------------|
| `review_paper` | Review paper (as reviewer model) |
| `fix_paper` | Fix paper based on review feedback |
| `review_loop` | Full review-fix cycle (medium/hard/nightmare) |
| `paper_improvement_loop` | Writing quality improvement loop |
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
| `refine_research` | Refine vague direction -> focused plan |
| `write_grant_proposal` | Draft grant proposal (NSFC/NSF/ERC/...) |

### Knowledge & Meta
| Function | Description |
|----------|-------------|
| `research_wiki` | Persistent knowledge base (papers/ideas/experiments/claims) |
| `meta_optimize` | Analyze usage, propose harness improvements |
| `compete` | Prompt competition between functions |

## Project Structure

```
Research-Agent-Harness/
├── SKILL.md                     # Skill definition for IDE discovery
├── research_harness/
│   ├── __init__.py              # Exports: agentic_research, research_pipeline, etc.
│   ├── agent.py                 # Entry point: agentic_research() @agentic_function
│   ├── pipeline.py              # 8-stage orchestrator
│   ├── evaluate.py              # Prompt competition
│   ├── utils.py                 # Shared utilities
│   ├── references/              # Writing principles, citation discipline, venue checklists
│   ├── wiki/                    # Research Wiki (persistent knowledge base)
│   └── stages/
│       ├── init.py              # Project directory setup
│       ├── literature/          # survey_topic, identify_gaps, search_arxiv, ...
│       ├── idea/                # generate_ideas, check_novelty, rank_ideas
│       ├── experiment/          # design_experiments, run_experiment, check_training, ...
│       ├── writing/             # 20 functions: write/polish/translate/analyze/figures
│       ├── review/              # review_paper, fix_paper, review_loop (3 levels), debate
│       ├── rebuttal/            # parse_reviews, build_strategy, draft_rebuttal
│       ├── presentation/        # generate_slides, generate_poster, speaker_notes
│       ├── theory/              # derive_formula, write_proof, plan_ablations, ...
│       ├── submission/          # check_submission
│       └── meta/                # meta_optimize
├── skills/                      # SKILL.md files for IDE discovery
│   ├── agentic-research/        # Our entry point skill
│   ├── 20-ml-paper-writing/     # Third-party
│   ├── humanizer/               # Third-party
│   ├── docx/                    # Third-party
│   ├── doc-coauthoring/         # Third-party
│   └── canvas-design/           # Third-party
└── templates/                   # Structured input/output templates
    ├── RESEARCH_BRIEF_TEMPLATE.md
    ├── RESEARCH_CONTRACT_TEMPLATE.md
    ├── EXPERIMENT_PLAN_TEMPLATE.md
    ├── NARRATIVE_REPORT_TEMPLATE.md
    ├── PAPER_PLAN_TEMPLATE.md
    ├── IDEA_CANDIDATES_TEMPLATE.md
    ├── EXPERIMENT_LOG_TEMPLATE.md
    └── FINDINGS_TEMPLATE.md
```

## Design Principles

1. **Python controls flow, LLM reasons** — workflow is deterministic Python; each step's intelligence comes from `@agentic_function` docstrings
2. **Prompt = docstring** — no external prompt files; the function's docstring IS the instruction to the LLM
3. **Single entry point** — `agentic_research()` reads its docstring listing all capabilities; the LLM decides what to call
4. **Cross-model review** — executor and reviewer use different LLMs to avoid self-play blind spots
5. **3 review difficulty levels** — medium (standard), hard (+reviewer memory, +debate), nightmare (+adversarial verification)
6. **Prompt competition** — for tasks with multiple approaches, generate from each and let another LLM pick the best
7. **Stage independence** — run any stage alone or chain them into a pipeline

## References

Prompt engineering informed by:
- [awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing) — battle-tested writing prompts from top research labs
- [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) — autonomous research pipeline with cross-model review
