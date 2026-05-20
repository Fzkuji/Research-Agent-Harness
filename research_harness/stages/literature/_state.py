"""State + small utility helpers for the literature loop.

Holds the canonical state schema, load/save IO, and the cheap pure
helpers that every other module needs (slug, paper_id, parse_json
wrapper, framework leaf walks, count summaries).

Keep this file tiny — heavyweight rendering / md writing lives in
`_artifacts.py`; the action lifecycle lives in `_actions.py`.
"""
from __future__ import annotations

import json
import os
from typing import Any

from research_harness.utils import parse_json


# ─── State init / load / save ──────────────────────────────────────────

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
    """Resume state if state.json exists, else init a new one.

    output_dir is the resume key; we deliberately do NOT require the
    stored direction to match the incoming one. The incoming direction
    overwrites state["direction"] so the latest phrasing flows into the
    dispatcher prompt.
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


# ─── Path / slug utilities ─────────────────────────────────────────────

_FS_FORBIDDEN = r'[<>:"\\|?*\x00-\x1f]'


def _slug(s: str) -> str:
    """Filesystem-safe slug. Preserves spaces and unicode; just strips
    chars that are illegal on macOS/Linux FS. Keeps names readable."""
    import re as _re
    out = _re.sub(_FS_FORBIDDEN, "_", (s or "").strip())
    return out or "unnamed"


def _topic_dir(output_dir: str, topic_path: str) -> str:
    parts = [_slug(p) for p in (topic_path or "").split("/") if p]
    return (
        os.path.join(output_dir, "topics", *parts)
        if parts else os.path.join(output_dir, "topics")
    )


def _rel_pdf(pdf_path: str | None, output_dir: str) -> str:
    if not pdf_path:
        return "—"
    try:
        return os.path.relpath(pdf_path, output_dir)
    except ValueError:
        return pdf_path


# ─── Paper / parse helpers ─────────────────────────────────────────────

def _paper_id(p: dict) -> str:
    return (
        p.get("id") or p.get("arxiv_id") or p.get("doi")
        or p.get("title", "")
    )


def _safe_parse(text: Any) -> dict:
    if not isinstance(text, str):
        return {}
    try:
        result = parse_json(text)
        return result if isinstance(result, dict) else {}
    except ValueError:
        return {}


# ─── Framework tree walks + count summaries ────────────────────────────

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
    return sum(
        1 for p in state["papers"] if p.get("tier") == "abstract_only"
    )


_CROSS_CUTTING_NAMES = {
    "cross-cutting concerns", "cross cutting concerns",
    "cross-cutting", "cross cutting",
}


def _section3_leaves(state: dict) -> list[tuple[str, str, int]]:
    """Method-side leaves that should appear as §3 subsections.

    Returns ordered list of `(leaf_name, full_path, paper_count)` for
    every leaf with >=1 placed paper, excluding the Cross-Cutting
    Concerns subtree (those go to §4). Order follows the framework's
    own child order — that determines §3.1, §3.2, ...
    """
    framework = state.get("framework") or {}
    counts = _papers_per_topic(state)
    out: list[tuple[str, str, int]] = []

    def walk(node: dict, prefix: str, in_xcut: bool) -> None:
        name = (node.get("name") or "").strip()
        path = f"{prefix}/{name}".strip("/")
        if name.lower() in _CROSS_CUTTING_NAMES:
            in_xcut = True
        children = node.get("children") or []
        if not children:
            if not in_xcut:
                n = counts.get(path, 0)
                if n > 0:
                    out.append((name, path, n))
            return
        for c in children:
            walk(c, path, in_xcut)

    walk(framework, "", False)
    return out


def _section3_leaves_md(state: dict) -> str:
    leaves = _section3_leaves(state)
    if not leaves:
        return "(no §3 leaves — framework has no method-side leaves with placed papers)"
    return "\n".join(
        f"{i}. {name}  ({n} papers)"
        for i, (name, _path, n) in enumerate(leaves, 1)
    )


def _section3_outline(state: dict) -> list[dict]:
    """Hierarchical §3 outline preserving framework structure.

    Returns a list of dicts in DFS order, each:
        {"name": str, "path": str, "depth": int,
         "is_leaf": bool, "papers": int, "number": str}
    where `number` is the nested heading number (e.g. "3.1", "3.1.2").

    Excludes the Cross-Cutting Concerns subtree. Prunes any subtree with
    zero descendant papers (so empty branches don't create empty headings).
    The root direction node is itself omitted; its children become §3.1,
    §3.2, ...
    """
    framework = state.get("framework") or {}
    counts = _papers_per_topic(state)

    def descendant_papers(node: dict, prefix: str, in_xcut: bool) -> int:
        name = (node.get("name") or "").strip()
        path = f"{prefix}/{name}".strip("/")
        if name.lower() in _CROSS_CUTTING_NAMES:
            return 0
        children = node.get("children") or []
        if not children:
            return counts.get(path, 0)
        return sum(descendant_papers(c, path, in_xcut) for c in children)

    out: list[dict] = []

    def walk(node: dict, prefix: str, depth: int, number: str) -> None:
        children = [
            c for c in (node.get("children") or [])
            if (c.get("name") or "").strip().lower() not in _CROSS_CUTTING_NAMES
            and descendant_papers(c, prefix, False) > 0
        ]
        for idx, c in enumerate(children, 1):
            cname = (c.get("name") or "").strip()
            cpath = f"{prefix}/{cname}".strip("/")
            cnum = f"{number}.{idx}" if number else f"3.{idx}"
            grand = c.get("children") or []
            is_leaf = not grand
            n_papers = (
                counts.get(cpath, 0) if is_leaf
                else descendant_papers(c, prefix, False)
            )
            out.append({
                "name": cname, "path": cpath, "depth": depth + 1,
                "is_leaf": is_leaf, "papers": n_papers, "number": cnum,
            })
            walk(c, cpath, depth + 1, cnum)

    walk(framework, "", 0, "")
    return out


def _section3_outline_md(state: dict) -> str:
    outline = _section3_outline(state)
    if not outline:
        return "(no §3 outline — no method-side branches with placed papers)"
    lines = []
    for it in outline:
        indent = "  " * (it["depth"] - 1)
        kind = "leaf" if it["is_leaf"] else "group"
        lines.append(
            f"{indent}{it['number']} {it['name']}  "
            f"[{kind}, {it['papers']} papers]"
        )
    return "\n".join(lines)
