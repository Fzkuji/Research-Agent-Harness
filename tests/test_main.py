"""Tests for research_harness.main — two-level autonomous loop.

Uses MockRuntime to test _pick_stage, _stage_step, and research_agent
WITHOUT calling a real LLM.
"""

import json
import os

import pytest

from tests.conftest import MockRuntime


# ── Helpers ──────────────────────────────────────────────────────────

def _json(obj: dict) -> str:
    """Wrap a dict as a JSON string (simulates LLM reply)."""
    return json.dumps(obj)


# ── _pick_stage ──────────────────────────────────────────────────────

class TestPickStage:
    """Level 1: stage selection."""

    def test_picks_valid_stage(self):
        from research_harness.main import _pick_stage

        rt = MockRuntime(_json({
            "stage": "literature",
            "reasoning": "need to survey first",
            "sub_task": "survey LLM uncertainty",
            "done": False,
        }))
        result = _pick_stage(task="Survey LLM uncertainty", progress="", runtime=rt)
        assert result["stage"] == "literature"
        assert result["done"] is False
        assert len(rt.calls) == 1

    def test_signals_done(self):
        from research_harness.main import _pick_stage

        rt = MockRuntime(_json({
            "stage": "done",
            "reasoning": "all tasks complete",
            "done": True,
        }))
        result = _pick_stage(task="task", progress="lots done", runtime=rt)
        assert result["done"] is True

    def test_bad_json_returns_done(self):
        from research_harness.main import _pick_stage

        rt = MockRuntime("I'm not sure what to do next, let me think...")
        result = _pick_stage(task="task", progress="", runtime=rt)
        assert result["done"] is True

    def test_progress_passed_to_llm(self):
        from research_harness.main import _pick_stage

        rt = MockRuntime(_json({"stage": "writing", "done": False, "sub_task": "x", "reasoning": "y"}))
        _pick_stage(task="t", progress="[literature] done", runtime=rt)
        prompt_text = rt.calls[0]["content"][0]["text"]
        assert "[literature] done" in prompt_text


# ── _stage_step ──────────────────────────────────────────────────────

class TestStageStep:
    """Level 2: function selection and execution within a stage."""

    def test_calls_function_successfully(self):
        from research_harness.main import _stage_step

        rt = MockRuntime(_json({
            "call": "polish_rigorous",
            "args": {"text": "test input"},
            "reasoning": "need polish",
        }))
        result = _stage_step(stage="writing", sub_task="polish text", context="", runtime=rt)
        assert result["call"] == "polish_rigorous"
        # polish_rigorous itself calls runtime.exec, so there should be 2 calls
        assert len(rt.calls) == 2
        assert result["success"] is True

    def test_unknown_function(self):
        from research_harness.main import _stage_step

        rt = MockRuntime(_json({
            "call": "nonexistent_function_xyz",
            "args": {},
            "reasoning": "confused",
        }))
        result = _stage_step(stage="writing", sub_task="task", context="", runtime=rt)
        assert result["success"] is False
        assert "Unknown function" in result["result"]

    def test_stage_done_signal(self):
        from research_harness.main import _stage_step

        rt = MockRuntime(_json({
            "stage_done": True,
            "reasoning": "nothing more to do",
        }))
        result = _stage_step(stage="writing", sub_task="task", context="", runtime=rt)
        assert result["stage_done"] is True
        assert result["call"] is None

    def test_bad_json_returns_done(self):
        from research_harness.main import _stage_step

        rt = MockRuntime("I think the task is complete now.")
        result = _stage_step(stage="writing", sub_task="task", context="", runtime=rt)
        assert result["success"] is True
        assert result["call"] is None

    def test_context_passed_to_llm(self):
        from research_harness.main import _stage_step

        rt = MockRuntime(_json({"stage_done": True, "reasoning": "done"}))
        _stage_step(stage="writing", sub_task="task", context="prev: polish OK", runtime=rt)
        prompt_text = rt.calls[0]["content"][0]["text"]
        assert "prev: polish OK" in prompt_text


# ── research_agent ───────────────────────────────────────────────────

