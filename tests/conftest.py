"""Shared fixtures for research_harness tests."""

import os
import tempfile
import shutil

import pytest


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
    """Mock agentic Runtime that records calls and returns canned responses."""

    def __init__(self, response: str = "Mock LLM response"):
        self.response = response
        self.calls = []

    def exec(self, content=None, **kwargs):
        self.calls.append({"content": content, **kwargs})
        return self.response


@pytest.fixture
def mock_runtime():
    """Provide a MockRuntime instance."""
    return MockRuntime()
