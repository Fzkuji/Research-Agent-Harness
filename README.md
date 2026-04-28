# Research Agent Harness

Autonomous research agent: from topic to submission-ready paper.

Built with [OpenProgram](https://github.com/Fzkuji/OpenProgram) (Agentic Programming paradigm) — Python controls the workflow, LLM reasons at each step via `@agentic_function` docstrings.

## Quick Start

### 1. Install

```bash
pip install research-agent-harness
```

<details>
<summary><b>Local development (editable)</b></summary>

Three-repo layout, `openprogram` first (this repo depends on it):

```bash
pip install -e ~/Documents/LLM\ Agent\ Harness/OpenProgram
pip install -e ~/Documents/Research-Agent-Harness     # this repo
```

`pip install -e` hard-codes absolute paths into `site-packages/*.pth`. If you rename any parent folder, `import research_harness` (or `openprogram`) will break with `ModuleNotFoundError` until you rerun `pip install -e .` from the new location. The OpenProgram symlink at `openprogram/programs/applications/Research-Agent-Harness` also points to an absolute path — recreate it after any move.

</details>


### 2. Set up LLM providers

```bash
# Executor: Claude Code CLI (recommended — full file system access)
npm install -g @anthropic-ai/claude-code && claude login

# Reviewer: Codex CLI (recommended — cross-model review with GPT)
npm install -g @openai/codex && codex auth login

# Or use API keys directly
export ANTHROPIC_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
```

### 3. Use

**CLI:**

```bash
# Basic: Claude does everything
research-harness "Survey recent work on LLM uncertainty"

# Cross-model review: Claude writes, GPT reviews (ARIS design)
research-harness "Review the paper at ./my-project/" \
    --provider claude-code \
    --review-provider codex

# List all available functions
research-harness --list
```

**In Python:**

```python
from research_harness.main import research_agent, _create_runtime

# Single model
rt = _create_runtime(provider="claude-code")
result = research_agent(task="Survey LLM uncertainty", runtime=rt)

# Cross-model review: Claude executor + Codex/GPT reviewer
exec_rt = _create_runtime(provider="claude-code")
review_rt = _create_runtime(provider="codex")
result = research_agent(
    task="Review the paper at ./my-project/ as EMNLP reviewer",
    runtime=exec_rt,
    review_runtime=review_rt,
)
```

**In Claude Code / Cursor (via skills):**

```
> /agentic-research "Survey recent work on LLM uncertainty and identify gaps"
> /agentic-research "Review paper/ as a NeurIPS reviewer with difficulty: nightmare"
> /agentic-research "Polish this paragraph for NeurIPS: <text>"
```

## Install as Claude Code / opencode skills

Two skills ship with this repo for paper review:

- **`paper-review`** — write a venue-format peer review from scratch using sentence skeletons drawn live from a corpus of ~500 GPTZero-verified human reviews (COLM / ICLR / NeurIPS / ICML, 2018-2025). Empirically 0% AI on GPTZero (ACM MM smoke test).
- **`humanize-paper-review`** — humanize an existing LLM-generated review draft via 2-stage redaction (extract structured judgment from draft, then re-generate prose from scratch). Preserves score / verdict / sub_scores verbatim, lands at 1% AI on GPTZero.

One-line install (Mac / Linux):
```bash
curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/install.py | python3
```

Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/install.py | python
```

The installer clones this repo to `~/.research-agent-harness`, symlinks the two skills into `~/.claude/skills/`, and adds the repo to `PYTHONPATH`. Customize via env vars:

```bash
AGENT_SKILL_DIR=~/.opencode/skills python install.py        # opencode
RESEARCH_HARNESS_DIR=/opt/rah AGENT_SKILL_DIR=~/my-prompts python install.py
```

Use after install:
```
> /paper-review my_paper.pdf venue="NeurIPS"
> /humanize-paper-review my_paper.pdf draft=existing_review.md venue="ACM Multimedia"
```

Upgrade later: `python ~/.research-agent-harness/install.py` (it does `git pull` + re-links).

## Architecture

### Two-Level Autonomous Loop

```
research_agent(task, runtime, review_runtime)
│
├── Level 1: _pick_stage(task, progress)
│   LLM sees 10 stages, picks the right one based on task + progress.
│
└── Level 2: _stage_step(stage, sub_task, context)
    LLM sees all functions in that stage, picks one to call.
    Prefers orchestrator functions (review_loop, run_literature, etc.)
    that chain multiple steps internally.
    Loops until stage_done or max steps reached.

→ Back to Level 1 with updated progress, until done or max stages.
```

**Key design:** Python controls the loop structure, LLM makes decisions at each step. Each `@agentic_function` calls `runtime.exec()` exactly once — the LLM reads the docstring and does the work.

### Registry

All 48+ functions are registered in `registry.py` with their stage membership. Functions are lazy-loaded. The dispatcher shows only functions in the current stage.

```python
STAGES = {
    "literature":   "Survey papers, search arXiv/Semantic Scholar, identify research gaps",
    "idea":         "Generate research ideas, check novelty, rank by promise",
    "experiment":   "Design experiments, implement, run, monitor training",
    "writing":      "Write sections, polish, translate, compress/expand, figures, compile LaTeX",
    "review":       "Review paper, fix based on feedback, review-fix loop",
    "rebuttal":     "Parse reviewer comments, build strategy, draft rebuttal",
    "presentation": "Generate slides, poster, speaker notes",
    "theory":       "Derive formulas, write proofs, plan ablations, grant proposals",
    "knowledge":    "Research wiki, meta-optimize harness",
    "project":      "Initialize project, run full pipeline",
}
```

### Cross-Model Review (ARIS Design)

Following [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep), the review system uses **two different models** — the reviewer (GPT via Codex) and the author (Claude) are adversarial by design.

```
review_loop(paper_dir, venue, exec_runtime=Claude, review_runtime=Codex/GPT)
│
├── lookup_venue_criteria(venue)         [GPT — query scoring rubric]
│
└── for round 1..4:                      [each round = new session]
    │
    ├── review_runtime.reset()           ← new session
    │
    ├── Phase A: review_paper()          [GPT reviews the paper]
    │   ├── medium:    curated context (15k tokens)
    │   ├── hard:      + reviewer memory + debate protocol
    │   └── nightmare: + full content (no truncation) + adversarial verification
    │
    ├── Phase B: Parse assessment        [extract score, verdict, weaknesses]
    │
    ├── Phase B.5: Reviewer Memory       [hard/nightmare — accumulate suspicions]
    │   In-memory string, passed to reviewer in next round's prompt.
    │   Reviewer checks if previous concerns were addressed or sidestepped.
    │
    ├── Phase B.6: Debate Protocol       [hard/nightmare — if weaknesses exist]
    │   ├── Author (Claude): rebut up to 3 weaknesses
    │   └── Reviewer (GPT): rule SUSTAINED / OVERRULED / PARTIALLY SUSTAINED
    │
    ├── Phase E: Save to AUTO_REVIEW.md  [cumulative log with full raw responses]
    │
    ├── Stop? score >= 6 or verdict contains "accept"/"ready" → return
    │
    ├── exec_runtime.reset()             ← new session
    └── Phase C: fix_paper()             [Claude fixes the paper]
```

**Difficulty levels (information control):**

| Level | Who controls what reviewer sees | Extra capabilities |
|-------|-------------------------------|-------------------|
| **medium** | **Author** curates 15k tokens for reviewer | Standard review |
| **hard** | **Author** curates 14k tokens, but reviewer has memory | Memory across rounds + debate protocol |
| **nightmare** | **Reviewer reads files independently** (author has zero info control) | Adversarial verification + independent file access |

The key design from ARIS: difficulty controls **information asymmetry**. In medium/hard, Claude decides what GPT sees. In nightmare, GPT reads the repo directly — Claude cannot hide anything.

**Providers:**

| Role | Recommended | Alternative |
|------|------------|------------|
| Executor (author) | `claude-code` (Claude Code CLI) | `anthropic` (API) |
| Reviewer | `codex` (Codex CLI, GPT, session continuity) | `openai` (API, stateless) |

### Runtime Providers

| Provider | CLI Flag | Session | File Access | Auth |
|----------|----------|---------|-------------|------|
| `claude-code` | `--provider claude-code` | Yes (reset per step) | Full file system | `claude login` |
| `codex` | `--provider codex` | Yes (auto thread ID) | Repo access | `codex auth login` |
| `openai` | `--provider openai` | No (stateless API) | None | `OPENAI_API_KEY` |
| `anthropic` | `--provider anthropic` | No (stateless API) | None | `ANTHROPIC_API_KEY` |

### Persistence & Tracing

- All leaf functions include a `# Persistence` prompt: the agent saves complete output to files and returns a summary.
- `AUTO_REVIEW.md` — cumulative review log with full raw reviewer responses, debate transcripts.
- Operation log (`--log path`) — append-only markdown log of all stage/step decisions.
- Results are saved to the **target project directory** (the agent infers the path from the task description).

## All Functions (48+)

### Literature & Search
| Function | Description |
|----------|-------------|
| `survey_topic` | Survey literature: find papers, organize by subtopic, note gaps |
| `identify_gaps` | Identify specific, actionable research gaps from a survey |
| `search_arxiv` | Search arXiv API for papers |
| `search_semantic_scholar` | Search Semantic Scholar API |
| `comprehensive_lit_review` | Full literature review with structured output |
| `run_literature` | **Orchestrator**: survey + gaps in one call |

### Idea Generation
| Function | Description |
|----------|-------------|
| `generate_ideas` | Generate research ideas from gaps |
| `check_novelty` | Check idea novelty against literature |
| `rank_ideas` | Rank ideas by feasibility and impact |
| `run_idea` | **Orchestrator**: generate + novelty check + rank |

### Experiment
| Function | Description |
|----------|-------------|
| `design_experiments` | Design experiment plan |
| `experiment_bridge` | Bridge from idea to executable experiment |
| `run_experiment` | Generate and run experiment code |
| `check_training` | Monitor training progress |
| `plan_ablations` | Design ablation studies |
| `run_experiments` | **Orchestrator**: design + run experiments |

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
| `review_paper` | Review paper against venue criteria |
| `fix_paper` | Fix paper based on review feedback |
| `lookup_venue_criteria` | Query venue-specific scoring rubric |
| `review_loop` | **Orchestrator**: full review-fix cycle (medium/hard/nightmare) |
| `paper_improvement_loop` | **Orchestrator**: writing quality improvement (2 rounds) |
| `parse_reviews` | Parse reviewer comments into structured issues |
| `build_rebuttal_strategy` | Build response strategy per weakness |
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
| `research_wiki` | Persistent knowledge base |
| `meta_optimize` | Analyze usage, propose harness improvements |

## Project Structure

```
Research-Agent-Harness/
├── SKILL.md                     # Skill definition for IDE discovery
├── research_harness/
│   ├── main.py                  # Two-level loop + CLI entry point
│   ├── registry.py              # Function registry (lazy loading, stage mapping)
│   ├── log.py                   # Append-only operation log
│   ├── pipeline.py              # 8-stage orchestrator
│   ├── utils.py                 # Shared utilities (parse_json, etc.)
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
├── tests/
│   ├── test_main.py             # Two-level loop, CLI, operation log
│   ├── test_registry.py         # Registry, stage mapping, orchestrators
│   ├── test_log.py              # Operation log
│   ├── test_e2e.py              # End-to-end against real projects
│   └── conftest.py              # MockRuntime, fixtures
├── skills/                      # SKILL.md files for IDE discovery
└── templates/                   # Structured input/output templates
```

## Design Principles

1. **Two-level autonomous loop** — Level 1 picks the research stage, Level 2 dispatches to functions within that stage. Python controls the loop, LLM makes decisions.
2. **Prompt = docstring** — no external prompt files; the function's docstring IS the instruction to the LLM.
3. **Cross-model review (ARIS design)** — executor (Claude) and reviewer (GPT/Codex) are different models to avoid self-play blind spots. 3 difficulty levels with reviewer memory and debate protocol.
4. **Agent saves files** — leaf functions prompt the agent to save complete output. No Python `open().write()` in the hot path. The agent decides where to save based on context.
5. **Orchestrators for complete workflows** — `review_loop`, `run_literature`, `run_idea`, `run_experiments` chain multiple steps. The dispatcher prefers these over individual leaf functions.
6. **Everything leaves a trace** — AUTO_REVIEW.md, operation logs, file saves. No work is lost.

## References

- [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) — autonomous research pipeline with cross-model review (primary reference for review loop design)
- [awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing) — battle-tested writing prompts from top research labs
- [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming) — the runtime framework (`@agentic_function`, `Runtime.exec()`)
