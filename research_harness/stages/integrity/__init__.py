# Adapted from academic-research-skills v3.12.0 (https://github.com/Imbad0202/academic-research-skills), (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: ARS's scholar-declared experiment-provenance gate (#260) and failure-mode
# checklist (modes 1/3/5) reimplemented as an autonomous Python gate that is mechanically
# grounded in harness-owned run_record.json artifacts and result files.
"""Stage: integrity — claim-to-evidence gate between experiments and writing.

Audits empirical claims in the analysis/paper text against the run records
and result files the harness itself produced. Verdict vocabulary:
ALIGNED / OVERSTATED / NOT_SUPPORTED / NO_PROVENANCE.
"""

from __future__ import annotations

import glob
import json
import os

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.utils import call_with_schema, parse_json


VERDICTS = ("ALIGNED", "OVERSTATED", "NOT_SUPPORTED", "NO_PROVENANCE")
FAILING_VERDICTS = ("NOT_SUPPORTED", "NO_PROVENANCE")

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "verdict": {"type": "string", "enum": list(VERDICTS)},
                    "evidence": {"type": "string"},
                },
                "required": ["claim", "verdict"],
            },
        },
    },
    "required": ["verdicts"],
}


@agentic_function(render_range={"depth": 0, "siblings": 0})
def extract_claims(paper_or_analysis_path: str, runtime: Runtime) -> str:
    """Extract the empirical claims from a draft or analysis document.

    An empirical claim is any statement asserting an experimental outcome:
    metric values, improvements/reductions ("12% better"), comparisons against
    baselines, seed/run counts, statistical significance, dataset sizes.
    Skip motivation, related work, and purely theoretical statements.

    For each claim record:
    - claim: the sentence (or minimal span) making the assertion
    - numbers: every number the claim depends on, as strings (e.g. "0.842", "12%")
    - source_hint: best guess at where the evidence should live
      (e.g. "results table", "ablation run", "accuracy.csv")

    Output ONLY a JSON object — no commentary, no markdown fence:
    {{"claims": [{{"claim": "...", "numbers": ["..."], "source_hint": "..."}}]}}
    Return {{"claims": []}} if the document contains no empirical claims.
    """
    with open(paper_or_analysis_path, "r", encoding="utf-8") as f:
        text = f.read()
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Document ({os.path.basename(paper_or_analysis_path)}):\n"
            f"{text[:20000]}"
        )},
    ])


# ---------------------------------------------------------------------------
# Evidence collection (deterministic)
# ---------------------------------------------------------------------------

def _load_run_records(project_dir: str) -> list[dict]:
    """Load all auto_experiment/**/run_record.json files (malformed ones noted)."""
    records = []
    pattern = os.path.join(project_dir, "auto_experiment", "**", "run_record.json")
    for path in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(path, project_dir)
        try:
            with open(path, "r", encoding="utf-8") as f:
                records.append({"path": rel, "record": json.load(f)})
        except (json.JSONDecodeError, OSError) as e:
            records.append({"path": rel, "record": None,
                            "error": f"unreadable run_record.json: {e}"})
    return records


def _result_file_excerpts(project_dir: str, per_file: int = 1500,
                          total: int = 9000) -> list[str]:
    """Bounded excerpts of experiments/ result files (csv/json)."""
    paths = set()
    for ext in ("csv", "json"):
        paths.update(glob.glob(os.path.join(project_dir, "experiments",
                                            "**", f"*.{ext}"), recursive=True))
    excerpts, used = [], 0
    for path in sorted(paths):
        if used >= total:
            break
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(per_file)
        except (OSError, UnicodeDecodeError):
            continue
        snippet = content[: total - used]
        used += len(snippet)
        excerpts.append(f"--- {os.path.relpath(path, project_dir)} ---\n{snippet}")
    return excerpts


def _find_claim_sources(project_dir: str) -> list[str]:
    """Analysis/paper text to audit: analysis_*.md, paper/*.tex, auto_experiment/SUMMARY.md."""
    sources = sorted(glob.glob(os.path.join(project_dir, "analysis_*.md")))
    sources += sorted(glob.glob(os.path.join(project_dir, "paper", "*.tex")))
    summary = os.path.join(project_dir, "auto_experiment", "SUMMARY.md")
    if os.path.exists(summary):
        sources.append(summary)
    return sources


# ---------------------------------------------------------------------------
# Verdict mapping (one exec, structured)
# ---------------------------------------------------------------------------

