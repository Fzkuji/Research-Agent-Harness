---
name: research
description: "Autonomous research agent: literature survey, idea generation, experiments, paper writing, cross-model review, rebuttal, presentation. Triggers: 'research', 'write paper', 'survey literature', 'generate ideas', 'run experiments', 'review paper', 'polish', 'translate', 'rebuttal', 'make slides', 'make poster', 'ablation', 'derive formula', 'write proof', 'grant proposal', '写论文', '文献调研', '润色', '翻译', '去AI味', '审稿', '实验分析'."
---

# Research Agent Harness

Autonomous research agent built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming).

## Usage

```
/research "<your task>"
```

This single entry point covers the entire research lifecycle. The agent reads your task and decides which functions to call. Examples:

```
/research "Survey recent work on uncertainty quantification in LLMs and identify research gaps"
/research "Generate 5 research ideas based on the gaps in related_work/gaps.md"
/research "Design experiments for the top-ranked idea in IDEA_REPORT.md"
/research "Write the introduction section based on outline/outline.md"
/research "Polish this paragraph for NeurIPS: <text>"
/research "翻译这段中文为英文LaTeX: <中文草稿>"
/research "Review paper/ as a NeurIPS reviewer and iterate until score >= 7"
/research "Parse these reviewer comments and draft an ICML rebuttal within 5000 chars: <reviews>"
/research "Generate Beamer slides for a 15-minute oral talk from paper/"
/research "Derive the gradient formula from these scattered notes: <notes>"
/research "Run the full pipeline for topic 'LLM Uncertainty', venue NeurIPS"
```

## Available Functions

See the full list by calling `research()` in Python, or read the `research` function's docstring in `research_harness/main.py`.

**Pipeline**: init → literature → idea → experiment → analysis → writing → review → submission

**Writing**: write_section, polish (rigorous/natural), translate (zh↔en), compress, expand, check_logic, analyze_results, results_to_claims, 中转中, 表达润色, 去AI味

**Figures**: figure/table captions, visualization recommendations, architecture diagrams, matplotlib plots, mermaid diagrams, LaTeX compilation

**Review**: cross-model review loop, paper improvement loop, parse reviews, rebuttal strategy, draft rebuttal

**Presentation**: Beamer slides, conference poster, speaker notes

**Theory**: formula derivation, proof writing, ablation planning, research refinement, grant proposals (NSFC/NSF/ERC/...)

**Search**: arXiv, Semantic Scholar, comprehensive literature review
