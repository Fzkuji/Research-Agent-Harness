"""Stage: literature.

`run_literature` is a single-step loop that repeatedly asks an LLM to pick
the next best action from a fixed set, dispatches to the corresponding leaf
function, and merges the result into a growing state. It exits when the
synthesis step succeeds (or a hard iteration cap is reached).

State is kept in-memory during a run and flushed to `<output_dir>/state.json`
after every step so partial runs can be inspected / resumed.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from agentic.function import agentic_function
from agentic.runtime import Runtime

from research_harness.stages.literature.annotate_papers import annotate_papers
from research_harness.stages.literature.comprehensive_lit_review import comprehensive_lit_review
from research_harness.stages.literature.evolve_framework import evolve_framework
from research_harness.stages.literature.extract_framework import extract_framework
from research_harness.stages.literature.identify_gaps import identify_gaps
from research_harness.stages.literature.search_arxiv import search_arxiv
from research_harness.stages.literature.search_papers_for_topic import search_papers_for_topic
from research_harness.stages.literature.search_semantic_scholar import search_semantic_scholar
from research_harness.stages.literature.seed_surveys import seed_surveys
from research_harness.stages.literature.survey_topic import survey_topic
from research_harness.stages.literature.synthesize_literature import synthesize_literature
from research_harness.utils import parse_json


# ═══════════════════════════════════════════════════════════════════════════
# Dispatcher — LLM picks the next action
# ═══════════════════════════════════════════════════════════════════════════

_DISPATCH_PROMPT = """You are driving a literature-review loop. Each turn you pick ONE
action from the list below. The orchestrator executes it and feeds the result
back into state.

Available actions (pick exactly one):

  seed_surveys        find survey papers → add to state.surveys
                      args: {{ "query": str (default=direction),
                               "k": int (default=3) }}

  extract_framework   from surveys + your knowledge, build/refresh topic tree
                      args: {{}}  (consumes state.surveys + state.framework)

  search_papers       find NEW papers under a specific topic (uses framework)
                      args: {{ "topic_path": "a/b/c",
                               "k": int (default=5) }}

  annotate_papers     assign topic_path + write contribution_summary for papers
                      that are not yet annotated
                      args: {{}}  (picks all unannotated papers)

  evolve_framework    refactor the topic tree based on accumulated evidence
                      args: {{}}

  synthesize          write the final deliverables (framework, topic reviews,
                      synthesis, gaps, ideas, bibliography). Marks stage done.
                      args: {{}}

Rules for picking:
- Cold start (no surveys): seed_surveys.
- Have surveys, no framework: extract_framework.
- Framework exists, leaves thin (<5 papers) and not yet searched: search_papers
  for the leaf that needs coverage most.
- Papers with annotated=false: annotate_papers.
- Orphan papers or a leaf >15 papers or a long streak of untouched evolution:
  evolve_framework.
- Framework hasn't changed meaningfully in ≥3 rounds AND every leaf has ≥5
  annotated papers AND no orphans remain: synthesize.
- If none of the above fits, pick the action that most reduces the biggest
  remaining weakness. Explain in `reasoning`.

Output format — return ONE JSON object, nothing else:
```json
{{
  "action": "<one of the actions above>",
  "action_args": {{ ... }},
  "reasoning": "why this action, now",
  "expect": "what the state should look like after this action"
}}
```

Research direction:
{direction}

State summary:
{state_summary}

