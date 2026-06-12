---
name: agentic-research
description: "Autonomous research agent: literature, ideas, experiments, writing, review, rebuttal, presentation, theory. Triggers: 'research', 'write paper', 'survey', 'polish', 'translate', 'review', 'rebuttal', 'slides', 'poster', '写论文', '文献调研', '润色', '翻译', '去AI味', '审稿'."
---

# Agentic Research

Autonomous research agent built with [OpenProgram](https://github.com/Fzkuji/OpenProgram) (Agentic Programming paradigm).

Two-level autonomous loop: Level 1 picks a research stage (literature, writing, review, ...), Level 2 dispatches to functions within that stage. Cross-model review uses GPT (via Codex) as reviewer and Claude as author.

## Usage

```
/agentic-research "<your task>"
```

Single entry point — the agent reads your task and autonomously decides which functions to call.

```
/agentic-research "Survey recent work on LLM uncertainty"
/agentic-research "Polish this paragraph for NeurIPS: <text>"
/agentic-research "翻译这段中文为英文LaTeX: <中文草稿>"
/agentic-research "Review paper/ as a NeurIPS reviewer"
/agentic-research "Run the full pipeline for topic 'LLM Uncertainty', venue NeurIPS"
```

## CLI

```bash
# Basic usage (--work-dir is required to run a task)
research-harness --work-dir /abs/path "your task"
research-harness --list                              # list all functions

# Cross-model review: Claude writes, GPT reviews (ARIS design)
research-harness --work-dir /abs/path "Review the paper at ./project/" \
    --provider claude-code \
    --review-provider openai-codex

# Custom models
research-harness --work-dir /abs/path "Survey LLM uncertainty" \
    --provider openai --model gpt-4o \
    --review-provider openai-codex

# Operation log is written automatically to <work-dir>/OPERATION_LOG.md
```

## Python

```python
from research_harness.main import research_agent
from openprogram.providers import create_runtime

# Single model
rt = create_runtime(provider="claude-code")
rt.set_workdir("/abs/path/to/work-dir")
result = research_agent(task="Survey LLM uncertainty", runtime=rt)

# Cross-model review
exec_rt = create_runtime(provider="claude-code")
exec_rt.set_workdir("/abs/path/to/work-dir")
review_rt = create_runtime(provider="openai-codex")
review_rt.set_workdir("/abs/path/to/work-dir")
result = research_agent(
    task="Review the paper at ./project/ as EMNLP reviewer",
    runtime=exec_rt,
    review_runtime=review_rt,
)
```
