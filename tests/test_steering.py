"""Mid-run steering inbox — push from one process, drain in the running loop."""
from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture()
def _state_dir(monkeypatch):
    d = tempfile.mkdtemp()
    monkeypatch.setenv("OPENPROGRAM_STATE_DIR", d)
    return d


def test_push_pending_drain_order(_state_dir):
    from research_harness import steering
    sid = "research_steer_test"
    assert steering.pending(sid) is False
    assert steering.push(sid, "skip experiments, fill literature first")
    assert steering.push(sid, "and target NeurIPS")
    assert steering.pending(sid) is True
    msgs = steering.drain(sid)
    assert msgs == ["skip experiments, fill literature first", "and target NeurIPS"]
    assert steering.pending(sid) is False  # drain removed them


def test_empty_message_ignored(_state_dir):
    from research_harness import steering
    sid = "research_steer_empty"
    assert steering.push(sid, "   ") is False
    assert steering.pending(sid) is False


def test_clear(_state_dir):
    from research_harness import steering
    sid = "research_steer_clear"
    steering.push(sid, "x")
    steering.clear(sid)
    assert steering.pending(sid) is False
