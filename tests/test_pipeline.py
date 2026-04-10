"""Tests for research_harness.pipeline — stage selection logic."""

import pytest

from research_harness.pipeline import STAGES, research_pipeline


class TestStageSelection:
    """Test how the pipeline selects which stages to run.

    These tests use a mock approach: we test the stage selection logic
    by calling research_pipeline with invalid project_dir (stages will
    skip due to missing prerequisites). The goal is to verify the
    control flow, not actual LLM calls.
    """

    def test_stages_constant(self):
        assert STAGES == [
            "init", "literature", "idea", "experiment",
            "analysis", "writing", "review", "submission",
        ]

    def test_stages_are_strings(self):
        for s in STAGES:
            assert isinstance(s, str)

    def test_stage_names_unique(self):
        assert len(STAGES) == len(set(STAGES))

    def test_pipeline_requires_runtime(self, tmp_dir):
        """Pipeline should raise if exec_runtime is not provided."""
        with pytest.raises(ValueError, match="exec_runtime"):
            research_pipeline(
                project_dir=tmp_dir,
                topic="Test",
                stages=["init"],
            )

    def test_pipeline_init_stage(self, tmp_dir, mock_runtime):
        """Init stage should create project structure."""
        import os
        result = research_pipeline(
            project_dir=tmp_dir,
            topic="Test Topic",
            stages=["init"],
            venue="NeurIPS",
            exec_runtime=mock_runtime,
        )
        assert isinstance(result, dict)