Current framework (truncated):
{framework_preview}
"""


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def _lit_decide(direction: str, state_summary: str, framework_preview: str,
                runtime: Runtime) -> str:
    """Ask the LLM which action to execute next. Returns raw JSON text."""
    return runtime.exec(content=[
        {"type": "text", "text": _DISPATCH_PROMPT.format(
            direction=direction,
            state_summary=state_summary,
            framework_preview=framework_preview or "(no framework yet)",
        )},
    ])


# ═══════════════════════════════════════════════════════════════════════════
# State helpers
# ═══════════════════════════════════════════════════════════════════════════

def _init_state(direction: str) -> dict:
    return {
        "direction": direction,
        "surveys": [],
        "papers": [],
        "framework": None,
        "audit": [],
        "iter": 0,
        "no_delta_streak": 0,
    }


def _load_or_init_state(output_dir: str, direction: str) -> dict:
    path = os.path.join(output_dir, "state.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state.get("direction") == direction:
                return state
        except (OSError, json.JSONDecodeError):
            pass
    return _init_state(direction)


def _save_state(output_dir: str, state: dict) -> None:
    path = os.path.join(output_dir, "state.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _leaf_count(node: dict | None) -> int:
    if not node:
        return 0
    children = node.get("children") or []
    if not children:
        return 1
    return sum(_leaf_count(c) for c in children)


def _iter_leaves(node: dict | None, prefix: str = ""):
    if not node:
        return
    path = f"{prefix}/{node.get('name', '')}".strip("/")
    children = node.get("children") or []
    if not children:
        yield path, node
        return
    for c in children:
        yield from _iter_leaves(c, path)


def _papers_per_topic(state: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in state["papers"]:
        for pl in p.get("placements", []):
            tp = pl.get("topic_path", "")
            counts[tp] = counts.get(tp, 0) + 1
    return counts


def _unannotated_count(state: dict) -> int:
    return sum(1 for p in state["papers"] if not p.get("annotated"))


def _orphan_count(state: dict) -> int:
    return sum(1 for p in state["papers"] if p.get("is_orphan"))


def _build_state_summary(state: dict) -> str:
    surveys = state["surveys"]
    papers = state["papers"]
    framework = state["framework"]
    audit_tail = state["audit"][-6:]

    lines = [
        f"iteration: {state['iter']}",
        f"surveys: {len(surveys)}",
    ]
    for s in surveys[:8]:
        lines.append(f"  - {s.get('title','?')[:80]} ({s.get('year','?')})")
    if len(surveys) > 8:
        lines.append(f"  ... and {len(surveys) - 8} more")

    lines.append(f"papers: {len(papers)} total, {_unannotated_count(state)} unannotated, "
                 f"{_orphan_count(state)} orphans")

    if framework:
        leaves = list(_iter_leaves(framework))
        counts = _papers_per_topic(state)
        lines.append(f"framework: {_leaf_count(framework)} leaves")
        thin = [(path, counts.get(path, 0)) for path, _ in leaves if counts.get(path, 0) < 5]
        if thin:
            lines.append("  thin leaves (<5 papers):")
            for path, n in thin[:10]:
                lines.append(f"    - {path}  ({n} papers)")
        heavy = [(path, counts.get(path, 0)) for path, _ in leaves if counts.get(path, 0) >= 15]
        if heavy:
            lines.append("  heavy leaves (>=15 papers, candidate for split):")
            for path, n in heavy[:5]:
                lines.append(f"    - {path}  ({n} papers)")
    else:
        lines.append("framework: (none yet)")

    lines.append(f"no_delta_streak: {state.get('no_delta_streak', 0)} "
                 "(consecutive evolve rounds with no non-trivial change)")

    if audit_tail:
        lines.append("recent audit:")
        for a in audit_tail:
            lines.append(f"  - iter {a.get('iter','?')}: {a.get('action','?')} — {a.get('summary','')[:100]}")

    return "\n".join(lines)


def _framework_preview(state: dict, max_chars: int = 2000) -> str:
    fw = state["framework"]
    if not fw:
        return ""
    text = json.dumps(fw, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        return text[:max_chars] + "\n... [truncated]"
    return text


def _safe_parse(text: Any) -> dict:
    if not isinstance(text, str):
        return {}
    try:
        return parse_json(text)
    except ValueError:
        return {}


def _paper_id(p: dict) -> str:
    return p.get("id") or p.get("arxiv_id") or p.get("doi") or p.get("title", "")


# ═══════════════════════════════════════════════════════════════════════════
# Per-action merge logic
# ═══════════════════════════════════════════════════════════════════════════

def _merge_seed_surveys(state: dict, parsed: dict) -> tuple[int, str]:
    new = parsed.get("surveys") or []
    existing_ids = {s.get("id") for s in state["surveys"]}
    existing_titles = {(s.get("title") or "").strip().lower() for s in state["surveys"]}
    added = 0
    for s in new:
        sid = s.get("id")
        title_key = (s.get("title") or "").strip().lower()
        if (sid and sid in existing_ids) or (title_key and title_key in existing_titles):
            continue
        state["surveys"].append(s)
        existing_ids.add(sid)
        existing_titles.add(title_key)
        added += 1
    return added, f"added {added} new surveys (total {len(state['surveys'])})"


def _merge_extract_framework(state: dict, parsed: dict) -> tuple[int, str]:
    fw = parsed.get("framework")
    if not fw:
        return 0, "no framework returned"
    state["framework"] = fw
    return 1, f"framework set ({_leaf_count(fw)} leaves)"


def _merge_search_papers(state: dict, parsed: dict) -> tuple[int, str]:
    new = parsed.get("papers") or []
    existing_ids = {_paper_id(p) for p in state["papers"]}
    added = 0
    pdf_count = 0
    html_count = 0
    for p in new:
        pid = p.get("id")
        if pid and pid in existing_ids:
            continue
        pdf_path = p.get("pdf_path") or None
        excerpt = p.get("context_excerpt") or None
        if pdf_path:
            pdf_count += 1
        elif excerpt:
            html_count += 1
        state["papers"].append({
            "id": pid,
            "title": p.get("title", ""),
            "authors": p.get("authors", []),
            "year": p.get("year"),
            "venue": p.get("venue"),
            "abstract": p.get("abstract", ""),
            "citation_count": p.get("citation_count"),
            "tentative_topic_path": p.get("tentative_topic_path"),
            "pdf_path": pdf_path,
            "context_excerpt": excerpt,
            "tier": p.get("tier") or ("pdf" if pdf_path else ("html" if excerpt else "abstract_only")),
            "placements": [],
            "annotated": False,
            "is_orphan": False,
            "orphan_suggested_topic": None,
            "source_used": None,
        })
        existing_ids.add(pid)
        added += 1
    return added, (
        f"added {added} papers (pdf={pdf_count}, html_excerpt={html_count}); "
        f"total {len(state['papers'])}"
    )


def _merge_annotate(state: dict, parsed: dict) -> tuple[int, str]:
    ann = parsed.get("annotations") or []
    index = {_paper_id(p): p for p in state["papers"]}
    updated = 0
    src_counts = {"pdf": 0, "context_excerpt": 0, "abstract": 0, "other": 0}
    for a in ann:
        pid = a.get("paper_id")
        if not pid or pid not in index:
            continue
        p = index[pid]
        p["placements"] = a.get("placements") or []
        p["is_orphan"] = bool(a.get("is_orphan"))
        p["orphan_suggested_topic"] = a.get("orphan_suggested_topic")
        p["source_used"] = a.get("source_used")
        p["annotated"] = True
        src = (a.get("source_used") or "other").lower()
        src_counts[src if src in src_counts else "other"] += 1
        updated += 1
    return updated, (
        f"annotated {updated} papers "
        f"(pdf={src_counts['pdf']}, html={src_counts['context_excerpt']}, "
        f"abs={src_counts['abstract']})"
    )


def _merge_evolve(state: dict, parsed: dict) -> tuple[int, str]:
    new_fw = parsed.get("new_framework")
    deltas = parsed.get("deltas") or []
    stable = bool(parsed.get("stable"))
    relocations = parsed.get("paper_relocations") or []

    non_trivial = [d for d in deltas if d.get("op") in ("add", "merge", "split", "drop")]

    if new_fw:
        state["framework"] = new_fw

    if relocations:
        reloc_index = {r.get("paper_id"): r for r in relocations}
        for p in state["papers"]:
            r = reloc_index.get(_paper_id(p))
            if not r:
                continue
            old = r.get("old_path", "")
            new = r.get("new_path", "")
            for pl in p.get("placements", []):
                if pl.get("topic_path") == old:
                    pl["topic_path"] = new

    if stable or not non_trivial:
        state["no_delta_streak"] = state.get("no_delta_streak", 0) + 1
    else:
        state["no_delta_streak"] = 0

    return len(deltas), (
        f"applied {len(deltas)} deltas ({len(non_trivial)} non-trivial), "
        f"relocated {len(relocations)} papers, streak={state['no_delta_streak']}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Action dispatcher
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULT_MAX_ITERS = 30


def _dispatch(action: str, args: dict, state: dict, direction: str,
              output_dir: str, runtime: Runtime) -> tuple[str, dict]:
    """Execute a leaf for the chosen action.

    Returns (raw_text_result, parsed_dict). parsed_dict may be empty if the
    leaf's output did not parse as JSON.
    """
    papers_dir = os.path.join(output_dir, "papers")
    os.makedirs(papers_dir, exist_ok=True)

    if action == "seed_surveys":
        query = args.get("query") or direction
        k = int(args.get("k", 3))
        existing_titles = "\n".join(
            s.get("title", "") for s in state["surveys"] if s.get("title")
        )
        text = seed_surveys(
            query=query, k=k, existing_titles=existing_titles,
            papers_dir=papers_dir, runtime=runtime,
        )

    elif action == "extract_framework":
        surveys_json = json.dumps(state["surveys"], ensure_ascii=False)
        current = json.dumps(state["framework"], ensure_ascii=False) if state["framework"] else ""
        text = extract_framework(
            direction=direction, surveys_json=surveys_json,
            current_framework_json=current, runtime=runtime,
        )

    elif action == "search_papers":
        topic_path = args.get("topic_path", "")
        if not topic_path:
            return "", {"error": "search_papers requires topic_path"}
        topic_description = args.get("topic_description", "")
        if not topic_description and state["framework"]:
            for path, node in _iter_leaves(state["framework"]):
                if path == topic_path:
                    topic_description = node.get("description", "")
                    break
        k = int(args.get("k", 5))
        top_k_pdf = int(args.get("top_k_pdf", 3))
        existing_ids = "\n".join(_paper_id(p) for p in state["papers"] if _paper_id(p))
        text = search_papers_for_topic(
            topic_path=topic_path, topic_description=topic_description,
            k=k, existing_ids=existing_ids, papers_dir=papers_dir,
            top_k_pdf=top_k_pdf, runtime=runtime,
        )

    elif action == "annotate_papers":
        unannotated = [p for p in state["papers"] if not p.get("annotated")]
        if not unannotated:
            return "", {"error": "no unannotated papers"}
        payload = [
            {
                "id": _paper_id(p),
                "title": p.get("title", ""),
                "abstract": p.get("abstract", ""),
                "tentative_topic_path": p.get("tentative_topic_path", ""),
                "pdf_path": p.get("pdf_path"),
                "context_excerpt": p.get("context_excerpt"),
                "tier": p.get("tier"),
            }
            for p in unannotated[:20]
        ]
        papers_json = json.dumps(payload, ensure_ascii=False)
        framework_json = json.dumps(state["framework"] or {}, ensure_ascii=False)
        text = annotate_papers(
            papers_json=papers_json, framework_json=framework_json, runtime=runtime,
        )

    elif action == "evolve_framework":
        framework_json = json.dumps(state["framework"] or {}, ensure_ascii=False)
        papers_json = json.dumps(
            [{"id": _paper_id(p), "title": p.get("title", ""),
              "placements": p.get("placements", []),
              "is_orphan": p.get("is_orphan", False),
              "orphan_suggested_topic": p.get("orphan_suggested_topic")}
             for p in state["papers"]], ensure_ascii=False,
        )
        surveys_json = json.dumps(state["surveys"], ensure_ascii=False)
        audit_tail = "\n".join(
            f"iter {a.get('iter','?')}: {a.get('action','?')} — {a.get('summary','')}"
            for a in state["audit"][-8:]
        )
        text = evolve_framework(
            framework_json=framework_json, papers_json=papers_json,
            surveys_json=surveys_json, audit_tail=audit_tail, runtime=runtime,
        )

    elif action == "synthesize":
        framework_json = json.dumps(state["framework"] or {}, ensure_ascii=False)
        papers_json = json.dumps(state["papers"], ensure_ascii=False)
        surveys_json = json.dumps(state["surveys"], ensure_ascii=False)
        text = synthesize_literature(
            direction=direction, framework_json=framework_json,
            papers_json=papers_json, surveys_json=surveys_json,
            output_dir=output_dir, runtime=runtime,
        )

    else:
        return "", {"error": f"unknown action: {action}"}

    parsed = _safe_parse(text)
    return text, parsed


# ═══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

def _derive_project_name(topic: str) -> str:
    """Turn a research direction into a short, readable folder name."""
    import re as _re
    clean = _re.sub(r"[\r\n]+", " ", (topic or "").strip())
    clean = _re.sub(r"[/:\\]", " ", clean)
    words = clean.split()[:6] or ["research"]
    return " ".join(words).strip() or "research"


def _resolve_output_dir(output_dir: str | None, topic: str) -> str:
    """Resolve output_dir to an absolute path.

    - If the caller passed an absolute path (after user-expansion), use it.
    - If the caller passed a relative path, join it under ~/Documents/.
    - If nothing was passed, default to
      ~/Documents/<project_name>/literature review.
    """
    if output_dir:
        expanded = os.path.abspath(os.path.expanduser(output_dir))
        return expanded
    project = _derive_project_name(topic)
    return os.path.abspath(
        os.path.expanduser(f"~/Documents/{project}/literature review")
    )


def run_literature(
    topic: str,
    output_dir: str = None,
    runtime: Runtime = None,
    max_iters: int = _DEFAULT_MAX_ITERS,
) -> dict:
    """Iteratively build a literature review by looping a single-step dispatcher.

    Each iteration: an LLM picks one of six actions (seed_surveys,
    extract_framework, search_papers, annotate_papers, evolve_framework,
    synthesize). The corresponding leaf function runs, its JSON output is
    parsed and merged into state. The loop exits when `synthesize` succeeds
    or `max_iters` is reached.

    Args:
        topic:      Research direction (root of the topic tree).
        output_dir: Absolute directory for state.json + synthesis artifacts.
                    If omitted, defaults to
                    `~/Documents/<project>/literature review` where `project`
                    is derived from `topic`.
        runtime:    LLM runtime (required).
        max_iters:  Hard cap on iterations.

    Returns:
        dict with direction, iterations, stats, framework, output_dir, done.
    """
    if runtime is None:
        raise ValueError("run_literature() requires a runtime argument")

    output_dir = _resolve_output_dir(output_dir, topic)
    os.makedirs(output_dir, exist_ok=True)
    state = _load_or_init_state(output_dir, topic)

    done = False
    last_action = None
    synth_result: dict = {}

    for i in range(state["iter"] + 1, max_iters + 1):
        state["iter"] = i

        state_summary = _build_state_summary(state)
        framework_preview = _framework_preview(state)

        reply = _lit_decide(
            direction=topic, state_summary=state_summary,
            framework_preview=framework_preview, runtime=runtime,
        )

        decision = _safe_parse(reply)
        action = (decision.get("action") or "").strip()
        args = decision.get("action_args") or {}
        reasoning = decision.get("reasoning", "")

        if not action:
            state["audit"].append({
                "iter": i, "action": "<none>",
                "summary": f"decision parse failed: {str(reply)[:120]}",
            })
            _save_state(output_dir, state)
            print(f"    [literature/{i}] decide: PARSE_FAIL", file=sys.stderr)
            if i >= 3 and last_action is None:
                break
            continue

        print(f"    [literature/{i}] {action}  ({reasoning[:80]})", file=sys.stderr)

        text, parsed = _dispatch(action, args, state, topic, output_dir, runtime)

        if "error" in parsed and len(parsed) == 1:
            summary = f"dispatch error: {parsed['error']}"
            changed = 0
        elif action == "seed_surveys":
            changed, summary = _merge_seed_surveys(state, parsed)
        elif action == "extract_framework":
            changed, summary = _merge_extract_framework(state, parsed)
        elif action == "search_papers":
            changed, summary = _merge_search_papers(state, parsed)
        elif action == "annotate_papers":
            changed, summary = _merge_annotate(state, parsed)
        elif action == "evolve_framework":
            changed, summary = _merge_evolve(state, parsed)
        elif action == "synthesize":
            synth_result = parsed
            done = bool(parsed.get("done"))
            changed = 1 if done else 0
            summary = "synthesis complete" if done else (
                "synthesize returned no done flag; "
                + (("error: " + parsed.get("error", "?")) if parsed else "parse failed")
            )
        else:
            changed = 0
            summary = f"unknown action: {action}"

        state["audit"].append({
            "iter": i, "action": action, "reasoning": reasoning,
            "changed": changed, "summary": summary,
        })
        _save_state(output_dir, state)
        last_action = action

        if action == "synthesize" and done:
            break

    return {
        "direction": topic,
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
    'comprehensive_lit_review',
    'evolve_framework',
    'extract_framework',
    'identify_gaps',
    'run_literature',
    'search_arxiv',
    'search_papers_for_topic',
    'search_semantic_scholar',
    'seed_surveys',
    'survey_topic',
    'synthesize_literature',
]
