"""End-to-end tests — run research_agent against a real project.

Tests use the Travel Agent project at /Users/fzkuji/Documents/Travel Agent/
as the target research project. The agent should read existing files,
identify what's missing, and work on improving the project.

Run with:  pytest tests/test_e2e.py -v -s -m e2e
"""

import os

import pytest

from openprogram.providers import create_runtime
from research_harness.main import research_agent

# The real research project to work on
TRAVEL_AGENT_PROJECT = "/Users/fzkuji/Documents/Travel Agent/2026-EMNLP-6002-TravelAgent"


@pytest.fixture(scope="module")
def rt():
    provider = os.environ.get("TEST_PROVIDER", "claude-code")
    return create_runtime(provider=provider)


def _print_result(result):
    print(f"\n[RESULT] success={result['success']}, stages={result['stages_completed']}")
    for h in result["history"]:
        stage = h.get("stage", "?")
        print(f"  [{stage}] {h.get('sub_task', '')[:60]}")
        for s in h.get("steps", []):
            call = s.get("call", "(direct)")
            ok = "OK" if s.get("success") else "FAIL"
            print(f"    {call} [{ok}]: {s.get('result', '')[:80]}")


@pytest.mark.e2e
class TestTravelAgentProject:
    """Tests that work ON the Travel Agent research project."""

    def test_review_existing_paper(self, rt):
        """Review the current state of the Travel Agent paper and identify what needs work."""
        result = research_agent(
            task=f"Review the paper at {TRAVEL_AGENT_PROJECT} as an EMNLP reviewer. "
                 f"Read all .tex files, identify strengths and weaknesses, "
                 f"and save the review to that project directory.",
            runtime=rt,
        )
        _print_result(result)
        assert result["success"] is True

    def test_polish_introduction(self, rt):
        """Read the introduction from the project and polish it."""
        result = research_agent(
            task=f"Read the introduction at {TRAVEL_AGENT_PROJECT}/1.\\ Introduction.tex, "
                 f"polish it for EMNLP submission quality, "
                 f"and save the polished version back to the project.",
            runtime=rt,
        )
        _print_result(result)
        assert result["success"] is True

    def test_survey_related_work(self, rt):
        """Survey literature relevant to the Travel Agent project."""
        result = research_agent(
            task=f"Based on the paper at {TRAVEL_AGENT_PROJECT}, "
                 f"survey recent work on LLM-based travel planning agents and multi-agent frameworks. "
                 f"Save the survey results to the project directory.",
            runtime=rt,
        )
        _print_result(result)
        assert result["success"] is True
