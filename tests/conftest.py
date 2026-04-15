"""Shared fixtures for research_harness tests."""

import os
import tempfile
import shutil

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: end-to-end tests that call a real LLM (slow, needs API key or claude-code)")


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory, cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="rh_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def project_dir(tmp_dir):
    """Create a minimal project directory structure for testing."""
    dirs = [
        "outline", "introduction", "method", "experiments",
        "related_work", "paper", "references", "code",
    ]
    for d in dirs:
        os.makedirs(os.path.join(tmp_dir, d), exist_ok=True)

    # Outline file
    with open(os.path.join(tmp_dir, "outline", "outline.md"), "w") as f:
        f.write("# Test Paper Outline\n\n## Introduction\nTest intro outline.\n")

    # Some section notes
    with open(os.path.join(tmp_dir, "introduction", "notes.md"), "w") as f:
        f.write("# Intro Notes\nMotivation: testing is important.\n")

    yield tmp_dir


class MockRuntime:
    """Mock agentic Runtime that records calls and returns canned responses.

    Supports multiple responses for multi-turn tests:
        MockRuntime(["first reply", "second reply"])
    Single response still works:
        MockRuntime("always this")
    """

    def __init__(self, response="Mock LLM response"):
        if isinstance(response, list):
            self._responses = list(response)
        else:
            self._responses = [response]
        self._index = 0
        self.calls = []

    def exec(self, content=None, **kwargs):
        self.calls.append({"content": content, **kwargs})
        resp = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return resp


@pytest.fixture
def mock_runtime():
    """Provide a MockRuntime instance."""
    return MockRuntime()
