"""Mid-run steering inbox — push from one process, drain in the running loop.

The inbox is file-backed under the real ~/.openprogram/sessions/<id>/steering
(SessionStore doesn't honour a temp state dir), so each test uses a unique
session id and clears it before+after to stay isolated across runs.
"""
from __future__ import annotations

import pytest

_SIDS = [
    "test_steer_order", "test_steer_empty", "test_steer_clear",
    "test_steer_current",
]


@pytest.fixture(autouse=True)
def _clean_inboxes():
    from research_harness import steering
    for sid in _SIDS:
        steering.clear(sid)
    steering.set_current_session(None)
    yield
    for sid in _SIDS:
        steering.clear(sid)
    steering.set_current_session(None)


def test_push_pending_drain_order():
    from research_harness import steering
    sid = "test_steer_order"
    assert steering.pending(sid) is False
    assert steering.push(sid, "skip experiments, fill literature first")
    assert steering.push(sid, "and target NeurIPS")
    assert steering.pending(sid) is True
    msgs = steering.drain(sid)
    assert msgs == ["skip experiments, fill literature first", "and target NeurIPS"]
    assert steering.pending(sid) is False  # drain removed them


def test_empty_message_ignored():
    from research_harness import steering
    sid = "test_steer_empty"
    assert steering.push(sid, "   ") is False
    assert steering.pending(sid) is False


def test_clear():
    from research_harness import steering
    sid = "test_steer_clear"
    steering.push(sid, "x")
    steering.clear(sid)
    assert steering.pending(sid) is False


def test_pending_current_for_orchestrator_loops():
    """Long orchestrators (run_literature/experiments/review) poll
    pending_current() with no session_id and break their inner loop so a
    mid-run steer isn't swallowed for minutes."""
    from research_harness import steering
    sid = "test_steer_current"
    steering.set_current_session(sid)
    assert steering.pending_current() is False
    steering.push(sid, "change direction")
    assert steering.pending_current() is True
    steering.set_current_session(None)
    # No current session registered → never reports pending.
    assert steering.pending_current() is False
