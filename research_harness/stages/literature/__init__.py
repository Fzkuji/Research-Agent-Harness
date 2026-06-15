"""Stage: literature.

`run_literature` is a single-step loop that repeatedly asks an LLM to
pick the next best action from a fixed set, dispatches to the
corresponding leaf function, and merges the result into a growing
`state` dict. It exits when the synthesis step succeeds (or a hard
iteration cap is reached).

State is kept in-memory during a run and flushed to
`<output_dir>/state.json` after every step so partial runs can be
inspected / resumed.

File layout (this package):
  - `__init__.py`      — orchestrator + re-exports (this file)
  - `_state.py`        — state schema, IO, slug, paper_id, framework
                         walks, count summaries
  - `_artifacts.py`    — md writers, bibliography, citation audit,
                         empty-leaf prune, dispatcher state summary
  - `_actions.py`      — catalog + decide LLM, per-action mergers,
                         dispatcher (incl. batched annotate)
  - `seed_surveys.py`         — leaf @agentic_function
  - `extract_framework.py`    — leaf @agentic_function
  - `search_papers_for_topic.py` — leaf @agentic_function
  - `annotate_papers.py`      — leaf @agentic_function
  - `evolve_framework.py`     — leaf @agentic_function
  - `synthesize_literature.py` — leaf @agentic_function
  - `search/arxiv.py` / `search/semantic_scholar.py` — search backends
  - `tools/survey_topic.py` / `tools/identify_gaps.py` /
    `tools/comprehensive_lit_review.py` — older standalone helpers,
    NOT driven by the loop

See README.md for the pipeline narrative.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from openprogram.agentic_programming.runtime import Runtime
from openprogram.agentic_programming.decision import (
    extract_action,
)

from research_harness.stages.literature.annotate_papers import (
    annotate_papers,
)
from research_harness.stages.literature.evolve_framework import (
    evolve_framework,
)
from research_harness.stages.literature.extract_framework import (
    extract_framework,
)
from research_harness.stages.literature.search_papers_for_topic import (
    search_papers_for_topic,
)
from research_harness.stages.literature.seed_surveys import seed_surveys
from research_harness.stages.literature.digest_paper import digest_paper
from research_harness.stages.literature.synthesize_literature import (
    synthesize_literature,
)
from research_harness.stages.literature.search import (
    search_arxiv,
    search_semantic_scholar,
)

from research_harness.stages.literature._state import (
    _leaf_count,
    _load_or_init_state,
    _orphan_count,
    _paper_id,
    _safe_parse,
    _save_state,
    _section3_leaves,
    _section3_leaves_md,
    _unannotated_count,
)
from research_harness.stages.literature._artifacts import (
    _audit_citations,
    _build_state_summary,
    _flush_artifacts,
    _framework_preview,
    _render_bibliography,
    _splice_bibliography_into_review,
)
from research_harness.stages.literature._actions import (
    _dispatch,
    _lit_decide,
    _merge_annotate,
    _merge_digest_paper,
    _merge_evolve,
    _merge_extract_framework,
    _merge_search_papers,
    _merge_seed_surveys,
)
from research_harness.stages.literature.evolve_framework import (
    evolve_framework as _evolve_framework_leaf,
)
from research_harness.stages.literature.synthesize_literature import (
    synthesize_literature as _synthesize_literature_leaf,
)


_DEFAULT_MAX_OUTER = 8
# Zero-progress early stop: if this many consecutive outer cycles end with
# the framework gaining nothing (no_delta_streak — every compensation
# evolve applied 0 deltas), the loop is spinning (e.g. seed_surveys keeps
# returning nothing because retrieval is dry / the model won't produce
# usable data). Stop instead of burning all max_outer*max_inner steps.
_MAX_NO_DELTA_STREAK = 2


def _audit_section3_headings(review_path: Path,
                             expected_leaves: list) -> list[str]:
    """Compare §3 subsection headings in review.md against the
    authoritative leaf list. Returns list of human-readable mismatch
    strings (extras / missing / order). Empty list = clean."""
    import re
    if not review_path.exists():
        return []
    text = review_path.read_text(encoding="utf-8")
    # Slice §3 region: from "## 3. ..." up to next "## " heading.
    m = re.search(r"(?m)^##\s+3\.\s+[^\n]*$", text)
    if not m:
        return ["§3 heading not found in review.md"]
    rest = text[m.end():]
    n = re.search(r"(?m)^##\s+\d", rest)
    s3_text = rest if not n else rest[:n.start()]
    # Collect all nested headings inside §3 (### / #### / #####, with
    # numbered prefix like 3.1, 3.2.1, 3.2.1.1, ...).
    found = re.findall(
        r"(?m)^#{3,6}\s+3(?:\.\d+)+\s+(.+?)\s*$", s3_text,
    )
    f_set = set(found)
    expected = [name for name, _path, _n in expected_leaves]
    out: list[str] = []
    for miss in [x for x in expected if x not in f_set]:
        out.append(f"missing §3 leaf heading: {miss!r}")
    return out
_DEFAULT_MAX_INNER = 10


# ═══════════════════════════════════════════════════════════════════════
# Output directory derivation
# ═══════════════════════════════════════════════════════════════════════

def _derive_project_name(direction: str) -> str:
    """Turn a research direction into a short, readable folder name."""
    import re as _re
    clean = _re.sub(r"[\r\n]+", " ", (direction or "").strip())
    clean = _re.sub(r"[/:\\]", " ", clean)
    words = clean.split()[:6] or ["research"]
    return " ".join(words).strip() or "research"


def _resolve_output_dir(output_dir: str | None,
                        direction: str) -> str:
    """Resolve output_dir to an absolute path.

    - Absolute path → use as-is.
    - Relative path → join under ~/Documents/.
    - None → ~/Documents/<project_name>/literature review.
    """
    if output_dir:
        return os.path.abspath(os.path.expanduser(output_dir))
    project = _derive_project_name(direction)
    return os.path.abspath(
        os.path.expanduser(
            f"~/Documents/{project}/literature review"
        )
    )


# ═══════════════════════════════════════════════════════════════════════
# End-of-cycle / end-of-run hooks
# ═══════════════════════════════════════════════════════════════════════

def _run_compensation_evolve(state: dict, direction: str,
                             output_dir: str, runtime: Runtime,
                             outer_no: int) -> None:
    """End-of-cycle compensation: run evolve_framework once.

    The inner loop tends to favor search/annotate; this guarantees
    the topic tree gets restructured at least once per outer cycle.
    """
    state["iter"] = state.get("iter", 0) + 1
    i = state["iter"]
    framework_json = json.dumps(
        state["framework"] or {}, ensure_ascii=False,
    )
    papers_json = json.dumps(
        [
            {
                "id": _paper_id(p),
                "title": p.get("title", ""),
                "placements": p.get("placements", []),
                "is_orphan": p.get("is_orphan", False),
                "orphan_suggested_topic": p.get(
                    "orphan_suggested_topic"),
            }
            for p in state["papers"]
        ],
        ensure_ascii=False,
    )
    surveys_json = json.dumps(state["surveys"], ensure_ascii=False)
    audit_tail = "\n".join(
        f"iter {a.get('iter','?')}: "
        f"{a.get('action','?')} — {a.get('summary','')}"
        for a in state["audit"][-8:]
    )
    try:
        text = _evolve_framework_leaf(
            framework_json=framework_json, papers_json=papers_json,
            surveys_json=surveys_json, audit_tail=audit_tail,
            runtime=runtime,
        )
    except Exception as e:  # noqa: BLE001
        state["audit"].append({
            "iter": i, "action": "evolve_framework",
            "changed": 0, "summary": f"compensation error: {e}",
        })
        print(
            f"    [literature/{outer_no}.evolve] ERROR: {e}",
            file=sys.stderr,
        )
        return
    parsed = _safe_parse(text)
    changed, summary = _merge_evolve(state, parsed)
    state["audit"].append({
        "iter": i, "action": "evolve_framework",
        "reasoning": "end-of-cycle compensation",
        "changed": changed, "summary": summary,
    })
    print(
        f"    [literature/{outer_no}.evolve] {summary[:80]}",
        file=sys.stderr,
    )


def _run_final_synthesize(state: dict, direction: str,
                          output_dir: str,
                          runtime: Runtime) -> tuple[dict, bool]:
    """End-of-run finalization: run synthesize_literature once.

    Writes the synthesis deliverable. Splice + audit run regardless of
    whether the LLM call succeeded — the model may have written
    review.md to disk via a tool call before dying on a parse error.
    """
    state["iter"] = state.get("iter", 0) + 1
    i = state["iter"]
    s3_leaves = _section3_leaves(state)
    print(
        f"    [literature/finalize] synthesize "
        f"(§3 leaves={len(s3_leaves)}; section-by-section)",
        file=sys.stderr,
    )
    parsed: dict = {}
    synthesize_error: Exception | None = None
    try:
        parsed = _synthesize_literature_leaf(
            direction=direction, state=state,
            output_dir=output_dir, runtime=runtime,
        ) or {}
    except Exception as e:  # noqa: BLE001
        synthesize_error = e
        print(
            f"    [literature/finalize] WARNING: synthesize raised "
            f"{type(e).__name__}: {e}; checking disk anyway.",
            file=sys.stderr,
        )

    done = bool(parsed.get("done"))

    review_path = Path(output_dir) / "synthesis" / "review.md"
    bib_md = _render_bibliography(state)
    spliced = _splice_bibliography_into_review(
        review_path, bib_md, state,
    )
    if spliced:
        print(
            f"    [literature/finalize] spliced programmatic bib into "
            f"review.md ({len(state.get('papers', []))} papers, "
            f"{len(state.get('surveys', []))} surveys)",
            file=sys.stderr,
        )
    else:
        print(
            f"    [literature/finalize] WARNING: review.md not found "
            f"at {review_path}; bibliography not spliced. Check the "
            f"LLM output.",
            file=sys.stderr,
        )

    s3_warnings = _audit_section3_headings(review_path, s3_leaves)
    if s3_warnings:
        print(
            f"    [literature/finalize] §3 adherence: "
            f"{len(s3_warnings)} mismatch(es):",
            file=sys.stderr,
        )
        for w in s3_warnings:
            print(f"      {w}", file=sys.stderr)

    cite_warnings = _audit_citations(state, output_dir)
    if cite_warnings:
        print(
            f"    [literature/finalize] citation audit: "
            f"{len(cite_warnings)} unknown arXiv IDs in review.md:",
            file=sys.stderr,
        )
        for w in cite_warnings[:20]:
            print(w, file=sys.stderr)
        audit_path = (
            Path(output_dir) / "synthesis" / "_citation_audit.md"
        )
        audit_path.write_text(
            "# Citation audit\n\n"
            "These arXiv IDs appear in review.md (sections 1-5) but "
            "are not in the literature state (state.json papers / "
            "surveys). They may be hallucinations, or references to "
            "important work the search step missed. Verify and "
            "either fetch the paper or remove the citation.\n\n"
            + "\n".join(cite_warnings)
            + "\n",
            encoding="utf-8",
        )

    if synthesize_error is not None:
        if spliced:
            summary = (
                f"synthesize raised {type(synthesize_error).__name__} "
                f"({synthesize_error}) but review.md was written; "
                f"bib spliced; audit ran"
            )
            done = True  # treat as successful enough — file exists
        else:
            summary = f"error: {synthesize_error}"
    else:
        summary = "synthesis complete" if done else (
            "synthesize did not return done=true; "
            + (
                ("error: " + parsed.get("error", "?"))
                if parsed else "parse failed"
            )
        )

    state["audit"].append({
        "iter": i, "action": "synthesize",
        "changed": 1 if done else 0,
        "summary": summary,
    })
    return parsed, done


# ═══════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════

def run_literature(
    direction: str,
    output_dir: str = None,
    runtime: Runtime = None,
    max_outer: int = _DEFAULT_MAX_OUTER,
    max_inner: int = _DEFAULT_MAX_INNER,
) -> dict:
    """Iteratively build a literature review via a two-level loop.

    Structure:
      for outer in 1..max_outer:
        for inner in 1..max_inner:
          LLM picks ONE action from {seed_surveys, extract_framework,
          search_papers, annotate_papers, evolve_framework, done}.
          Leaf runs, result merged into state.
          If action="done" (scope=cycle): break inner.
          If action="done" (scope=all):   break inner AND outer.
        end-of-cycle compensation: evolve_framework (unconditional).
      end-of-run finalization: synthesize_literature (unconditional).

    Args:
        direction:  Research direction / project descriptor.
        output_dir: Absolute directory. Same output_dir → resume.
        runtime:    LLM runtime (required).
        max_outer:  Hard cap on outer cycles.
        max_inner:  Hard cap on inner steps per cycle.

    Returns:
        dict with direction, iterations, stats, framework, output_dir,
        done.
    """
    if runtime is None:
        raise ValueError(
            "run_literature() requires a runtime argument"
        )

    output_dir = _resolve_output_dir(output_dir, direction)
    os.makedirs(output_dir, exist_ok=True)
    state = _load_or_init_state(output_dir, direction)

    synth_result: dict = {}
    done = False
    stop_all = False

    for outer in range(1, max_outer + 1):
        state["outer"] = outer

        for inner in range(1, max_inner + 1):
            state["iter"] = state.get("iter", 0) + 1
            i = state["iter"]

            state_summary = _build_state_summary(state)
            framework_preview = _framework_preview(state)

            reply = _lit_decide(
                direction=direction, state_summary=state_summary,
                framework_preview=framework_preview, runtime=runtime,
            )

            parsed_action = (
                extract_action(reply) if isinstance(reply, str)
                else None
            )
            if parsed_action is None:
                action = ""
                args = {}
            else:
                action = (parsed_action.get("call") or "").strip()
                args = parsed_action.get("args") or {}
            reasoning = ""

            if not action:
                state["audit"].append({
                    "iter": i, "action": "<none>",
                    "summary": (
                        f"decision parse failed: {str(reply)[:120]}"
                    ),
                })
                _save_state(output_dir, state)
                _flush_artifacts(state, output_dir, i)
                print(
                    f"    [literature/{outer}.{inner}] PARSE_FAIL",
                    file=sys.stderr,
                )
                continue

            if action == "done":
                scope = (
                    args.get("scope") or "cycle"
                ).strip().lower()
                if scope == "all":
                    stop_all = True
                state["audit"].append({
                    "iter": i, "action": "done",
                    "reasoning": reasoning, "changed": 0,
                    "summary": f"LLM done (scope={scope})",
                })
                _save_state(output_dir, state)
                _flush_artifacts(state, output_dir, i)
                print(
                    f"    [literature/{outer}.{inner}] done "
                    f"scope={scope}  ({reasoning[:80]})",
                    file=sys.stderr,
                )
                break

            print(
                f"    [literature/{outer}.{inner}] {action}  "
                f"({reasoning[:80]})",
                file=sys.stderr,
            )

            text, parsed = _dispatch(
                action, args, state, direction, output_dir, runtime,
            )

            if "error" in parsed and len(parsed) == 1:
                summary = f"dispatch error: {parsed['error']}"
                changed = 0
            elif action == "seed_surveys":
                changed, summary = _merge_seed_surveys(state, parsed)
            elif action == "extract_framework":
                changed, summary = _merge_extract_framework(
                    state, parsed,
                )
            elif action == "search_papers":
                changed, summary = _merge_search_papers(state, parsed)
            elif action == "annotate_papers":
                changed, summary = _merge_annotate(state, parsed)
            elif action == "evolve_framework":
                changed, summary = _merge_evolve(state, parsed)
            elif action == "digest_paper":
                changed, summary = _merge_digest_paper(state, parsed)
            else:
                changed = 0
                summary = f"unknown action: {action}"

            state["audit"].append({
                "iter": i, "action": action,
                "reasoning": reasoning,
                "changed": changed, "summary": summary,
            })
            _save_state(output_dir, state)
            _flush_artifacts(state, output_dir, i)

        # End-of-cycle compensation (always runs)
        _run_compensation_evolve(
            state, direction, output_dir, runtime, outer,
        )
        _save_state(output_dir, state)
        _flush_artifacts(state, output_dir, state["iter"])

        if stop_all:
            break

        # Zero-progress early stop: consecutive outer cycles that add
        # nothing to the framework mean the loop is spinning (dry
        # retrieval, a model that won't return usable data). Stop and let
        # final synthesis run on whatever was gathered, instead of burning
        # every remaining cycle re-trying the same dead action.
        if state.get("no_delta_streak", 0) >= _MAX_NO_DELTA_STREAK:
            print(
                f"    [literature] no-progress streak "
                f"{state['no_delta_streak']} >= {_MAX_NO_DELTA_STREAK} "
                f"after cycle {outer} — stopping early.",
                file=sys.stderr,
            )
            break

    # End-of-run finalization
    synth_result, done = _run_final_synthesize(
        state, direction, output_dir, runtime,
    )
    _save_state(output_dir, state)
    _flush_artifacts(state, output_dir, state["iter"], done=done)

    return {
        "direction": direction,
        "output_dir": output_dir,
        "iterations": state["iter"],
        "done": done,
        "framework": state["framework"],
        "stats": {
            "surveys": len(state["surveys"]),
            "papers": len(state["papers"]),
            "leaves": _leaf_count(state["framework"]),
            "orphans": _orphan_count(state),
            "unannotated": _unannotated_count(state),
        },
        "synthesis": synth_result,
    }


__all__ = [
    'annotate_papers',
    'digest_paper',
    'evolve_framework',
    'extract_framework',
    'run_literature',
    'search_arxiv',
    'search_papers_for_topic',
    'search_semantic_scholar',
    'seed_surveys',
    'synthesize_literature',
]
