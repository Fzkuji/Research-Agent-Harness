"""Action lifecycle for the literature loop.

Three concerns live here:

1. **Catalog + decide LLM**: `_build_lit_actions_available` and
   `_lit_decide` define which actions the picker LLM can choose from
   on each tick.

2. **Dispatcher**: `_dispatch` maps the chosen action onto the actual
   leaf @agentic_function (from sibling modules — annotate_papers,
   evolve_framework, etc.). Includes the batched annotate logic that
   keeps stdout under the asyncio readline buffer cap.

3. **Mergers**: `_merge_*` functions take a parsed dict from a leaf
   and update `state` in place. They also report `(changed, summary)`
   for the audit log.

Cross-module split:
  - State + tiny utilities → `_state.py`
  - Markdown / bib / prune / summary → `_artifacts.py`
  - Orchestration loop → package `__init__.py`
"""
from __future__ import annotations

import json
import os

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime
from openprogram.programs.functions.buildin.build_catalog import build_catalog

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
from research_harness.stages.literature._artifacts import (
    _prune_empty_leaves,
)
from research_harness.stages.literature._state import (
    _iter_leaves,
    _leaf_count,
    _paper_id,
    _safe_parse,
)
from research_harness.utils import parse_json


# ═══════════════════════════════════════════════════════════════════════
# Catalog + decide LLM
# ═══════════════════════════════════════════════════════════════════════

def _noop(**_kw):
    """Placeholder callable for catalog entries — `_lit_decide` only
    picks; `_dispatch` calls the real implementations."""
    return None


def _build_lit_actions_available() -> dict:
    """Registry of literature-loop actions for build_catalog /
    parse_action."""
    return {
        "seed_surveys": {
            "function": _noop,
            "description": (
                "Find survey papers (defaults to the research direction "
                "as query) and add them to state.surveys."
            ),
            "input": {
                "query": {
                    "source": "llm", "type": str,
                    "description": (
                        "search query; defaults to the research "
                        "direction"
                    ),
                },
                "k": {
                    "source": "llm", "type": int,
                    "description": (
                        "number of surveys to fetch (default 3)"
                    ),
                },
            },
            "output": {},
        },
        "extract_framework": {
            "function": _noop,
            "description": (
                "From state.surveys plus any existing framework, build "
                "or refresh the topic tree. Consumes state.surveys + "
                "state.framework."
            ),
            "input": {},
            "output": {},
        },
        "search_papers": {
            "function": _noop,
            "description": (
                "Find NEW papers under a specific topic path in the "
                "framework."
            ),
            "input": {
                "topic_path": {
                    "source": "llm", "type": str,
                    "description": (
                        "path in the framework tree, e.g. 'a/b/c'"
                    ),
                },
                "k": {
                    "source": "llm", "type": int,
                    "description": (
                        "number of papers to fetch (default 5)"
                    ),
                },
                "top_k_pdf": {
                    "source": "llm", "type": int,
                    "description": (
                        "how many of those to upgrade to PDF tier "
                        "(default 3)"
                    ),
                },
            },
            "output": {},
        },
        "annotate_papers": {
            "function": _noop,
            "description": (
                "For every paper with annotated=false, assign "
                "topic_path and write a contribution_summary. Picks "
                "all unannotated papers."
            ),
            "input": {},
            "output": {},
        },
        "evolve_framework": {
            "function": _noop,
            "description": (
                "Refactor the topic tree based on accumulated evidence "
                "(merge/split/rename/drop leaves)."
            ),
            "input": {},
            "output": {},
        },
        "done": {
            "function": _noop,
            "description": (
                "No further useful action at this moment. "
                "scope='cycle' breaks the inner loop; scope='all' "
                "stops the outer loop too."
            ),
            "input": {
                "scope": {
                    "source": "llm", "type": str,
                    "options": ["cycle", "all"],
                    "description": "'cycle' (default) or 'all'",
                },
            },
            "output": {},
        },
    }


