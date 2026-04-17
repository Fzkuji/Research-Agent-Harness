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

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

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

Rules for picking — FIRST-PASS mode (no prior synthesize in state):
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

Rules for picking — REFINEMENT mode (prior synthesize exists):
Your job is to IMPROVE what's already there, not redo it. The state summary
will show `mode: REFINEMENT` and `N non-trivial improvements since` the last
synthesize. Priorities, in order:
  1. If papers at tier=abstract_only exist, re-run search_papers on their topic
     with `top_k_pdf` large enough to include them — so they upgrade to PDF
     tier. This is the most valuable cheap improvement.
  2. If any leaf has <5 papers, run search_papers for it.
  3. If the research direction is time-sensitive (LLM-era topics, fast fields)
     and the newest paper in state is >12 months old, run search_papers or
     seed_surveys with a query restricted to the latest year.
  4. If annotations are thin (many summaries based on abstract_only), re-run
     annotate_papers after step 1 upgraded them.
  5. If new papers materially shifted the structure (new orphan cluster,
     a leaf grew past 15), run evolve_framework.
  6. Re-synthesize ONLY when BOTH:
       - ≥3 non-trivial improvements have been made since the last synthesize,
         AND
       - convergence is re-achieved (stable framework, no orphans, all leaves
         ≥5 annotated papers).
     If you believe no meaningful improvement is possible (already saturated),
     pick action=synthesize with reasoning="nothing to improve; finalize" and
     the synthesize leaf will read existing files and touch up in place.
  7. Never pick the same no-op synthesize back-to-back. If you picked it and
     nothing changed, prefer stage_done or a search/expand action.

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
    """Resume state if state.json exists in output_dir, else init a new one.

    We intentionally do NOT require the stored direction to match the
    incoming one — output_dir is the resume key. The incoming direction
    overwrites state["direction"] so the latest phrasing (possibly carrying
    new intent from the user) flows into the dispatcher prompt.
    """
    path = os.path.join(output_dir, "state.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            state["direction"] = direction
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


# ─── Artifact tree (human-readable md layout) ──────────────────────────────

_FS_FORBIDDEN = r'[<>:"\\|?*\x00-\x1f]'


def _slug(s: str) -> str:
    """Filesystem-safe slug. Preserves spaces and unicode; just strips chars
    that are illegal on macOS/Linux FS. Keeps names readable."""
    import re as _re
    out = _re.sub(_FS_FORBIDDEN, "_", (s or "").strip())
    return out or "unnamed"


def _topic_dir(output_dir: str, topic_path: str) -> str:
    parts = [_slug(p) for p in (topic_path or "").split("/") if p]
    return os.path.join(output_dir, "topics", *parts) if parts else os.path.join(output_dir, "topics")


def _rel_pdf(pdf_path: str | None, output_dir: str) -> str:
    if not pdf_path:
        return "—"
    try:
        return os.path.relpath(pdf_path, output_dir)
    except ValueError:
        return pdf_path


def _render_framework_tree(node: dict | None, papers_by_topic: dict[str, list],
                           prefix: str = "", depth: int = 0) -> list[str]:
    if not node:
        return ["(no framework yet)"]
    lines = []
    name = node.get("name", "?")
    path = f"{prefix}/{name}".strip("/")
    children = node.get("children") or []
    if children:
        lines.append(f"{'  ' * depth}- **{name}** — {node.get('description','')[:80]}")
        for c in children:
            lines.extend(_render_framework_tree(c, papers_by_topic, path, depth + 1))
    else:
        count = len(papers_by_topic.get(path, []))
        lines.append(f"{'  ' * depth}- **{name}** ({count} papers) — {node.get('description','')[:80]}")
    return lines


def _index_papers_by_topic(state: dict) -> dict[str, list]:
    idx: dict[str, list] = {}
    for p in state["papers"]:
        for pl in p.get("placements") or []:
            tp = pl.get("topic_path", "")
            if not tp:
                continue
            idx.setdefault(tp, []).append((_paper_id(p), pl))
    return idx


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_survey_md(path: str, s: dict, output_dir: str) -> None:
    authors = ", ".join(s.get("authors", []) or [])
    toc = s.get("toc", []) or []
    claims = s.get("key_claims", []) or []
    content = (
        f"# {s.get('title', 'Untitled survey')}\n\n"
        f"- **ID**: {s.get('id', '—')}\n"
        f"- **Authors**: {authors or '—'}\n"
        f"- **Year**: {s.get('year', '—')}\n"
        f"- **Venue**: {s.get('venue', '—')}\n"
        f"- **PDF**: `{_rel_pdf(s.get('pdf_path'), output_dir)}`\n\n"
        f"## Abstract\n\n{s.get('abstract', '—')}\n\n"
        f"## Table of contents\n\n"
        + ("\n".join(f"- {t}" for t in toc) if toc else "_(none)_")
        + "\n\n## Key claims\n\n"
        + ("\n".join(f"- {c}" for c in claims) if claims else "_(none)_")
        + "\n"
    )
    _write(path, content)


def _write_paper_md(path: str, p: dict, placement: dict | None,
                    output_dir: str) -> None:
    authors = ", ".join(p.get("authors", []) or [])
    topic = placement.get("topic_path") if placement else "(orphan)"
    contribution = (placement or {}).get("contribution_summary", "")
    orphan_note = ""
    if p.get("is_orphan"):
        orphan_note = (
            f"- **Orphan**: yes — suggested topic: "
            f"{p.get('orphan_suggested_topic') or '—'}\n"
        )
    content = (
        f"# {p.get('title', 'Untitled')}\n\n"
        f"- **ID**: {p.get('id', '—')}\n"
        f"- **Authors**: {authors or '—'}\n"
        f"- **Year**: {p.get('year', '—')}, **Venue**: {p.get('venue', '—')}\n"
        f"- **Citations**: {p.get('citation_count', '—')}\n"
        f"- **Topic**: {topic}\n"
        f"- **Tier**: {p.get('tier', '—')} "
        f"(source used: {p.get('source_used') or '—'})\n"
        f"- **PDF**: `{_rel_pdf(p.get('pdf_path'), output_dir)}`\n"
        f"{orphan_note}\n"
        f"## Abstract\n\n{p.get('abstract', '—')}\n\n"
    )
    if placement is not None and contribution:
        content += f"## Contribution in `{topic}`\n\n{contribution}\n"
    elif p.get("is_orphan"):
        content += "## Contribution\n\n_(not yet placed — see suggested topic above)_\n"
    else:
        content += "## Contribution\n\n_(not yet annotated)_\n"
    _write(path, content)


def _write_topic_overview_md(path: str, topic_path: str, node: dict,
                             papers: list, state: dict) -> None:
    paper_idx = {_paper_id(p): p for p in state["papers"]}
    lines = [
        f"# {node.get('name', topic_path)}",
        "",
        f"**Path**: `{topic_path}`",
        f"**Source**: {node.get('source', '—')}",
        f"**Papers in this topic**: {len(papers)}",
        "",
        f"## Description\n\n{node.get('description', '—')}",
        "",
    ]
    oq = node.get("open_questions") or []
    lines.append("## Open questions\n")
    if oq:
        lines.extend(f"- {q}" for q in oq)
    else:
        lines.append("_(none)_")
    lines.append("\n## Papers\n")
    if papers:
        for pid, _pl in papers:
            p = paper_idx.get(pid)
            if not p:
                continue
            title = p.get("title", pid)
            year = p.get("year", "?")
            lines.append(f"- [{title}]({_slug(pid)}.md) ({year})")
    else:
        lines.append("_(none yet)_")
    lines.append("")
    _write(path, "\n".join(lines))


def _write_readme_md(path: str, state: dict, output_dir: str,
                     iter_no: int, done: bool) -> None:
    fw = state.get("framework")
    counts = _index_papers_by_topic(state)
    annotated = sum(1 for p in state["papers"] if p.get("annotated"))
    orphans = sum(1 for p in state["papers"] if p.get("is_orphan"))
    status = "done" if done else f"running (iter {iter_no})"
    lines = [
        f"# Literature Review — {state.get('direction', '')}",
        "",
        f"- **Status**: {status}",
        f"- **Iterations**: {state.get('iter', 0)}",
        f"- **Surveys**: {len(state['surveys'])}",
        f"- **Papers**: {len(state['papers'])} (annotated: {annotated}, orphans: {orphans})",
        f"- **Framework leaves**: {_leaf_count(fw)}",
        f"- **no_delta_streak**: {state.get('no_delta_streak', 0)}",
        "",
        "## Framework",
        "",
    ]
    lines.extend(_render_framework_tree(fw, counts))
    lines.append("")
    lines.append("## Recent actions")
    lines.append("")
    for a in state.get("audit", [])[-10:]:
        lines.append(
            f"- iter {a.get('iter', '?')}: **{a.get('action', '?')}** — "
            f"{(a.get('summary') or '')[:140]}"
        )
    lines.append("")
    lines.append("## Layout")
    lines.append("")
    lines.extend([
        "- `state.json` — canonical machine state",
        "- `surveys/` — one markdown per survey",
        "- `topics/<path>/` — per-topic folders: `_overview.md` + per-paper annotations",
        "- `orphans/` — papers not yet placed in the framework",
        "- `papers/<id>.pdf` — downloaded PDFs",
        "- `audit.md` — chronological action log",
        "- `synthesis/` — final deliverables (written when `synthesize` fires)",
    ])
    lines.append("")
    _write(path, "\n".join(lines))


def _write_audit_md(path: str, state: dict) -> None:
    lines = [f"# Audit log — {state.get('direction', '')}", ""]
    for a in state.get("audit", []):
        lines.append(f"## Iter {a.get('iter', '?')} — `{a.get('action', '?')}`")
        if a.get("reasoning"):
            lines.append(f"\n**Reasoning**: {a['reasoning']}")
        if a.get("summary"):
            lines.append(f"\n**Result**: {a['summary']}")
        if a.get("changed") is not None:
            lines.append(f"\n**Changed**: {a['changed']}")
        lines.append("")
    _write(path, "\n".join(lines))


def _flush_artifacts(state: dict, output_dir: str, iter_no: int,
                     done: bool = False) -> None:
    """Rewrite the human-readable artifact tree from state.

    - `topics/` and `orphans/` are fully regenerated (wiped then rewritten)
      so that evolve_framework's merge/split/rename/drop ops reflect
      immediately.
    - `surveys/` is append-only (surveys don't get removed mid-run).
    - `README.md` and `audit.md` are rewritten each call.
    - `papers/` (PDFs) is untouched.
    - `synthesis/` is untouched (only the synthesize leaf writes there).
    """
    import shutil
    try:
        topics_dir = os.path.join(output_dir, "topics")
        orphans_dir = os.path.join(output_dir, "orphans")
        if os.path.isdir(topics_dir):
            shutil.rmtree(topics_dir, ignore_errors=True)
        if os.path.isdir(orphans_dir):
            shutil.rmtree(orphans_dir, ignore_errors=True)

        # Surveys — incremental, keyed by id
        surveys_dir = os.path.join(output_dir, "surveys")
        os.makedirs(surveys_dir, exist_ok=True)
        for s in state["surveys"]:
            sid = _slug(s.get("id") or s.get("title", "unknown"))
            path = os.path.join(surveys_dir, f"{sid}.md")
            if not os.path.exists(path):
                _write_survey_md(path, s, output_dir)

        # Topics
        fw = state.get("framework")
        if fw:
            papers_by_topic = _index_papers_by_topic(state)
            for tp, node in _iter_leaves(fw):
                td = _topic_dir(output_dir, tp)
                os.makedirs(td, exist_ok=True)
                papers_here = papers_by_topic.get(tp, [])
                _write_topic_overview_md(
                    os.path.join(td, "_overview.md"),
                    tp, node, papers_here, state,
                )
                for pid, placement in papers_here:
                    p = next(
                        (p for p in state["papers"] if _paper_id(p) == pid),
                        None,
                    )
                    if p is None:
                        continue
                    _write_paper_md(
                        os.path.join(td, f"{_slug(pid)}.md"),
                        p, placement, output_dir,
                    )

        # Orphans
        orphans = [p for p in state["papers"] if p.get("is_orphan")]
        if orphans:
            os.makedirs(orphans_dir, exist_ok=True)
            for p in orphans:
                pid = _paper_id(p)
                _write_paper_md(
                    os.path.join(orphans_dir, f"{_slug(pid)}.md"),
                    p, placement=None, output_dir=output_dir,
                )

        _write_readme_md(
            os.path.join(output_dir, "README.md"),
            state, output_dir, iter_no, done,
        )
        _write_audit_md(os.path.join(output_dir, "audit.md"), state)
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


def _abstract_only_count(state: dict) -> int:
    return sum(1 for p in state["papers"] if p.get("tier") == "abstract_only")


def _thin_leaves(state: dict, threshold: int = 5) -> list[tuple[str, int]]:
    fw = state.get("framework")
    if not fw:
        return []
    counts = _papers_per_topic(state)
    out = []
    for path, _node in _iter_leaves(fw):
        n = counts.get(path, 0)
        if n < threshold:
            out.append((path, n))
    return out


def _prior_synthesize_iter(state: dict) -> int | None:
    """Return iter number of the most recent successful synthesize, else None."""
    for a in reversed(state.get("audit", [])):
        if a.get("action") == "synthesize" and (a.get("changed") or 0) > 0:
            return a.get("iter")
    return None


def _improvements_since_synth(state: dict) -> int:
    """Count non-trivial, non-synthesize actions after the last synthesize."""
    last = _prior_synthesize_iter(state)
    if last is None:
        return 0
    n = 0
    for a in state.get("audit", []):
        if (a.get("iter") or 0) <= last:
            continue
        if a.get("action") == "synthesize":
            continue
        if (a.get("changed") or 0) <= 0:
            continue
        n += 1
    return n


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

    prior = _prior_synthesize_iter(state)
    if prior is None:
        lines.append("mode: FIRST-PASS (no prior synthesize)")
    else:
        improvements = _improvements_since_synth(state)
        lines.append(
            f"mode: REFINEMENT (prior synthesize at iter {prior}; "
            f"{improvements} non-trivial improvements since)"
        )
        abs_only = _abstract_only_count(state)
        if abs_only:
            lines.append(
                f"  weakness: {abs_only} papers still at tier=abstract_only "
                "— candidates for re-search in PDF mode"
            )
        if framework:
            thin = _thin_leaves(state, threshold=5)
            if thin:
                lines.append(
                    f"  weakness: {len(thin)} thin leaves (<5 annotated papers)"
                )

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

def _derive_project_name(direction: str) -> str:
    """Turn a research direction into a short, readable folder name."""
    import re as _re
    clean = _re.sub(r"[\r\n]+", " ", (direction or "").strip())
    clean = _re.sub(r"[/:\\]", " ", clean)
    words = clean.split()[:6] or ["research"]
    return " ".join(words).strip() or "research"


def _resolve_output_dir(output_dir: str | None, direction: str) -> str:
    """Resolve output_dir to an absolute path.

    - If the caller passed an absolute path (after user-expansion), use it.
    - If the caller passed a relative path, join it under ~/Documents/.
    - If nothing was passed, default to
      ~/Documents/<project_name>/literature review.
    """
    if output_dir:
        expanded = os.path.abspath(os.path.expanduser(output_dir))
        return expanded
    project = _derive_project_name(direction)
    return os.path.abspath(
        os.path.expanduser(f"~/Documents/{project}/literature review")
    )


def run_literature(
    direction: str,
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
        direction:  Research direction / project descriptor. May be short
                    ("LLM Distillation") or a longer phrase that carries
                    extra intent ("LLM Distillation, focus on 2024 on-policy
                    methods"). Used to build the LLM prompt and to derive a
                    folder name when output_dir is omitted. Not used as a
                    strict resume key — resume is keyed on output_dir only.
        output_dir: Absolute directory for state.json + synthesis artifacts.
                    If omitted, defaults to
                    `~/Documents/<project>/literature review` where `project`
                    is derived from `direction`. Same output_dir → resume.
        runtime:    LLM runtime (required).
        max_iters:  Hard cap on iterations.

    Returns:
        dict with direction, iterations, stats, framework, output_dir, done.
    """
    if runtime is None:
        raise ValueError("run_literature() requires a runtime argument")

    output_dir = _resolve_output_dir(output_dir, direction)
    os.makedirs(output_dir, exist_ok=True)
    state = _load_or_init_state(output_dir, direction)

    done = False
    last_action = None
    synth_result: dict = {}

    for i in range(state["iter"] + 1, max_iters + 1):
        state["iter"] = i

        state_summary = _build_state_summary(state)
        framework_preview = _framework_preview(state)

        reply = _lit_decide(
            direction=direction, state_summary=state_summary,
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
            _flush_artifacts(state, output_dir, i)
            print(f"    [literature/{i}] decide: PARSE_FAIL", file=sys.stderr)
            if i >= 3 and last_action is None:
                break
            continue

        print(f"    [literature/{i}] {action}  ({reasoning[:80]})", file=sys.stderr)

        text, parsed = _dispatch(action, args, state, direction, output_dir, runtime)

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
        _flush_artifacts(state, output_dir, i, done=(action == "synthesize" and done))
        last_action = action

        if action == "synthesize" and done:
            break

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
