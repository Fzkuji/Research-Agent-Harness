"""Tests for the integrity gate (research_harness.stages.integrity)."""

import json
import os

import pytest

from tests.conftest import MockRuntime

from research_harness.stages.integrity import (
    _load_run_records,
    extract_claims,
    integrity_gate,
)


RECORD = {
    "run_id": "step1-a1b2",
    "command": "python train.py --seed 0",
    "config_summary": "lr=1e-4, bs=32",
    "exit_status": "ok",
    "result_files": ["experiments/results.csv"],
    "key_metrics": {"accuracy": 0.84},
    "seeds": [0],
    "timestamp_note": "2026-06-12 run",
}


def _j(obj):
    return json.dumps(obj)


def _make_project(tmp_dir, run_record=None, summary=None, result_csv=None):
    if run_record is not None:
        rdir = os.path.join(tmp_dir, "auto_experiment", "step1")
        os.makedirs(rdir, exist_ok=True)
        with open(os.path.join(rdir, "run_record.json"), "w", encoding="utf-8") as f:
            f.write(run_record if isinstance(run_record, str) else _j(run_record))
    if summary is not None:
        os.makedirs(os.path.join(tmp_dir, "auto_experiment"), exist_ok=True)
        with open(os.path.join(tmp_dir, "auto_experiment", "SUMMARY.md"),
                  "w", encoding="utf-8") as f:
            f.write(summary)
    if result_csv is not None:
        os.makedirs(os.path.join(tmp_dir, "experiments"), exist_ok=True)
        with open(os.path.join(tmp_dir, "experiments", "results.csv"),
                  "w", encoding="utf-8") as f:
            f.write(result_csv)


class TestRunRecords:
    def test_valid_record_parses(self, tmp_dir):
        _make_project(tmp_dir, run_record=RECORD)
        records = _load_run_records(tmp_dir)
        assert len(records) == 1
        assert records[0]["record"]["run_id"] == "step1-a1b2"
        assert records[0]["record"]["key_metrics"] == {"accuracy": 0.84}
        assert records[0]["path"].endswith("run_record.json")

    def test_malformed_record_noted_not_fatal(self, tmp_dir):
        _make_project(tmp_dir, run_record="{not json")
        records = _load_run_records(tmp_dir)
        assert len(records) == 1
        assert records[0]["record"] is None
        assert "error" in records[0]

    def test_no_records(self, tmp_dir):
        assert _load_run_records(tmp_dir) == []


class TestExtractClaims:
    def test_single_exec_with_document_text(self, tmp_dir):
        path = os.path.join(tmp_dir, "analysis_main.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Our method reaches 0.84 accuracy.")
        rt = MockRuntime(_j({"claims": [{"claim": "0.84 accuracy",
                                         "numbers": ["0.84"],
                                         "source_hint": "results.csv"}]}))
        reply = extract_claims(paper_or_analysis_path=path, runtime=rt)
        assert len(rt.calls) == 1
        assert "0.84 accuracy" in rt.calls[0]["content"][0]["text"]
        assert json.loads(reply)["claims"][0]["numbers"] == ["0.84"]


