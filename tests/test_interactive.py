"""Tests for the attended Socratic dialogue mode (stages/interactive)."""

import json
import os

import pytest

from openprogram.functions.agentics.ask_user import set_ask_user

from research_harness.stages.interactive import socratic_plan
from tests.conftest import MockRuntime


def _j(obj) -> str:
    return json.dumps(obj)


@pytest.fixture
def scripted_user():
    """Register a scripted ask_user handler; always unregister after."""
    answers = []

    def install(*replies):
        answers.extend(replies)

    set_ask_user(lambda q: answers.pop(0) if answers else None)
    try:
        yield install
    finally:
        set_ask_user(None)


class TestSocraticPlan:
    def test_dialogue_collects_answers_and_writes_brief(self, tmp_path,
                                                        scripted_user):
        scripted_user("We study LLM uncertainty", "Calibration error on QA")
        rt = MockRuntime([
            _j({"call": "ask", "args": {
                "question": "What is the core claim?",
                "qtype": "clarifying", "insight": ""}}),
            _j({"call": "ask", "args": {
                "question": "What evidence would support it?",
                "qtype": "probing",
                "insight": "[INSIGHT: thesis] LLM uncertainty is measurable"}}),
            _j({"call": "wrap_up", "args": {
                "brief_markdown": "# Research Brief\n\nCore: uncertainty."}}),
        ])
        out = socratic_plan(topic="LLM uncertainty",
                            output_dir=str(tmp_path), runtime=rt)
        assert "RESEARCH_BRIEF.md" in out
        brief = (tmp_path / "RESEARCH_BRIEF.md").read_text(encoding="utf-8")
        assert "Core: uncertainty" in brief
        transcript = (tmp_path / "dialogue_transcript.md").read_text(
            encoding="utf-8")
        assert "What is the core claim?" in transcript
        assert "We study LLM uncertainty" in transcript
        assert "[INSIGHT: thesis]" in transcript

    def test_quit_word_triggers_wrap_up(self, tmp_path, scripted_user):
        scripted_user("done")
        rt = MockRuntime([
            _j({"call": "ask", "args": {
                "question": "First question?", "qtype": "clarifying",
                "insight": ""}}),
            _j({"call": "wrap_up", "args": {
                "brief_markdown": "# Brief from partial dialogue"}}),
        ])
        out = socratic_plan(topic="x", output_dir=str(tmp_path), runtime=rt)
        assert "RESEARCH_BRIEF.md" in out
        assert (tmp_path / "RESEARCH_BRIEF.md").exists()

    def test_headless_returns_error_not_crash(self, tmp_path):
        # No handler registered and pytest stdin is not a TTY.
        set_ask_user(None)
        rt = MockRuntime("unused")
        out = socratic_plan(topic="x", output_dir=str(tmp_path), runtime=rt)
        assert out.startswith("ERROR:")
        assert not (tmp_path / "RESEARCH_BRIEF.md").exists()
        assert rt.calls == []  # no model call wasted

    def test_requires_runtime(self):
        with pytest.raises(ValueError):
            socratic_plan.__wrapped__(topic="x", runtime=None)

    def test_hidden_from_autonomous_loop(self):
        from research_harness.registry import (
            build_stage_available, oversight,
        )
        assert oversight("socratic_plan") == "interactive"
        assert "socratic_plan" not in build_stage_available("project")

    def test_max_turns_forces_wrap_up(self, tmp_path, scripted_user):
        scripted_user("a1", "a2", "a3")
        ask = _j({"call": "ask", "args": {
            "question": "Again?", "qtype": "probing", "insight": ""}})
        rt = MockRuntime([
            ask, ask,
            # forced wrap-up exec after the turn cap
            _j({"call": "wrap_up", "args": {
                "brief_markdown": "# Forced brief"}}),
        ])
        out = socratic_plan(topic="x", output_dir=str(tmp_path),
                            runtime=rt, max_turns=2)
        assert "RESEARCH_BRIEF.md" in out
        assert (tmp_path / "RESEARCH_BRIEF.md").read_text(
            encoding="utf-8") == "# Forced brief"
