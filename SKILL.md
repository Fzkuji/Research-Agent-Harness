---
name: agentic-research
description: "Autonomous research agent: literature, ideas, experiments, writing, review, rebuttal, presentation, theory. Triggers: 'research', 'write paper', 'survey', 'polish', 'translate', 'review', 'rebuttal', 'slides', 'poster', '写论文', '文献调研', '润色', '翻译', '去AI味', '审稿'."
---

# Agentic Research

Autonomous research agent built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming).

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
research-harness "your task"
research-harness --list                  # list all functions
research-harness --provider codex "task" # choose provider
echo "text" | research-harness "润色"     # pipe input
```

## Python

```python
from research_harness import research_agent

result = research_agent(task="Survey LLM uncertainty", runtime=my_runtime)
```
