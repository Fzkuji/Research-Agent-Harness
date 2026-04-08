---
name: agentic-research
description: "Agentic-Programming research agent: literature survey, idea generation, experiments, paper writing, cross-model review (3 difficulty levels), rebuttal, presentation, research wiki, meta-optimization. Triggers: 'research', 'agentic research', 'write paper', 'survey literature', 'generate ideas', 'run experiments', 'review paper', 'polish', 'translate', 'rebuttal', 'make slides', 'make poster', 'ablation', 'derive formula', 'write proof', 'grant proposal', 'research wiki', 'meta optimize', '写论文', '文献调研', '润色', '翻译', '去AI味', '审稿', '实验分析'."
---

# Agentic Research

Autonomous research agent built with [Agentic Programming](https://github.com/Fzkuji/Agentic-Programming). Part of the Agentic-Programming ecosystem.

## Usage

```
/agentic-research "<your task>"
```

This single entry point covers the entire research lifecycle. The agent reads your task and decides which functions to call. Examples:

```
/agentic-research "Survey recent work on uncertainty quantification in LLMs and identify research gaps"
/agentic-research "Generate 5 research ideas based on the gaps in related_work/gaps.md"
/agentic-research "Design experiments for the top-ranked idea in IDEA_REPORT.md"
/agentic-research "Write the introduction section based on outline/outline.md"
/agentic-research "Polish this paragraph for NeurIPS: <text>"
/agentic-research "翻译这段中文为英文LaTeX: <中文草稿>"
/agentic-research "Review paper/ as a NeurIPS reviewer with difficulty: nightmare"
/agentic-research "Parse these reviewer comments and draft an ICML rebuttal within 5000 chars: <reviews>"
/agentic-research "Generate Beamer slides for a 15-minute oral talk from paper/"
/agentic-research "Derive the gradient formula from these scattered notes: <notes>"
/agentic-research "Run the full pipeline for topic 'LLM Uncertainty', venue NeurIPS"
/agentic-research "Initialize research wiki and ingest these papers"
/agentic-research "Analyze usage patterns and suggest harness optimizations"
```

## Available Functions

See the full list by calling `agentic_research()` in Python, or read the docstring in `main.py`.

**Pipeline**: init → literature → idea → experiment → analysis → writing → review → submission

**Writing**: write_section, polish (rigorous/natural), translate (zh↔en), compress, expand, check_logic, analyze_results, results_to_claims, 中转中, 表达润色, 去AI味

**Figures**: figure/table captions, visualization recommendations, architecture diagrams, matplotlib plots, mermaid diagrams, LaTeX compilation

**Review**: cross-model review loop (medium/hard/nightmare), debate protocol, reviewer memory, paper improvement loop, parse reviews, rebuttal strategy, draft rebuttal

**Presentation**: Beamer slides, conference poster, speaker notes

**Theory**: formula derivation, proof writing, ablation planning, research refinement, grant proposals (NSFC/NSF/ERC/...)

**Search**: arXiv, Semantic Scholar, comprehensive literature review

**Knowledge**: research wiki (papers/ideas/experiments/claims + relationship graph)

**Meta**: harness self-optimization from usage logs

**References**: writing principles, citation discipline, venue checklists
