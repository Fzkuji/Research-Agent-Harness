"""Tests for research_agent's run-logic guards — the controls that keep
a run moving end-to-end and stop it from spinning.

Covers the optimization pass:
  - global step budget (_MAX_TOTAL_STEPS)
  - per-function failure backstop (_MAX_FUNC_FAILURES -> blocked, dropped
    from the catalog)
  - cross-stage no-progress guard (_MAX_STAGE_REVISITS)
  - func_done normalization (done/passed/none -> one bool)

All via MockRuntime — no real LLM. The point is that whatever the model
does, the loop terminates and reports WHY.
"""
import json

from research_harness.main import (
    research_agent, _stage_step,
    _MAX_TOTAL_STEPS, _MAX_FUNC_FAILURES, _MAX_STAGE_REVISITS,
)
from tests.conftest import MockRuntime


def _json(obj: dict) -> str:
    return json.dumps(obj)


# ── func_done normalization (problem 1+2) ────────────────────────────

class TestFuncDoneNormalization:
    """_stage_step must surface a single func_done bool regardless of
    whether the orchestrator returned done / passed / nothing."""

    def test_done_false_is_surfaced(self, monkeypatch):
        """An orchestrator returning {'done': False} -> func_done False."""
        import research_harness.main as m

        avail = {"fake_orch": {"function": lambda runtime=None: {"done": False},
                               "description": "x", "input": {}, "output": {}}}
        monkeypatch.setattr(m, "build_stage_available", lambda stage: avail)
        monkeypatch.setattr(m, "render_options", lambda a: "fake_orch")
        monkeypatch.setattr(m, "extract_action", lambda r: {"call": "fake_orch"})
        monkeypatch.setattr(m, "parse_args",
                            lambda reply, av, rt: (av["fake_orch"]["function"], {}))

        rt = MockRuntime(_json({"call": "fake_orch"}))
        out = _stage_step(stage="literature", sub_task="x", context="", runtime=rt)
        assert out["success"] is True
        assert out["func_done"] is False

    def test_passed_maps_to_func_done(self, monkeypatch):
        """review_loop-style {'passed': True} -> func_done True."""
        import research_harness.main as m

        avail = {"review_loop": {"function": lambda runtime=None: {"passed": True},
                                 "description": "x", "input": {}, "output": {}}}
        monkeypatch.setattr(m, "build_stage_available", lambda stage: avail)
        monkeypatch.setattr(m, "render_options", lambda a: "review_loop")
        monkeypatch.setattr(m, "extract_action", lambda r: {"call": "review_loop"})
        monkeypatch.setattr(m, "parse_args",
                            lambda reply, av, rt: (av["review_loop"]["function"], {}))

        rt = MockRuntime(_json({"call": "review_loop"}))
        out = _stage_step(stage="review", sub_task="x", context="", runtime=rt)
        assert out["func_done"] is True

    def test_no_flag_single_shot_is_done(self, monkeypatch):
        """A single-shot function (no flag, plain dict) -> func_done True."""
        import research_harness.main as m

        avail = {"run_idea": {"function": lambda runtime=None: {"ideas": "..."},
                              "description": "x", "input": {}, "output": {}}}
        monkeypatch.setattr(m, "build_stage_available", lambda stage: avail)
        monkeypatch.setattr(m, "render_options", lambda a: "run_idea")
        monkeypatch.setattr(m, "extract_action", lambda r: {"call": "run_idea"})
        monkeypatch.setattr(m, "parse_args",
                            lambda reply, av, rt: (av["run_idea"]["function"], {}))

        rt = MockRuntime(_json({"call": "run_idea"}))
        out = _stage_step(stage="idea", sub_task="x", context="", runtime=rt)
        assert out["func_done"] is True


# ── blocked-function backstop (problem 3) ────────────────────────────

