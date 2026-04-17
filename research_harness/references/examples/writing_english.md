# Writing (English) — Quality Standards

## What good academic writing looks like

### Abstract: Five-sentence formula
1. What you achieved (the claim)
2. Why the problem is important and difficult
3. How you approached it (method in one sentence)
4. What evidence supports the claim (key result)
5. What number the reader should remember

### Before/After — Polishing Example

**Before (typical draft):**
> We use a new method to improve the performance of language models on reasoning tasks. Our method works better than previous methods. We test it on several benchmarks and get good results.

**After (publication-ready):**
> We introduce Chain-of-Verification (CoVe), a two-stage prompting strategy that reduces hallucination in large language models by 38% on TruthfulQA. CoVe first generates an initial response, then produces targeted verification questions whose answers are cross-checked against the original output. On four factual QA benchmarks, CoVe consistently outperforms self-consistency and retrieval-augmented baselines while requiring no additional training.

### Key differences:
- Specific method name, not "a new method"
- Concrete numbers, not "good results"
- Mechanism described, not just "works better"
- Positioned against specific baselines

## Common problems to catch
- Overclaiming without evidence ("significantly outperforms")
- Vague contributions ("we propose a novel framework")
- AI-flavored openings ("In recent years, LLMs have achieved remarkable...")
- Missing quantitative results in abstract/intro
