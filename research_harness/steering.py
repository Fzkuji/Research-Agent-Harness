"""Mid-run steering — inject a user's course-correction into a live run.

The user, watching a long research run, may want to change direction
("stop writing experiments, go back and fill the literature first"). This is
the channel for that: any surface pushes a message; the research_agent loop
drains it at its next stage/step boundary and folds it into the next routing
decision — without interrupting the in-flight step.

Cross-process by design. The research CLI runs IN ITS OWN PROCESS, so a
separate ``research-harness steer`` invocation cannot touch its memory. The
inbox is therefore a per-session directory of message files under the session
dir; any process (the steer subcommand, the worker forwarding a TUI/web
action) drops a file, and the running loop drains them in order. A pure
in-memory queue would only work within one process — this also covers it
because ``push`` writes a file the same loop reads.

File layout: ``<session_dir>/steering/<ts>-<rand>.txt`` (one message each).
Drained files are deleted. Resolution of <session_dir> reuses the store's
``_session_dir`` so it matches wherever sessions actually live.
"""
from __future__ import annotations

import os


def _steer_dir(session_id: str) -> "str | None":
    """``<session_dir>/steering`` for this session, created on demand. None if
    the session dir can't be resolved (no store configured)."""
    if not session_id:
        return None
    try:
        from openprogram.store.session.session_store import SessionStore
        sdir = SessionStore()._session_dir(session_id)
        d = os.path.join(str(sdir), "steering")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return None


def push(session_id: str, message: str) -> bool:
    """Queue a steering message for ``session_id``. Returns True if written.

    Any process may call this (the steer subcommand, the worker). Uses a
    monotonic-ish filename so drain order is stable; ``index`` varies the name
    within the same second without needing a clock the caller controls."""
    if not message or not message.strip():
        return False
    d = _steer_dir(session_id)
    if d is None:
        return False
    # Name by existing count + a short token so concurrent pushes don't clash.
    import uuid
    n = len([f for f in os.listdir(d) if f.endswith(".txt")])
    path = os.path.join(d, f"{n:06d}-{uuid.uuid4().hex[:6]}.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(message.strip())
        return True
    except OSError:
        return False


def pending(session_id: str) -> bool:
    """True when there is at least one un-drained steering message."""
    d = _steer_dir(session_id)
    if d is None:
        return False
    try:
        return any(f.endswith(".txt") for f in os.listdir(d))
    except OSError:
        return False


def drain(session_id: str) -> "list[str]":
    """Take and remove all queued messages for ``session_id`` (oldest first)."""
    d = _steer_dir(session_id)
    if d is None:
        return []
    try:
        files = sorted(f for f in os.listdir(d) if f.endswith(".txt"))
    except OSError:
        return []
    msgs: list[str] = []
    for fn in files:
        p = os.path.join(d, fn)
        try:
            with open(p, encoding="utf-8") as f:
                msgs.append(f.read().strip())
        except OSError:
            continue
        try:
            os.unlink(p)
        except OSError:
            pass
    return msgs


def clear(session_id: str) -> None:
    """Drop any queued messages (call when a run ends, so the next starts clean)."""
    drain(session_id)