def test_blocked_function_dropped_from_catalog(monkeypatch):
    """A name in `blocked` must not appear in the catalog handed to the LLM."""
    import research_harness.main as m

    avail = {
        "good_fn": {"function": lambda runtime=None: "ok", "description": "g",
                    "input": {}, "output": {}},
        "bad_fn": {"function": lambda runtime=None: "ok", "description": "b",
                   "input": {}, "output": {}},
    }
    captured = {}

    def _render(a):
        captured["names"] = set(a.keys())
        return ",".join(a.keys())

    monkeypatch.setattr(m, "build_stage_available", lambda stage: dict(avail))
    monkeypatch.setattr(m, "render_options", _render)
    monkeypatch.setattr(m, "extract_action", lambda r: {"call": "good_fn"})
    monkeypatch.setattr(m, "parse_args",
                        lambda reply, av, rt: (av["good_fn"]["function"], {}))

    rt = MockRuntime(_json({"call": "good_fn"}))
    _stage_step(stage="x", sub_task="x", context="", runtime=rt,
                blocked=frozenset({"bad_fn"}))
    assert "bad_fn" not in captured["names"]
    assert "good_fn" in captured["names"]


# ── end-to-end: a spinning run TERMINATES via the guards ─────────────

def test_repeatedly_failing_function_is_blocked_and_run_ends(monkeypatch):
    """A function that always fails gets blocked after _MAX_FUNC_FAILURES;
    the run then ends instead of looping forever. This is the regression
    for the real review_loop spin (model never called the submit tool).

    _pick_stage is stubbed to always route into 'review' (the LLM never
    voluntarily says done) so the ONLY thing that can end the run is a
    run-logic guard — exactly what we're testing.
    """
    import research_harness.main as m

    monkeypatch.setattr(m, "_pick_stage",
                        lambda task, progress, runtime: {
                            "stage": "review", "sub_task": "x",
                            "reasoning": "", "done": False, "ok": True})
    monkeypatch.setattr(m, "_conclusion",
                        lambda task, history, completed, runtime: "stub")

    # Every stage step "fails" with the same broken function.
    monkeypatch.setattr(m, "_stage_step",
                        lambda **kw: {"call": "flaky", "args_summary": "",
                                      "result": "ValueError: submit tool not called",
                                      "success": False, "func_done": False,
                                      "stage_done": False})

    rt = MockRuntime(["unused"])
    result = research_agent(task="spin", runtime=rt)

    # Terminated, didn't hang, and never falsely reports success.
    assert result["success"] is False
    assert result["total_steps"] <= _MAX_TOTAL_STEPS
    assert result["stop_reason"] is not None


def test_global_step_budget_caps_total_work(monkeypatch):
    """Even if every step 'succeeds' and the LLM never says done, the run
    stops at _MAX_TOTAL_STEPS — the cross-stage backstop. _pick_stage is
    stubbed to keep routing forward, _stage_step to always succeed without
    ever signalling stage_done, so only the global budget can end it."""
    import research_harness.main as m

    # Route into a different stage each visit so the no-progress guard
    # (which stops a stuck stage) doesn't fire first — we want the GLOBAL
    # budget to be the thing that trips.
    stages = ["literature", "idea", "experiment", "writing", "review",
              "rebuttal", "presentation", "theory", "knowledge", "project"]
    counter = {"n": 0}

    def _pick(task, progress, runtime):
        s = stages[counter["n"] % len(stages)]
        counter["n"] += 1
        return {"stage": s, "sub_task": "x", "reasoning": "",
                "done": False, "ok": True}

    monkeypatch.setattr(m, "_pick_stage", _pick)
    monkeypatch.setattr(m, "_conclusion",
                        lambda task, history, completed, runtime: "stub")
    # Succeeds, makes progress, never says stage_done, and uses a DIFFERENT
    # args_summary each call so the per-stage repeat guard never trips —
    # the only thing that can stop this is the global step budget.
    step_n = {"n": 0}

    def _step(**kw):
        step_n["n"] += 1
        return {"call": "noop", "args_summary": f"v{step_n['n']}",
                "result": "ok", "success": True,
                "func_done": False, "stage_done": False}

    monkeypatch.setattr(m, "_stage_step", _step)

    rt = MockRuntime(["unused"])
    result = research_agent(task="never-ending", runtime=rt)
    assert result["total_steps"] <= _MAX_TOTAL_STEPS
    # The global budget (not max_stages, not the repeat guard) is what
    # ended it — verify the run actually pushed up against the ceiling.
    assert result["total_steps"] >= _MAX_TOTAL_STEPS - _MAX_STAGE_REVISITS
    assert result["stop_reason"] is not None
    assert "budget" in result["stop_reason"]