@agentic_function(render_range={"depth": 0, "siblings": 0})
def _lit_decide(direction: str, state_summary: str,
                framework_preview: str, runtime: Runtime) -> str:
    """Pick the next literature-loop action. Single-step dispatch.

Reply in the standard openprogram action format, with the action's args:

    {"call": "<action_name>", "args": { ... }}

Guidance — FIRST-PASS mode (no prior synthesize in state):
- Cold start (no surveys): seed_surveys.
- Have surveys, no framework: extract_framework.
- Framework exists, leaves thin (<5 papers) and not yet searched:
  search_papers for the leaf that needs coverage most.
- Papers with annotated=false: annotate_papers.
- Orphans present, or a leaf past ~15 papers, or several rounds passed
  with no structural review: evolve_framework.
- Framework stable for several rounds AND every leaf has ≥5 annotated
  papers AND no orphans remain: done.

Guidance — REFINEMENT mode (prior synthesize exists):
Improve what's there, don't redo it. Priorities, in order:
  1. If papers at tier=abstract_only exist, re-run search_papers on
     their topic with `top_k_pdf` large enough to include them —
     upgrades them to PDF tier. Most valuable cheap improvement.
  2. If any leaf has <5 papers, run search_papers for it.
  3. If the direction is time-sensitive and the newest paper is >12
     months old, search_papers / seed_surveys with a recent-year query.
  4. If annotations are thin (many abstract_only summaries), re-run
     annotate_papers after step 1 upgraded them.
  5. If new papers materially shifted the structure (new orphan
     cluster, a leaf grew past 15), run evolve_framework.
  6. If saturated: done.

Returns raw JSON text; the orchestrator parses and dispatches.
"""
    available = _build_lit_actions_available()
    catalog = build_catalog(available)
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research direction:\n{direction}\n\n"
            f"State summary:\n{state_summary}\n\n"
            f"Current framework (truncated):\n"
            f"{framework_preview or '(no framework yet)'}\n\n"
            f"== Actions ==\n{catalog}"
        )},
    ])


# ═══════════════════════════════════════════════════════════════════════
# Per-action merge logic
# ═══════════════════════════════════════════════════════════════════════

def _merge_seed_surveys(state: dict, parsed: dict) -> tuple[int, str]:
    new = parsed.get("surveys") or []
    existing_ids = {s.get("id") for s in state["surveys"]}
    existing_titles = {
        (s.get("title") or "").strip().lower()
        for s in state["surveys"]
    }
    added = 0
    for s in new:
        sid = s.get("id")
        title_key = (s.get("title") or "").strip().lower()
        if (
            (sid and sid in existing_ids)
            or (title_key and title_key in existing_titles)
        ):
            continue
        state["surveys"].append(s)
        existing_ids.add(sid)
        existing_titles.add(title_key)
        added += 1
    return added, (
        f"added {added} new surveys (total {len(state['surveys'])})"
    )


def _merge_extract_framework(state: dict,
                             parsed: dict) -> tuple[int, str]:
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
            "tier": p.get("tier") or (
                "pdf" if pdf_path else (
                    "html" if excerpt else "abstract_only"
                )
            ),
            "placements": [],
            "annotated": False,
            "is_orphan": False,
            "orphan_suggested_topic": None,
            "source_used": None,
        })
        existing_ids.add(pid)
        added += 1
    return added, (
        f"added {added} papers (pdf={pdf_count}, "
        f"html_excerpt={html_count}); total {len(state['papers'])}"
    )


def _merge_annotate(state: dict, parsed: dict) -> tuple[int, str]:
    ann = parsed.get("annotations") or []
    index = {_paper_id(p): p for p in state["papers"]}
    updated = 0
    src_counts = {
        "pdf": 0, "context_excerpt": 0, "abstract": 0, "other": 0,
    }
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

    non_trivial = [
        d for d in deltas
        if d.get("op") in ("add", "merge", "split", "drop")
    ]

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

    n_pruned, _pruned_paths = _prune_empty_leaves(state)
    prune_part = (
        f", pruned {n_pruned} empty leaves" if n_pruned else ""
    )

    return len(deltas), (
        f"applied {len(deltas)} deltas "
        f"({len(non_trivial)} non-trivial), "
        f"relocated {len(relocations)} papers, "
        f"streak={state['no_delta_streak']}{prune_part}"
    )


# ═══════════════════════════════════════════════════════════════════════
# Action dispatcher
# ═══════════════════════════════════════════════════════════════════════

