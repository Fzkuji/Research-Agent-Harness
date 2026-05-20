"""Human-readable artifact rendering + bibliography + audit + prune.

Everything that turns the in-memory `state` dict into markdown / files
on disk lives here. No LLM calls — pure data → text.

Layout written by `_flush_artifacts`:
  - `README.md`               — top-level snapshot
  - `audit.md`                — chronological action log
  - `surveys/<id>.md`         — per-survey card (incremental)
  - `topics/<path>/_overview.md` + per-paper md (regenerated each tick)
  - `orphans/<id>.md`         — unplaced papers
  - `synthesis/`              — written only by `synthesize_literature`

Bibliography (`_render_bibliography`) walks state directly so every
entry traces back to fetched arXiv / Semantic Scholar metadata, not LLM
memory — this catches hallucinated citations.

Citation audit (`_audit_citations`) flags arXiv IDs in synthesis prose
that are not in state (likely hallucinations).

Hard prune (`_prune_empty_leaves`) drops empty leaves the
`evolve_framework` LLM hedged on.

State summary (`_build_state_summary`) is the compact dump fed to
`_lit_decide` so the picker LLM can see what's done and what's thin.
"""
from __future__ import annotations

import json
import os
import re as _re
import shutil
from pathlib import Path

from research_harness.stages.literature._state import (
    _abstract_only_count,
    _iter_leaves,
    _leaf_count,
    _orphan_count,
    _paper_id,
    _papers_per_topic,
    _rel_pdf,
    _slug,
    _topic_dir,
    _unannotated_count,
)


# ─── Markdown writers ──────────────────────────────────────────────────

def _render_framework_tree(node: dict | None,
                           papers_by_topic: dict[str, list],
                           prefix: str = "", depth: int = 0) -> list[str]:
    if not node:
        return ["(no framework yet)"]
    lines = []
    name = node.get("name", "?")
    path = f"{prefix}/{name}".strip("/")
    children = node.get("children") or []
    if children:
        lines.append(
            f"{'  ' * depth}- **{name}** — "
            f"{node.get('description','')[:80]}"
        )
        for c in children:
            lines.extend(
                _render_framework_tree(
                    c, papers_by_topic, path, depth + 1)
            )
    else:
        count = len(papers_by_topic.get(path, []))
        lines.append(
            f"{'  ' * depth}- **{name}** ({count} papers) — "
            f"{node.get('description','')[:80]}"
        )
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
        f"- **Year**: {p.get('year', '—')}, "
        f"**Venue**: {p.get('venue', '—')}\n"
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
        content += (
            "## Contribution\n\n_(not yet placed — see suggested topic "
            "above)_\n"
        )
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
        f"- **Papers**: {len(state['papers'])} "
        f"(annotated: {annotated}, orphans: {orphans})",
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
            f"- iter {a.get('iter', '?')}: **{a.get('action', '?')}** "
            f"— {(a.get('summary') or '')[:140]}"
        )
    lines.append("")
    lines.append("## Layout")
    lines.append("")
    lines.extend([
        "- `state.json` — canonical machine state",
        "- `surveys/` — one markdown per survey",
        "- `topics/<path>/` — per-topic folders: `_overview.md` + "
        "per-paper annotations",
        "- `orphans/` — papers not yet placed in the framework",
        "- `papers/<id>.pdf` — downloaded PDFs",
        "- `audit.md` — chronological action log",
        "- `synthesis/` — final deliverables (written when "
        "`synthesize` fires)",
    ])
    lines.append("")
    _write(path, "\n".join(lines))


def _write_audit_md(path: str, state: dict) -> None:
    lines = [f"# Audit log — {state.get('direction', '')}", ""]
    for a in state.get("audit", []):
        lines.append(
            f"## Iter {a.get('iter', '?')} — `{a.get('action', '?')}`"
        )
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
    """Rewrite the human-readable artifact tree from state."""
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
                        (p for p in state["papers"]
                         if _paper_id(p) == pid),
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
        _write_audit_md(
            os.path.join(output_dir, "audit.md"), state,
        )
    except OSError:
        pass


# ─── Programmatic bibliography ─────────────────────────────────────────
# Built by walking state["papers"] + state["surveys"] directly, NOT by
# the LLM. Catches the bug class where the LLM confidently invents
# arXiv IDs / years / authors from half-remembered facts.

