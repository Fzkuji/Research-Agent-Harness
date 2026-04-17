# LITERATURE — Quality Standards

## What a good literature survey looks like

### Structure requirements

A survey should be organized as a **hierarchy of subtopics**, not a flat list.
Each subtopic should contain 5-15 papers, grouped by approach or contribution type.

Good structure example:
```
# Literature Survey: Context Management in LLM Agents

## 1. Context Window Optimization
### 1.1 Compression-based approaches
  - Paper 1...
  - Paper 2...
### 1.2 Retrieval-augmented approaches
  - Paper 3...

## 2. Multi-Agent Context Sharing
### 2.1 Shared memory architectures
  - Paper 4...
### 2.2 Message passing protocols
  - Paper 5...

## 3. Long-Term Memory
### 3.1 Vector store approaches
### 3.2 Knowledge graph approaches
```

### Paper entry format

Each paper entry should include ALL of the following:

```
- **Title** (Authors, Venue Year) [paper](url) [code](url)
  Core contribution: one sentence describing what's new.
  Method: brief description of the approach.
  Limitation: what it doesn't solve.
```

Good example:
```
- **ReAct: Synergizing Reasoning and Acting in Language Models**
  (Yao et al., ICLR 2023) [paper](https://arxiv.org/abs/2210.03629) [code](https://github.com/ysymyth/ReAct)
  Core: Interleaves chain-of-thought reasoning with tool-use actions in a single prompt.
  Method: LLM generates thought-action-observation traces; actions call external APIs.
  Limitation: Prone to error propagation — one wrong action derails the entire trace.
```

Bad example (too vague):
```
- ReAct (2023) — A method for combining reasoning and acting in LLMs.
```

### Coverage standards

A thorough survey should:
- Cover **20+ papers** minimum for a broad topic
- Include **foundational work** (pre-2023) AND **recent work** (2024-2026)
- Prioritize **top venues**: NeurIPS, ICML, ICLR, ACL, EMNLP, AAAI, CVPR
- Include both **journal** (JMLR, TPAMI, TACL, Nature MI) and **conference** papers
- Note which papers are **arXiv-only** vs **peer-reviewed**
- End each section with a **gap analysis**: "Existing work in this area lacks..."

### Optional enhancements
- Use impact indicators: 🔥 (code available, stars >= 100), ⭐ (citations >= 50)
- Include a summary table with columns: Title | Venue | Year | Method | Key Result
- For experiment-heavy topics, add a comparison table: Method | Dataset | Metric | Result

## Reference repositories (use as structural examples)

When organizing a survey, study these repositories for inspiration on structure,
categorization, and entry formatting. Choose the style most appropriate for the topic.

### Agent & Reasoning
- https://github.com/WooooDyy/LLM-Agent-Paper-List
  Style: Hierarchical by agent components (Brain/Perception/Action), `[Year/Month] Title. Author. Venue. [paper][code]`
- https://github.com/hyp1231/awesome-llm-powered-agent
  Style: Nested categories with 🔥📖 impact indicators, grouped by application domain
- https://github.com/luo-junyu/Awesome-Agent-Papers
  Style: Alphabetical categories + brief description per paper

### Deep Research & Reasoning
- https://github.com/DavidZWZ/Awesome-Deep-Research
  Style: Comprehensive table with columns: Title | Date | Base Model | Optimization | Architecture | Evaluation
  Good for: systematic comparison of methods across multiple dimensions

### Uncertainty, Reliability & Robustness
- https://github.com/jxzhangjhu/Awesome-LLM-Uncertainty-Reliability-Robustness
  Style: Three-tier taxonomy (Uncertainty → Estimation/Calibration/Confidence; Reliability → Hallucination/Truthfulness; Robustness → OOD/Adversarial)
  Good for: topics with clear sub-problem decomposition

### LLM + Reinforcement Learning
- https://github.com/WindyLab/LLM-RL-Papers
  Style: Organized by methodology type (Action/Reward/Planning/State), each entry has framework diagram + detailed description
  Good for: method-centric surveys where visual architecture comparison matters

### Federated Learning
- https://github.com/youngfish42/Awesome-FL
  Style: Dual-axis organization (by research field AND by publication venue/tier), annotation system 🔥⭐🎓
  Good for: cross-disciplinary topics spanning multiple research communities

### Meta-Learning
- https://github.com/sudharsan13296/Awesome-Meta-Learning
  Style: Classic format `**Title** (Year) *Authors* [pdf][code]`, clean subcategories (Zero-Shot/Few-Shot/MAML/Meta-RL)
  Good for: well-established fields with clear methodological families

## Function-specific standards

### survey_topic
- Minimum 20 papers, organized into 3-5 subtopics
- Each subtopic has an introductory paragraph explaining the research direction
- Each paper has: title, authors, venue, year, URL, 1-line contribution, 1-line limitation
- End with "Key Observations" section summarizing trends

### identify_gaps
- Each gap must be **specific and actionable** (not "more research needed")
- Good: "No existing method handles context windows > 128K tokens without quality degradation on multi-hop reasoning tasks"
- Bad: "Long context is still an open problem"
- Prioritize gaps by impact: which gaps, if solved, would enable the most progress?
- For each gap, cite which papers come closest and why they fall short

### search_arxiv / search_semantic_scholar
- Return structured results with ALL metadata (ID, title, authors, date, venue, citations)
- Sort by relevance, then by citation count
- Flag highly-cited papers (>50 citations)
- Note publication status: peer-reviewed vs preprint

### comprehensive_lit_review
- Must be publication-ready LaTeX with proper \citep{} and \citet{} usage
- Follow progression or parallel structure per subsection
- Every subsection ends with limitation discussion connecting to your contribution
- Include both classic foundations and cutting-edge recent work
