"""Tests for research_harness.log — operation log module."""

import os

import pytest

from research_harness import log as oplog


class TestLogModule:
    """Test append-only operation log."""

    def test_append_noop_when_none(self):
        """append() with None log_file should silently do nothing."""
        oplog.append(None, "some text")  # should not raise

    def test_log_session_creates_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.log.md")
        oplog.log_session(path, "my task")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "my task" in content

    def test_log_stage_appends(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.log.md")
        oplog.log_session(path, "task")
        oplog.log_stage(path, 1, "literature", "survey papers")
        with open(path) as f:
            content = f.read()
        assert "[literature]" in content
        assert "survey papers" in content

    def test_log_step_appends(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.log.md")
        oplog.log_session(path, "task")
        oplog.log_step(path, "survey_topic", "topic=LLM", True, "Found 10 papers")
        with open(path) as f:
            content = f.read()
        assert "survey_topic" in content
        assert "OK" in content

    def test_log_step_failure(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.log.md")
        oplog.log_session(path, "task")
        oplog.log_step(path, "bad_func", "", False, "Error occurred")
        with open(path) as f:
            content = f.read()
        assert "FAIL" in content

    def test_log_done_appends(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.log.md")
        oplog.log_session(path, "task")
        oplog.log_done(path, "all complete")
        with open(path) as f:
            content = f.read()
        assert "DONE" in content

    def test_full_session_log(self, tmp_dir):
        """Simulate a full session and verify log structure."""
        path = os.path.join(tmp_dir, "full.log.md")
        oplog.log_session(path, "Survey LLM uncertainty")
        oplog.log_stage(path, 1, "literature", "survey recent papers")
        oplog.log_step(path, "survey_topic", "topic=LLM uncertainty", True, "Found papers")
        oplog.log_step(path, "identify_gaps", "survey=...", True, "3 gaps found")
        oplog.log_stage(path, 2, "idea", "generate ideas from gaps")
        oplog.log_step(path, "generate_ideas", "topic=LLM, gaps=...", True, "5 ideas generated")
        oplog.log_done(path, "task complete")

        with open(path) as f:
            content = f.read()

        # Verify structure
        assert content.count("##") >= 2  # at least 2 stage headers
        assert "survey_topic" in content
        assert "identify_gaps" in content
        assert "generate_ideas" in content
        assert "DONE" in content