def _bib_entry(item: dict, kind: str) -> str:
    pid = item.get("id") or "—"
    year = item.get("year") or "—"
    authors = item.get("authors") or []
    if isinstance(authors, list):
        authors_str = ", ".join(authors) if authors else "—"
    else:
        authors_str = str(authors)
    title = (item.get("title") or "Untitled").strip()
    venue = (item.get("venue") or "").strip()
    tag = "[survey]" if kind == "survey" else ""
    venue_part = f" {venue}." if venue else ""
    return (
        f"- **[{pid}]** {tag} {authors_str} ({year}). "
        f"*{title}*.{venue_part}"
    ).strip().replace("  ", " ")


def _render_bibliography(state: dict) -> str:
    """Render bib as markdown bullets, sorted year-desc / author-asc,
    deduped by id."""
    papers = list(state.get("papers", []) or [])
    surveys = list(state.get("surveys", []) or [])
    items = (
        [(p, "paper") for p in papers]
        + [(s, "survey") for s in surveys]
    )

    def _sort_key(it):
        item, _kind = it
        year = item.get("year") or 0
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = 0
        authors = item.get("authors") or []
        first = (
            authors[0] if isinstance(authors, list) and authors else ""
        )
        return (-year, str(first).lower())

    items.sort(key=_sort_key)

    seen: set[str] = set()
    lines: list[str] = []
    for item, kind in items:
        pid = item.get("id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        lines.append(_bib_entry(item, kind))
    return "\n".join(lines) + "\n"


_BIB_PLACEHOLDER = "<!-- bibliography appended programmatically -->"


def _splice_bibliography_into_review(review_path: Path, bib_md: str,
                                     state: dict) -> bool:
    """Install programmatic bibliography in review.md.

    Strategy: regardless of what the LLM wrote, the final References
    section is owned by us. We (a) replace the explicit placeholder if
    present, otherwise (b) cut from the first `## 6. References` /
    `## References` heading to EOF and replace with our bib, otherwise
    (c) append. This prevents duplicate `## 6. References` headings
    when the LLM disregards the placeholder instruction and writes its
    own bibliography.
    """
    if not review_path.exists():
        return False
    text = review_path.read_text(encoding="utf-8")
    n_papers = len(state.get("papers", []) or [])
    n_surveys = len(state.get("surveys", []) or [])
    note = (
        f"\n*Generated programmatically from state "
        f"({n_papers} papers, {n_surveys} surveys). All entries trace "
        "to fetched metadata; the LLM does not edit this section.*\n\n"
    )
    block = note + bib_md
    if _BIB_PLACEHOLDER in text:
        new_text = text.replace(_BIB_PLACEHOLDER, block.lstrip())
    else:
        m = _re.search(r"(?m)^##\s+(?:6\.\s+)?References\s*$", text)
        if m:
            head = text[:m.start()].rstrip() + "\n\n"
            new_text = head + "## 6. References\n" + block
        else:
            sep = "\n\n" if not text.endswith("\n") else "\n"
            new_text = text + f"{sep}## 6. References\n{block}"
    review_path.write_text(new_text, encoding="utf-8")
    return True


# ─── Citation audit ────────────────────────────────────────────────────

_ARXIV_RE = _re.compile(
    r"arXiv:\s*([0-9]{4}\.[0-9]{4,6})", _re.IGNORECASE,
)


def _audit_citations(state: dict, output_dir: str) -> list[str]:
    """Scan review.md (sections 1-5) for arXiv IDs not in state.

    The bibliography section is excluded — it is generated
    programmatically so by definition every entry there is in state.
    """
    review_path = Path(output_dir) / "synthesis" / "review.md"
    if not review_path.exists():
        return []
    text = review_path.read_text(encoding="utf-8", errors="ignore")
    body = text.split("## 6. References", 1)[0]
    body = body.split("## References", 1)[0]

    known_ids: set[str] = set()
    for it in (
        (state.get("papers") or [])
        + (state.get("surveys") or [])
    ):
        pid = (it.get("id") or "").lower()
        if pid:
            known_ids.add(pid)
            if ":" in pid:
                known_ids.add(pid.split(":", 1)[1])

    warnings: list[str] = []
    for m in _ARXIV_RE.finditer(body):
        arxiv_id = m.group(1).lower()
        if (
            arxiv_id not in known_ids
            and f"arxiv:{arxiv_id}" not in known_ids
        ):
            warnings.append(
                f"  review.md: arXiv:{arxiv_id} not in state"
            )
    return warnings


# ─── Hard prune of empty leaves ────────────────────────────────────────
# evolve_framework hedges against churn and rarely drops empty leaves.
# This is the deterministic complement: any leaf with 0 placed papers
# AND not directly sourced from a survey TOC gets removed.

def _prune_empty_leaves(state: dict) -> tuple[int, list[str]]:
    """Mutates state["framework"] in place. Returns (n_pruned, paths)."""
    fw = state.get("framework")
    if not fw:
        return 0, []
    counts = _papers_per_topic(state)
    pruned: list[str] = []

    def _walk(node: dict, parent_path: str) -> bool:
        children = node.get("children") or []
        kept = []
        for child in children:
            child_path = (
                f"{parent_path}/{child['name']}" if parent_path
                else child["name"]
            )
            if _walk(child, child_path):
                kept.append(child)
            else:
                pruned.append(child_path)
        node["children"] = kept
        if kept:
            return True
        if counts.get(parent_path, 0) > 0:
            return True
        if (node.get("source") or "").lower() == "survey":
            return True
        return False

    for child in list(fw.get("children") or []):
        child_path = child["name"]
        if not _walk(child, child_path):
            pruned.append(child_path)
            fw["children"].remove(child)
    return len(pruned), pruned


def _thin_leaves(state: dict,
                 threshold: int = 5) -> list[tuple[str, int]]:
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


# ─── State summary for the dispatcher LLM ──────────────────────────────

def _prior_synthesize_iter(state: dict) -> int | None:
    """Return iter number of the most recent successful synthesize."""
    for a in reversed(state.get("audit", [])):
        if (
            a.get("action") == "synthesize"
            and (a.get("changed") or 0) > 0
        ):
            return a.get("iter")
    return None


def _improvements_since_synth(state: dict) -> int:
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
        lines.append(
            f"  - {s.get('title','?')[:80]} ({s.get('year','?')})"
        )
    if len(surveys) > 8:
        lines.append(f"  ... and {len(surveys) - 8} more")

    lines.append(
        f"papers: {len(papers)} total, "
        f"{_unannotated_count(state)} unannotated, "
        f"{_orphan_count(state)} orphans"
    )

    if framework:
        leaves = list(_iter_leaves(framework))
        counts = _papers_per_topic(state)
        lines.append(f"framework: {_leaf_count(framework)} leaves")
        thin = [
            (path, counts.get(path, 0))
            for path, _ in leaves if counts.get(path, 0) < 5
        ]
        if thin:
            lines.append("  thin leaves (<5 papers):")
            for path, n in thin[:10]:
                lines.append(f"    - {path}  ({n} papers)")
        heavy = [
            (path, counts.get(path, 0))
            for path, _ in leaves if counts.get(path, 0) >= 15
        ]
        if heavy:
            lines.append(
                "  heavy leaves (>=15 papers, candidate for split):"
            )
            for path, n in heavy[:5]:
                lines.append(f"    - {path}  ({n} papers)")
    else:
        lines.append("framework: (none yet)")

    lines.append(
        f"no_delta_streak: {state.get('no_delta_streak', 0)} "
        "(consecutive evolve rounds with no non-trivial change)"
    )

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
                f"  weakness: {abs_only} papers still at "
                "tier=abstract_only — candidates for re-search in PDF "
                "mode"
            )
        if framework:
            thin = _thin_leaves(state, threshold=5)
            if thin:
                lines.append(
                    f"  weakness: {len(thin)} thin leaves "
                    "(<5 annotated papers)"
                )

    if audit_tail:
        lines.append("recent audit:")
        for a in audit_tail:
            lines.append(
                f"  - iter {a.get('iter','?')}: "
                f"{a.get('action','?')} — "
                f"{a.get('summary','')[:100]}"
            )

    return "\n".join(lines)


def _framework_preview(state: dict, max_chars: int = 2000) -> str:
    fw = state["framework"]
    if not fw:
        return ""
    text = json.dumps(fw, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        return text[:max_chars] + "\n... [truncated]"
    return text