class TestIntegrityGate:
    def test_no_sources_passes_without_llm(self, tmp_dir):
        result = integrity_gate(tmp_dir, runtime=None)
        assert result["passed"] is True
        assert result["n_claims"] == 0
        assert result["report_path"] is None

    def test_runtime_required_when_text_exists(self, tmp_dir):
        _make_project(tmp_dir, summary="Accuracy is 0.84.")
        with pytest.raises(ValueError, match="runtime"):
            integrity_gate(tmp_dir, runtime=None)

    def test_pass_with_aligned_claims(self, tmp_dir):
        _make_project(tmp_dir, run_record=RECORD,
                      summary="Accuracy is 0.84 on the test set.",
                      result_csv="epoch,accuracy\n10,0.84\n")
        rt = MockRuntime([
            _j({"claims": [{"claim": "Accuracy is 0.84",
                            "numbers": ["0.84"],
                            "source_hint": "results.csv"}]}),
            # call_with_schema attempts return text (no tool call) and fail;
            # the parse_json fallback consumes this same reply.
            _j({"verdicts": [{"claim": "Accuracy is 0.84",
                              "verdict": "ALIGNED",
                              "evidence": "run_record step1-a1b2 key_metrics.accuracy"}]}),
        ])
        result = integrity_gate(tmp_dir, runtime=rt)
        assert result["passed"] is True
        assert result["n_claims"] == 1
        assert result["failures"] == []
        report = open(result["report_path"], encoding="utf-8").read()
        assert "GATE: PASS" in report
        assert "ALIGNED" in report
        # The judging exec was grounded in the run record + result file
        judge_text = rt.calls[1]["content"][0]["text"]
        assert "step1-a1b2" in judge_text
        assert "results.csv" in judge_text

    def test_fail_with_unsupported_claims(self, tmp_dir):
        _make_project(tmp_dir, run_record=RECORD,
                      summary="Accuracy is 0.84. We improve 30% over GPT-4.")
        rt = MockRuntime([
            _j({"claims": [
                {"claim": "Accuracy is 0.84", "numbers": ["0.84"],
                 "source_hint": "run record"},
                {"claim": "We improve 30% over GPT-4", "numbers": ["30%"],
                 "source_hint": "unknown"},
            ]}),
            _j({"verdicts": [
                {"claim": "Accuracy is 0.84", "verdict": "ALIGNED",
                 "evidence": "key_metrics.accuracy=0.84"},
                {"claim": "We improve 30% over GPT-4", "verdict": "NO_PROVENANCE",
                 "evidence": "no run record mentions GPT-4"},
            ]}),
        ])
        result = integrity_gate(tmp_dir, runtime=rt)
        assert result["passed"] is False
        assert result["n_claims"] == 2
        assert len(result["failures"]) == 1
        assert result["failures"][0]["claim"] == "We improve 30% over GPT-4"
        assert result["failures"][0]["verdict"] == "NO_PROVENANCE"
        report = open(result["report_path"], encoding="utf-8").read()
        assert "GATE: FAIL — 1 claims lack provenance" in report

    def test_unparseable_extraction_passes_empty(self, tmp_dir):
        _make_project(tmp_dir, summary="Nothing numeric here.")
        rt = MockRuntime("no json at all")
        result = integrity_gate(tmp_dir, runtime=rt)
        assert result["passed"] is True
        assert result["n_claims"] == 0
        report = open(result["report_path"], encoding="utf-8").read()
        assert "GATE: PASS" in report


class TestPipelineWiring:
    def _fake_gate(self, calls, result):
        def fake(project_dir, runtime=None):
            calls.append(project_dir)
            return result
        return fake

    def test_gate_called_and_warnings_embedded(self, tmp_dir, monkeypatch):
        import research_harness.stages.integrity as integrity_mod
        from research_harness.pipeline import research_pipeline
        calls = []
        monkeypatch.setattr(integrity_mod, "integrity_gate", self._fake_gate(
            calls,
            {"passed": False, "n_claims": 1,
             "failures": [{"claim": "Fake 99% accuracy",
                           "verdict": "NO_PROVENANCE"}],
             "report_path": os.path.join(tmp_dir, "INTEGRITY_REPORT.md")},
        ))
        rt = MockRuntime("mock section text")
        results = research_pipeline(project_dir=tmp_dir, stages=["writing"],
                                    exec_runtime=rt)
        assert calls == [tmp_dir]
        assert results["integrity_gate"]["passed"] is False
        warn_path = os.path.join(tmp_dir, "INTEGRITY_WARNINGS.md")
        assert os.path.exists(warn_path)
        warn = open(warn_path, encoding="utf-8").read()
        assert "Fake 99% accuracy" in warn
        # Every write_section context embeds the warnings
        assert rt.calls
        for call in rt.calls:
            text = call["content"][0]["text"]
            assert "Integrity warnings" in text
            assert "Fake 99% accuracy" in text

    def test_gate_pass_writes_no_warnings(self, tmp_dir, monkeypatch):
        import research_harness.stages.integrity as integrity_mod
        from research_harness.pipeline import research_pipeline
        calls = []
        monkeypatch.setattr(integrity_mod, "integrity_gate", self._fake_gate(
            calls, {"passed": True, "n_claims": 2, "failures": [],
                    "report_path": None},
        ))
        rt = MockRuntime("mock section text")
        results = research_pipeline(project_dir=tmp_dir, stages=["writing"],
                                    exec_runtime=rt)
        assert calls == [tmp_dir]
        assert results["integrity_gate"]["passed"] is True
        assert not os.path.exists(os.path.join(tmp_dir, "INTEGRITY_WARNINGS.md"))
        assert "Integrity warnings" not in rt.calls[0]["content"][0]["text"]

    def test_gate_error_does_not_block_writing(self, tmp_dir, monkeypatch):
        import research_harness.stages.integrity as integrity_mod
        from research_harness.pipeline import research_pipeline

        def boom(project_dir, runtime=None):
            raise RuntimeError("gate exploded")

        monkeypatch.setattr(integrity_mod, "integrity_gate", boom)
        rt = MockRuntime("mock section text")
        results = research_pipeline(project_dir=tmp_dir, stages=["writing"],
                                    exec_runtime=rt)
        assert results["integrity_gate"]["passed"] is None
        assert "gate exploded" in results["integrity_gate"]["error"]
        # writing still produced the paper sections
        assert os.path.exists(os.path.join(tmp_dir, "paper",
                                           "1Introduction.tex"))