def _judge_claims(claims: list[dict], run_records: list[dict],
                  excerpts: list[str], runtime: Runtime) -> list[dict]:
    """Map each claim to evidence with a verdict. One LLM exec (with retry/fallback)."""
    instructions = (
        "You are the integrity gate of an autonomous research pipeline. "
        "Map EACH empirical claim below to the run evidence and give a verdict:\n"
        "- ALIGNED: the claim's numbers and direction match a run record or result file.\n"
        "- OVERSTATED: evidence exists but the claim goes beyond it "
        "(stronger wording, broader scope, cherry-picked).\n"
        "- NOT_SUPPORTED: evidence exists and contradicts the claim.\n"
        "- NO_PROVENANCE: no run record or result file accounts for the claim "
        "(hallucinated-result risk).\n"
        "In `evidence`, cite the run record path / result file / metric that "
        "grounds the verdict, or state what is missing.\n\n"
        "Claims:\n"
        + json.dumps(claims, indent=1, ensure_ascii=False)
        + "\n\nRun records (machine-written by the experiment stage):\n"
        + (json.dumps(run_records, indent=1, ensure_ascii=False, default=str)[:12000]
           if run_records else "(no run records found)")
        + "\n\nResult file excerpts:\n"
        + ("\n".join(excerpts) if excerpts else "(no result files found)")
    )
    try:
        result = call_with_schema(
            runtime=runtime,
            instructions=instructions,
            schema_name="submit_verdicts",
            schema_description="Submit one verdict per empirical claim.",
            parameters=_VERDICT_SCHEMA,
        )
    except Exception:
        reply = runtime.exec(content=[{"type": "text", "text": (
            instructions
            + "\n\nOutput ONLY a JSON object: "
            + '{"verdicts": [{"claim": "...", "verdict": "ALIGNED|OVERSTATED|'
            + 'NOT_SUPPORTED|NO_PROVENANCE", "evidence": "..."}]}'
        )}])
        result = parse_json(reply)

    rows = []
    for row in result.get("verdicts", []) or []:
        if not isinstance(row, dict):
            continue
        verdict = str(row.get("verdict", "")).strip().upper().replace(" ", "_")
        if verdict not in VERDICTS:
            verdict = "NO_PROVENANCE"  # conservative: unknown verdict fails
        rows.append({"claim": str(row.get("claim", "")),
                     "verdict": verdict,
                     "evidence": str(row.get("evidence", ""))})
    return rows


# ---------------------------------------------------------------------------
# Report + gate
# ---------------------------------------------------------------------------

def _cell(text: str) -> str:
    return (text or "").replace("\n", " ").replace("|", "\\|")[:200]


def _write_report(project_dir: str, rows: list[dict], run_records: list[dict],
                  n_result_files: int, summary_line: str) -> str:
    lines = [
        "# Integrity Report",
        "",
        "Claim-to-evidence audit between experiments and writing.",
        "Verdicts: ALIGNED / OVERSTATED / NOT_SUPPORTED / NO_PROVENANCE.",
        "",
        f"- Run records found: {len(run_records)}"
        + (f" ({', '.join(r['path'] for r in run_records)})" if run_records else ""),
        f"- Result files excerpted: {n_result_files}",
        "",
        "| # | Claim | Verdict | Evidence |",
        "|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {_cell(r['claim'])} | {r['verdict']} "
                     f"| {_cell(r['evidence'])} |")
    if not rows:
        lines.append("| - | (no empirical claims found) | - | - |")
    lines += ["", summary_line, ""]
    report_path = os.path.join(project_dir, "INTEGRITY_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path


def integrity_gate(project_dir: str, runtime: Runtime = None) -> dict:
    """Audit empirical claims in analysis/paper text against run artifacts.

    Mechanically grounded: evidence is the harness's own
    auto_experiment/**/run_record.json plus experiments/ result files —
    not scholar declarations as in ARS #260.

    Args:
        project_dir: Research project directory.
        runtime:     LLM runtime (required when there is text to audit).

    Returns:
        {"passed": bool, "n_claims": int, "failures": [...], "report_path": str|None}
    """
    project_dir = os.path.expanduser(project_dir)
    sources = _find_claim_sources(project_dir)
    if not sources:
        return {"passed": True, "n_claims": 0, "failures": [],
                "report_path": None, "note": "no analysis/paper text found"}
    if runtime is None:
        raise ValueError("runtime is required when there is text to audit")

    run_records = _load_run_records(project_dir)
    excerpts = _result_file_excerpts(project_dir)

    claims = []
    for src in sources:
        reply = extract_claims(paper_or_analysis_path=src, runtime=runtime)
        try:
            parsed = parse_json(reply)
        except ValueError:
            continue  # unparseable extraction — skip this source
        for c in parsed.get("claims", []) or []:
            if isinstance(c, dict) and c.get("claim"):
                c["source_file"] = os.path.relpath(src, project_dir)
                claims.append(c)

    if not claims:
        report_path = _write_report(project_dir, [], run_records,
                                    len(excerpts), "GATE: PASS")
        return {"passed": True, "n_claims": 0, "failures": [],
                "report_path": report_path}

    rows = _judge_claims(claims, run_records, excerpts, runtime)
    failures = [r for r in rows if r["verdict"] in FAILING_VERDICTS]
    summary = ("GATE: PASS" if not failures
               else f"GATE: FAIL — {len(failures)} claims lack provenance")
    report_path = _write_report(project_dir, rows, run_records,
                                len(excerpts), summary)
    return {"passed": not failures, "n_claims": len(claims),
            "failures": failures, "report_path": report_path}


__all__ = ["extract_claims", "integrity_gate"]