class TestResearchAgent:
    """Top-level research_agent orchestration."""

    def test_requires_runtime(self):
        from research_harness.main import research_agent
        with pytest.raises(ValueError, match="runtime"):
            research_agent(task="test", runtime=None)

    def test_single_stage_then_done(self):
        """Agent picks one stage, runs one step, then signals done."""
        from research_harness.main import research_agent

        responses = [
            # _pick_stage call 1: pick writing
            _json({"stage": "writing", "reasoning": "polish needed", "sub_task": "polish text", "done": False}),
            # _stage_step call 1: call polish_rigorous
            _json({"call": "polish_rigorous", "args": {"text": "draft"}, "reasoning": "polish"}),
            # polish_rigorous's own runtime.exec
            "Polished text here.",
            # _stage_step call 2: stage done
            _json({"stage_done": True, "reasoning": "polishing complete"}),
            # _pick_stage call 2: overall done
            _json({"stage": "done", "reasoning": "task complete", "done": True}),
        ]
        rt = MockRuntime(responses)
        result = research_agent(task="polish my text", runtime=rt)

        assert result["success"] is True
        assert result["stages_completed"] >= 1
        assert any(h.get("stage") == "writing" for h in result["history"])

    def test_unknown_stage_skipped(self):
        """If LLM picks a non-existent stage, it's skipped and loop continues."""
        from research_harness.main import research_agent

        responses = [
            # pick a bad stage
            _json({"stage": "nonexistent_xyz", "reasoning": "confused", "sub_task": "x", "done": False}),
            # then signal done
            _json({"stage": "done", "reasoning": "done", "done": True}),
        ]
        rt = MockRuntime(responses)
        result = research_agent(task="test", runtime=rt)

        assert result["success"] is True
        assert any("error" in h for h in result["history"])

    def test_safety_limit_stops_loop(self):
        """Loop stops at internal safety limit even if LLM never says done."""
        from research_harness.main import research_agent, _MAX_STAGES

        always_writing = _json({"stage": "writing", "reasoning": "more polish", "sub_task": "polish", "done": False})
        always_polish = _json({"call": "polish_rigorous", "args": {"text": "x"}, "reasoning": "polish"})
        mock_polish_result = "polished"
        stage_done = _json({"stage_done": True, "reasoning": "ok"})

        responses = []
        for _ in range(_MAX_STAGES + 5):
            responses.extend([always_writing, always_polish, mock_polish_result, stage_done])

        rt = MockRuntime(responses)
        result = research_agent(task="test", runtime=rt)

        assert result["stages_completed"] <= _MAX_STAGES + 1

    def test_history_records_steps(self):
        """History captures stage names, sub_tasks, and step results."""
        from research_harness.main import research_agent

        responses = [
            _json({"stage": "writing", "reasoning": "write", "sub_task": "write intro", "done": False}),
            _json({"call": "check_logic", "args": {"text": "some text"}, "reasoning": "check"}),
            "No issues found.",
            _json({"stage_done": True, "reasoning": "done"}),
            _json({"done": True, "reasoning": "all done"}),
        ]
        rt = MockRuntime(responses)
        result = research_agent(task="test", runtime=rt)

        writing_stage = [h for h in result["history"] if h.get("stage") == "writing"]
        assert len(writing_stage) == 1
        steps = writing_stage[0]["steps"]
        assert len(steps) >= 1
        assert steps[0]["call"] == "check_logic"
        assert steps[0]["success"] is True


# ── _create_runtime ──────────────────────────────────────────────────

class TestCreateRuntime:
    """Runtime factory auto-detection."""

    def test_claude_code_provider(self):
        from research_harness.main import _create_runtime
        rt = _create_runtime(provider="claude-code")
        assert rt is not None

    def test_unknown_provider_raises(self):
        from research_harness.main import _create_runtime
        with pytest.raises(RuntimeError):
            _create_runtime(provider="nonexistent_provider_xyz")


# ── CLI main() ───────────────────────────────────────────────────────

class TestCLI:
    """CLI entry point smoke tests."""

    def test_list_flag(self, capsys):
        """--list should print functions and exit."""
        from research_harness.main import main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["research-harness", "--list"]
            main()
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        assert "survey_topic" in captured.out
        assert "[literature]" in captured.out

    def test_no_args_shows_help(self, capsys, monkeypatch):
        """No args in a tty should show help."""
        from research_harness.main import main
        import sys
        import io
        # Simulate a tty stdin so main() goes to print_help instead of stdin.read()
        fake_stdin = io.StringIO("")
        fake_stdin.isatty = lambda: True
        monkeypatch.setattr("sys.stdin", fake_stdin)
        old_argv = sys.argv
        try:
            sys.argv = ["research-harness"]
            main()
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "task" in captured.out.lower()

    def test_list_shows_orchestrators(self, capsys):
        """--list should show orchestrator functions."""
        from research_harness.main import main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["research-harness", "--list"]
            main()
        finally:
            sys.argv = old_argv

        captured = capsys.readouterr()
        assert "run_literature" in captured.out
        assert "run_idea" in captured.out
        assert "run_experiments" in captured.out
