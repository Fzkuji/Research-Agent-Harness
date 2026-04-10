"""Tests for research_harness.evaluate — prompt competition."""

import pytest

from research_harness.evaluate import compete


class TestCompete:
    """Test the compete() prompt competition function."""

    def test_single_candidate(self, mock_runtime):
        """Single function should return directly with score 10."""
        def dummy_fn(text, runtime):
            return "Polished text output"

        result = compete(
            functions=[dummy_fn],
            kwargs={"text": "test input", "runtime": mock_runtime},
            eval_runtime=mock_runtime,
        )
        assert result["winner_index"] == 0
        assert result["winner_output"] == "Polished text output"
        assert result["winner_name"] == "dummy_fn"
        assert result["scores"] == [10]
        assert result["reasoning"] == "Single candidate"

    def test_returns_expected_keys(self, mock_runtime):
        """Result dict should have all expected keys."""
        def fn_a(text, runtime):
            return "Output A"

        result = compete(
            functions=[fn_a],
            kwargs={"text": "test", "runtime": mock_runtime},
            eval_runtime=mock_runtime,
        )
        expected_keys = {
            "winner_index", "winner_output", "winner_name",
            "scores", "reasoning", "all_candidates",
        }
        assert set(result.keys()) == expected_keys

    def test_all_candidates_populated(self, mock_runtime):
        """all_candidates should list each function's output."""
        def fn_a(text, runtime):
            return "Output A"

        result = compete(
            functions=[fn_a],
            kwargs={"text": "test", "runtime": mock_runtime},
            eval_runtime=mock_runtime,
        )
        assert len(result["all_candidates"]) == 1
        assert result["all_candidates"][0]["name"] == "fn_a"
        assert result["all_candidates"][0]["output"] == "Output A"
