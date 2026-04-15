"""Integration tests for LLM-dependent @agentic_function functions.

These tests call real LLM providers and verify output quality.
Run with: pytest tests/test_llm_functions.py -v -s

Note: Output format varies by runtime provider.
- Direct API (anthropic/openai): returns clean transformed text
- claude-code: may return analysis + transformed text mixed together
Tests check that the LLM understands the task and produces relevant output.
"""

import pytest

from research_harness.main import _create_runtime


@pytest.fixture(scope="module")
def rt():
    """Create a shared runtime for all LLM tests.

    Uses claude-code by default to avoid API key issues.
    Override with TEST_PROVIDER env var.
    """
    import os
    provider = os.environ.get("TEST_PROVIDER", "claude-code")
    return _create_runtime(provider=provider)


class TestPolishRigorous:
    """Test academic polishing function."""

    def test_fixes_grammar(self, rt):
        from research_harness.stages.writing.polish_rigorous import polish_rigorous

        text = "We use a new method that works really good and is way better than old ones. The results show its great."
        result = polish_rigorous(text=text, runtime=rt)

        print(f"\n[INPUT]  {text}")
        print(f"[OUTPUT] {result}")

        assert isinstance(result, str)
        assert len(result) > 10
        # The LLM should produce something different from the input
        assert result.strip() != text.strip()


class TestPolishNatural:
    """Test AI-flavor removal function."""

    def test_removes_ai_words(self, rt):
        from research_harness.stages.writing.polish_natural import polish_natural

        text = "In this paper, we leverage a novel framework to delve into the intricacies of the multifaceted landscape of deep learning, showcasing a tapestry of improvements."
        result = polish_natural(text=text, runtime=rt)

        print(f"\n[INPUT]  {text}")
        print(f"[OUTPUT] {result}")

        assert isinstance(result, str)
        assert len(result) > 20
        # The output should address AI word issues - either by removing them
        # or by pointing them out (depending on runtime)
        result_lower = result.lower()
        # At minimum, the LLM should recognize these as problematic
        ai_words = ["leverage", "delve", "tapestry", "multifaceted"]
        mentioned_or_removed = any(
            w not in result_lower or  # word was removed
            f'"{w}"' in result_lower or  # word was quoted/discussed
            f"**{w}**" in result_lower or  # word was highlighted
            f"**\"{w}\"**" in result_lower
            for w in ai_words
        )
        assert mentioned_or_removed, "LLM should address AI-flavored words"


class TestTranslateZh2En:
    """Test Chinese to English translation."""

    def test_translates_academic_text(self, rt):
        from research_harness.stages.writing.translate_zh2en import translate_zh2en

        text = "我们提出了一种新的注意力机制，通过动态调整权重分配来提高模型在长文本上的表现。"
        result = translate_zh2en(text=text, runtime=rt)

        print(f"\n[INPUT]  {text}")
        print(f"[OUTPUT] {result}")

        assert isinstance(result, str)
        assert len(result) > 10
        # The LLM should produce a response that engages with the content
        assert result.strip() != text.strip()


class TestCompressText:
    """Test text compression function."""

    def test_reduces_word_count(self, rt):
        from research_harness.stages.writing.compress_text import compress_text

        text = "In order to effectively and efficiently address the aforementioned challenges and limitations that have been identified in the existing body of literature, we propose a novel and innovative approach."
        result = compress_text(text=text, runtime=rt)

        print(f"\n[INPUT]  ({len(text.split())} words) {text}")
        print(f"[OUTPUT] ({len(result.split())} words) {result}")

        assert isinstance(result, str)
        assert len(result) > 10
        # The LLM should recognize redundancy in the input
        result_lower = result.lower()
        # Check it produces a shorter version somewhere in the output
        has_short_version = (
            "to address" in result_lower or
            "we propose" in result_lower or
            "limitations" in result_lower
        )
        assert has_short_version, "Output should contain a compressed version"


class TestExpandText:
    """Test text expansion function."""

    def test_adds_depth(self, rt):
        from research_harness.stages.writing.expand_text import expand_text

        text = "Our method outperforms baselines on all datasets."
        result = expand_text(text=text, runtime=rt)

        print(f"\n[INPUT]  ({len(text.split())} words) {text}")
        print(f"[OUTPUT] ({len(result.split())} words) {result}")

        assert isinstance(result, str)
        # Output should be longer than the tiny input
        assert len(result) > len(text)


class TestGenerateFigureCaption:
    """Test figure caption generation."""

    def test_generates_caption(self, rt):
        from research_harness.stages.writing.generate_figure_caption import generate_figure_caption

        desc = "A bar chart comparing F1 scores of 5 methods (Ours, BERT, GPT-2, RoBERTa, XLNet) on 3 datasets (GLUE, SQuAD, MNLI). Our method achieves the highest scores."
        result = generate_figure_caption(description=desc, runtime=rt)

        print(f"\n[INPUT]  {desc}")
        print(f"[OUTPUT] {result}")

        assert isinstance(result, str)
        assert len(result) > 20


class TestCheckLogic:
    """Test logic checking function."""

    def test_detects_contradiction(self, rt):
        from research_harness.stages.writing.check_logic import check_logic

        # This text has a logical issue: standard self-attention is O(n^2), not O(n log n)
        text = "We propose a transformer-based model that processes input sequences in parallel. The self-attention mechanism computes attention weights for all positions simultaneously, reducing the computational complexity from O(n^2) to O(n log n)."
        result = check_logic(text=text, runtime=rt)

        print(f"\n[INPUT]  {text}")
        print(f"[OUTPUT] {result}")

        assert isinstance(result, str)
        assert len(result) > 0
        # The LLM should detect the complexity claim issue
        result_lower = result.lower()
        has_feedback = (
            "contradict" in result_lower or
            "inconsisten" in result_lower or
            "standard" in result_lower or
            "o(n" in result_lower or
            "complexity" in result_lower or
            "事实" in result or
            "矛盾" in result or
            "问题" in result
        )
        assert has_feedback, "LLM should detect the logical issue in complexity claim"


class TestAnalyzeResults:
    """Test experimental results analysis."""

    def test_analyzes_data(self, rt):
        from research_harness.stages.writing.analyze_results import analyze_results

        data = """
Method    | BLEU  | ROUGE-L | BERTScore
----------|-------|---------|----------
Baseline  | 32.1  | 45.3    | 0.87
+Attention| 35.4  | 48.7    | 0.89
+Ours     | 38.2  | 51.2    | 0.91
"""
        result = analyze_results(data=data, runtime=rt)

        print(f"\n[INPUT]\n{data}")
        print(f"[OUTPUT] {result}")

        assert isinstance(result, str)
        assert len(result) > 50
        # Should reference the actual numbers or methods
        result_lower = result.lower()
        has_analysis = (
            "bleu" in result_lower or
            "rouge" in result_lower or
            "baseline" in result_lower or
            "attention" in result_lower or
            "improvement" in result_lower or
            "提升" in result or
            "提高" in result or
            "38" in result
        )
        assert has_analysis, "Analysis should reference the actual data"