def _dispatch(action: str, args: dict, state: dict, direction: str,
              output_dir: str,
              runtime: Runtime) -> tuple[str, dict]:
    """Execute the leaf for the chosen action.

    Returns (raw_text, parsed_dict). parsed_dict may be empty if the
    leaf's output did not parse as JSON.
    """
    papers_dir = os.path.join(output_dir, "papers")
    os.makedirs(papers_dir, exist_ok=True)

    if action == "seed_surveys":
        query = args.get("query") or direction
        k = int(args.get("k", 3))
        existing_titles = "\n".join(
            s.get("title", "")
            for s in state["surveys"] if s.get("title")
        )
        text = seed_surveys(
            query=query, k=k, existing_titles=existing_titles,
            papers_dir=papers_dir, runtime=runtime,
        )

    elif action == "extract_framework":
        surveys_json = json.dumps(state["surveys"], ensure_ascii=False)
        current = (
            json.dumps(state["framework"], ensure_ascii=False)
            if state["framework"] else ""
        )
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
        existing_ids = "\n".join(
            _paper_id(p) for p in state["papers"] if _paper_id(p)
        )
        text = search_papers_for_topic(
            topic_path=topic_path,
            topic_description=topic_description, k=k,
            existing_ids=existing_ids, papers_dir=papers_dir,
            top_k_pdf=top_k_pdf, runtime=runtime,
        )

    elif action == "annotate_papers":
        unannotated = [
            p for p in state["papers"] if not p.get("annotated")
        ]
        if not unannotated:
            return "", {"error": "no unannotated papers"}
        # Batch in chunks to keep stdout under the asyncio readline
        # buffer cap. Single-shot with 20 papers + framework + every
        # paper's context_excerpt blew that limit on codex CLI; drop
        # context_excerpt when pdf_path is set (the LLM can read the
        # PDF directly), and cap each call at BATCH papers.
        BATCH = 6
        MAX_PAPERS_PER_ACTION = 18  # ~3 batches per dispatch tick
        framework_json = json.dumps(
            state["framework"] or {}, ensure_ascii=False,
        )
        merged_annotations: list = []
        merged_notes: list = []
        merged_text_parts: list = []
        target = unannotated[:MAX_PAPERS_PER_ACTION]
        for start in range(0, len(target), BATCH):
            batch = target[start:start + BATCH]
            payload = []
            for p in batch:
                row = {
                    "id": _paper_id(p),
                    "title": p.get("title", ""),
                    "abstract": p.get("abstract", ""),
                    "tentative_topic_path": p.get(
                        "tentative_topic_path", ""),
                    "pdf_path": p.get("pdf_path"),
                    "tier": p.get("tier"),
                }
                if (
                    not p.get("pdf_path")
                    and p.get("context_excerpt")
                ):
                    row["context_excerpt"] = p.get("context_excerpt")
                payload.append(row)
            papers_json = json.dumps(payload, ensure_ascii=False)
            try:
                batch_text = annotate_papers(
                    papers_json=papers_json,
                    framework_json=framework_json,
                    runtime=runtime,
                )
            except Exception as e:
                merged_text_parts.append(
                    f"[batch {start // BATCH + 1} failed: "
                    f"{type(e).__name__}: {e}]"
                )
                continue
            merged_text_parts.append(batch_text)
            # parse_json raises ValueError when codex's response has no
            # JSON object (rare — happens when the model emits prose
            # only). Treat that batch as a parse miss and move on; the
            # remaining batches still produce valid annotations.
            batch_parsed = None
            if isinstance(batch_text, str):
                try:
                    batch_parsed = parse_json(batch_text)
                except ValueError:
                    batch_parsed = None
            if not isinstance(batch_parsed, dict):
                continue
            anns = batch_parsed.get("annotations") or []
            if isinstance(anns, list):
                merged_annotations.extend(anns)
            note = batch_parsed.get("notes")
            if note:
                merged_notes.append(str(note))
        text = "\n\n---\n\n".join(merged_text_parts)
        combined = {
            "annotations": merged_annotations,
            "notes": (
                " | ".join(merged_notes) if merged_notes else ""
            ),
        }
        return text, combined

    elif action == "evolve_framework":
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
        text = evolve_framework(
            framework_json=framework_json, papers_json=papers_json,
            surveys_json=surveys_json, audit_tail=audit_tail,
            runtime=runtime,
        )

    else:
        # synthesize is NOT a valid inner action — it runs as
        # end-of-run finalization. If the LLM picks it here by mistake,
        # return a noop error.
        return "", {"error": f"unknown action: {action}"}

    parsed = _safe_parse(text)
    return text, parsed
