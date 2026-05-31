"""Survey synthesis: orchestrator + section-level leaf functions.

`synthesize_literature` is now a Python orchestrator (NOT an
`@agentic_function`). It walks the framework, calls one small leaf per
section to keep prompts tight and errors local, writes each piece to
`synthesis/sections/<name>.md`, then concatenates into
`synthesis/review.md`.

Sections (each = one LLM call via its own `@agentic_function` leaf):

  - abstract           — `_write_abstract`
  - 1. introduction    — `_write_introduction`
  - 2. taxonomy        — `_write_taxonomy_overview`  (overview only)
  - 3.X per branch     — `_write_branch_detail`      (one call per
                          top-level method-side branch)
  - 4. cross-cutting   — `_write_cross_cutting`
  - 5. research gaps   — `_write_research_gaps`

§6 References is left as a placeholder; the orchestrator (in
`__init__.py`) splices the programmatic bibliography after this
function returns.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.stages.literature._state import (
    _CROSS_CUTTING_NAMES,
    _papers_per_topic,
    _slug,
)


# ─── Filtering / outline helpers ───────────────────────────────────────


def _branch_paths(node: dict, prefix: str = "") -> set[str]:
    """All node paths inside this subtree (inclusive)."""
    name = (node.get("name") or "").strip()
    path = f"{prefix}/{name}".strip("/")
    out = {path}
    for c in node.get("children") or []:
        out |= _branch_paths(c, path)
    return out


def _papers_under_branch(state: dict, branch_node: dict,
                         branch_prefix: str) -> list[dict]:
    """Papers with at least one placement inside the branch subtree."""
    paths = _branch_paths(branch_node, branch_prefix)
    out = []
    for p in state["papers"]:
        for pl in p.get("placements") or []:
            if pl.get("topic_path") in paths:
                out.append(p)
                break
    return out


def _branch_outline_md(branch_node: dict, branch_prefix: str,
                      counts: dict[str, int],
                      branch_number: str) -> str:
    """Outline for ONE top-level branch, numbered as `<branch_number>.X.Y`.

    Prunes empty subtrees. Excludes nothing — caller must already have
    filtered out cross-cutting branches.
    """
    lines: list[str] = []

    def descendant_papers(n: dict, prefix: str) -> int:
        nm = (n.get("name") or "").strip()
        path = f"{prefix}/{nm}".strip("/")
        ch = n.get("children") or []
        if not ch:
            return counts.get(path, 0)
        return sum(descendant_papers(c, path) for c in ch)

    def walk(n: dict, n_prefix: str, number: str, depth: int) -> None:
        n_name = (n.get("name") or "").strip()
        n_path = f"{n_prefix}/{n_name}".strip("/")
        kids = [
            c for c in (n.get("children") or [])
            if descendant_papers(c, n_path) > 0
        ]
        for idx, c in enumerate(kids, 1):
            cn = (c.get("name") or "").strip()
            cp = f"{n_path}/{cn}".strip("/")
            cnum = f"{number}.{idx}"
            grand = c.get("children") or []
            is_leaf = not grand
            n_papers = (
                counts.get(cp, 0) if is_leaf
                else descendant_papers(c, n_path)
            )
            indent = "  " * depth
            kind = "leaf" if is_leaf else "group"
            lines.append(
                f"{indent}{cnum} {cn}  [{kind}, {n_papers} papers]"
            )
            walk(c, n_path, cnum, depth + 1)

    walk(branch_node, branch_prefix, branch_number, 0)
    if lines:
        return "\n".join(lines)
    bname = (branch_node.get("name") or "").strip()
    bpath = f"{branch_prefix}/{bname}".strip("/")
    n_papers = counts.get(bpath, 0)
    return (
        f"(branch is itself a leaf — write per-leaf content directly "
        f"under `### {branch_number} {bname}`; "
        f"{n_papers} papers placed here)"
    )


def _top_level_branches(framework: dict) -> list[tuple[dict, str]]:
    """Return [(child_node, child_prefix), ...] for the direct children
    of the framework root, EXCLUDING any cross-cutting subtree."""
    if not framework:
        return []
    root_name = (framework.get("name") or "").strip()
    out = []
    for c in framework.get("children") or []:
        cn = (c.get("name") or "").strip()
        if cn.lower() in _CROSS_CUTTING_NAMES:
            continue
        out.append((c, root_name))
    return out


def _cross_cutting_subtree(framework: dict) -> dict | None:
    for c in framework.get("children") or []:
        if (c.get("name") or "").strip().lower() in _CROSS_CUTTING_NAMES:
            return c
    return None


def _compact_paper(p: dict) -> dict:
    """Trim a paper dict for prompt compactness."""
    return {
        "id": p.get("id"),
        "title": p.get("title"),
        "authors": p.get("authors"),
        "year": p.get("year"),
        "venue": p.get("venue"),
        "tier": p.get("tier"),
        "pdf_path": p.get("pdf_path"),
        "abstract": p.get("abstract"),
        "contribution_summary": p.get("contribution_summary"),
        "placements": p.get("placements"),
        "limitations": p.get("limitations"),
    }


def _compact_survey(s: dict) -> dict:
    return {
        "id": s.get("id"),
        "title": s.get("title"),
        "authors": s.get("authors"),
        "year": s.get("year"),
        "toc": s.get("toc"),
        "key_claims": s.get("key_claims"),
    }


# ─── Section-level leaves (one LLM call each) ──────────────────────────


@agentic_function(render_range={"siblings": -1})
def _write_abstract(direction: str, framework_outline: str,
                    stats_json: str, surveys_brief: str,
                    runtime: Runtime) -> str:
    """Write the survey abstract.

    Output: 150-250 words. Single paragraph. State the field, the
    central problem, the scope of this review (what is / is not
    covered), the main organizing axes, key trends, and the gaps the
    review will highlight.

    Return the abstract text only — no heading, no preamble, no JSON.
    Do not invent specific numbers or paper-level claims.
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Direction: {direction}\n\n"
        f"Framework outline:\n{framework_outline}\n\n"
        f"Stats: {stats_json}\n\n"
        f"Survey TOC summary:\n{surveys_brief}\n\n"
        f"Write the abstract (150-250 words, one paragraph, no "
        f"heading, no JSON)."
    )}])


@agentic_function(render_range={"siblings": -1})
def _write_introduction(direction: str, framework_outline: str,
                        surveys_brief: str,
                        runtime: Runtime) -> str:
    """Write §1 Introduction.

    Three short subsections (no `###` heading, just bold inline labels
    or short paragraph breaks):

      - Problem framing: 2-3 paragraphs. Define the field, why it
        matters, the central tension that motivates the review.
      - Scope: 1 paragraph. What sub-problems / time range /
        methodologies are in-scope; what is explicitly out of scope.
      - Roadmap: 1 paragraph mapping each later section to a part of
        the story (§2 taxonomy, §3 detailed review, §4 cross-cutting,
        §5 gaps).

    Return prose only. Start with `## 1. Introduction` as the section
    header. Do not write any other top-level headings. Cite surveys
    inline as `[<id>]` if relevant; do not invent paper IDs.
    Target 600-1000 words.
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Direction: {direction}\n\n"
        f"Framework outline:\n{framework_outline}\n\n"
        f"Surveys:\n{surveys_brief}\n\n"
        f"Write §1 Introduction (600-1000 words). Start with the "
        f"`## 1. Introduction` heading. Return prose only."
    )}])


@agentic_function(render_range={"siblings": -1})
def _write_taxonomy_overview(direction: str, framework_outline: str,
                             counts_json: str,
                             runtime: Runtime) -> str:
    """Write §2 Taxonomy as an overview ONLY.

    Structure:
      1. A compact bulleted outline mirroring the framework tree:
         use indentation (2 spaces per depth) and `-` bullets, NOT
         numbered headings. Each bullet:
            `- <name>  (N papers)  — <one-sentence description>`
      2. Two short paragraphs explaining the organizing axes — why
         these branches, where cross-cutting concerns sit, how the
         tree maps to §3.

    NO per-paper detail. NO `### 2.X` headings — just the section
    header `## 2. Taxonomy` then the bulleted outline and prose.
    Target 400-700 words total. Return prose + bullets only.
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Direction: {direction}\n\n"
        f"Framework outline:\n{framework_outline}\n\n"
        f"Per-leaf paper counts: {counts_json}\n\n"
        f"Write §2 Taxonomy (overview only, 400-700 words). Start "
        f"with the `## 2. Taxonomy` heading. Use bullets, not "
        f"sub-headings, for the tree."
    )}])


@agentic_function(render_range={"siblings": -1})
def _write_branch_detail(direction: str, branch_name: str,
                         branch_number: str,
                         branch_outline: str,
                         papers_json: str,
                         runtime: Runtime) -> str:
    """Write ONE top-level §3 branch (e.g. §3.1 Off-Policy Post-Training).

    The branch may be nested. The outline gives you the EXACT heading
    structure to follow:
        - lines like `3.X.Y <name>  [group, N papers]` → emit a
          `#### 3.X.Y <name>` heading followed by a 3-6 sentence
          overview of what unifies the children. NO per-paper detail.
        - lines like `3.X.Y.Z <name>  [leaf, N papers]` → emit a
          `##### 3.X.Y.Z <name>` heading followed by the per-leaf
          structure described below.
        - the top branch itself gets `### 3.X <name>` and a 4-8
          sentence branch overview.

    Heading depth rule: the number of dots in the section number
    equals the markdown heading depth. `3.1` → `###`, `3.1.1` →
    `####`, `3.1.1.1` → `#####`.

    Per-leaf structure (only for `[leaf, ...]` lines):
      - **Overview** (2-4 sentences): the sub-problem and what makes
        it hard.
      - **Methods** — one paragraph per paper, ordered by method
        lineage (foundations → refinements → recent). Each paragraph
        starts with the citation `[<id>]` (verbatim from the paper's
        id field) then covers, in order:
          1. Problem framing (what the paper specifically targets).
          2. Method (technical core, 2-4 sentences). If `pdf_path` is
             non-null, you MAY use the Read tool to enrich method
             details from the PDF.
          3. Evidence (datasets, metrics, headline numbers — only
             numbers that appear in the abstract / contribution
             summary / PDF; do NOT invent).
          4. Limitation (one sentence).
      - **Trends** (1 paragraph): what shifted within this sub-problem.
      - **Open questions** (bulleted): from framework + papers.

    Hard rules:
      - Use ONLY the headings prescribed by the outline. Do NOT add
        extras, do NOT skip, do NOT merge.
      - Heading text must equal the name verbatim.
      - Cite using paper ids verbatim in `[id]` form. Do not invent
        IDs not present in `papers_json`.
      - Return prose + headings only. No JSON, no preamble.
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Direction: {direction}\n\n"
        f"Top-level branch: {branch_number} {branch_name}\n\n"
        f"Outline (AUTHORITATIVE — exact headings, exact order):\n"
        f"{branch_outline}\n\n"
        f"Papers placed inside this branch:\n{papers_json}\n\n"
        f"Write the full §{branch_number} section. Start with "
        f"`### {branch_number} {branch_name}` and follow the "
        f"outline."
    )}])


@agentic_function(render_range={"siblings": -1})
def _write_cross_cutting(direction: str, framework_outline: str,
                         xcut_outline: str,
                         papers_json: str,
                         surveys_brief: str,
                         runtime: Runtime) -> str:
    """Write §4 Cross-cutting synthesis.

    Subsections:
      - **How the sub-problems connect** (2-3 paragraphs): shared
        primitives, conflicting goals, pipeline stages.
      - **Consensus vs contested claims**:
          - Consensus: claims most surveys / multiple primary papers
            agree on. Cite ≥2 sources per claim.
          - Contested or open: claims where surveys disagree or recent
            work challenges older consensus. Cite the disagreeing
            sources.
      - **Cross-cutting concerns from framework** (if `xcut_outline`
        is non-empty): one paragraph per cross-cutting node, drawing
        on papers that touch multiple branches.
      - **Historical arc** (1-2 paragraphs): where the field was 3-5
        years ago, what changed, the current frontier.

    Start with `## 4. Cross-cutting synthesis`. Use `### 4.1`, `4.2`,
    ... for the subsections above. Cite paper IDs verbatim. Target
    1500-2500 words.
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Direction: {direction}\n\n"
        f"Framework outline:\n{framework_outline}\n\n"
        f"Cross-cutting subtree:\n{xcut_outline}\n\n"
        f"Papers (compact):\n{papers_json}\n\n"
        f"Surveys:\n{surveys_brief}\n\n"
        f"Write §4 Cross-cutting synthesis (1500-2500 words). Start "
        f"with `## 4. Cross-cutting synthesis`."
    )}])


@agentic_function(render_range={"siblings": -1})
def _write_research_gaps(direction: str, framework_outline: str,
                         papers_json: str,
                         runtime: Runtime) -> str:
    """Write §5 Research gaps.

    Concrete, actionable gaps. Not 'more research needed'. Organize
    as `### 5.1`, `### 5.2`, ..., grouped by framework branch where
    natural. Each gap:

      - **Gap <n>.<m> — <short title>**
      - **What's missing** (1 sentence, specific).
      - **Why existing work doesn't address it** (cite specific
        papers and what they do / do not do).
      - **What would plausibly fix it** (method sketch, 2-4
        sentences; not a full design).

    Start with `## 5. Research gaps`. Cite paper IDs verbatim.
    Target 1500-2500 words.
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Direction: {direction}\n\n"
        f"Framework outline:\n{framework_outline}\n\n"
        f"Papers (compact):\n{papers_json}\n\n"
        f"Write §5 Research gaps (1500-2500 words). Start with "
        f"`## 5. Research gaps`."
    )}])


# ─── Orchestrator ──────────────────────────────────────────────────────


_BIB_PLACEHOLDER_LINE = (
    "<!-- bibliography appended programmatically -->"
)


def _framework_outline_text(framework: dict, counts: dict[str, int]) -> str:
    """Plain bulleted outline of the WHOLE framework (incl. xcut),
    used as shared context across leaves. One node per line, indented."""
    lines: list[str] = []

    def walk(n: dict, prefix: str, depth: int) -> None:
        nm = (n.get("name") or "").strip()
        path = f"{prefix}/{nm}".strip("/")
        ch = n.get("children") or []
        is_leaf = not ch
        if depth == 0:
            lines.append(f"{nm}  [root]")
        else:
            indent = "  " * (depth - 1)
            n_papers = counts.get(path, 0) if is_leaf else 0
            tag = "leaf" if is_leaf else "group"
            suffix = f"  ({n_papers} papers)" if is_leaf else ""
            lines.append(f"{indent}- {nm}  [{tag}]{suffix}")
        for c in ch:
            walk(c, path, depth + 1)

    walk(framework or {}, "", 0)
    return "\n".join(lines)


def _strip_leading_heading_dupes(text: str, expected_heading: str) -> str:
    """If the model emitted the heading twice or wrapped the section
    in quotes / fences, normalize to a single instance starting at the
    expected heading."""
    text = text.strip()
    # Strip ```markdown ... ``` fences if any.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def synthesize_literature(direction: str, state: dict,
                          output_dir: str,
                          runtime: Runtime) -> dict:
    """Build review.md by calling one LLM per section.

    This function is NOT an `@agentic_function` — it is a Python
    orchestrator that calls the section-level leaves (each of which
    IS agentic) and concatenates their outputs.

    Side effects:
      - writes `synthesis/sections/<name>.md` for each section
      - writes `synthesis/review.md` (concatenated)

    Returns a small JSON-shaped dict with stats and `done=True` so the
    caller can treat it like the previous leaf's parsed result.
    """
    framework = state.get("framework") or {}
    counts = _papers_per_topic(state)
    outline = _framework_outline_text(framework, counts)

    papers_compact = [_compact_paper(p) for p in state.get("papers") or []]
    surveys_compact = [_compact_survey(s) for s in state.get("surveys") or []]
    surveys_brief = json.dumps(surveys_compact, ensure_ascii=False)

    counts_json = json.dumps(counts, ensure_ascii=False)
    stats = {
        "papers": len(state.get("papers") or []),
        "surveys": len(state.get("surveys") or []),
        "leaves": sum(1 for k, v in counts.items() if v > 0),
    }
    stats_json = json.dumps(stats, ensure_ascii=False)

    sections_dir = Path(output_dir) / "synthesis" / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    review_path = Path(output_dir) / "synthesis" / "review.md"

    pieces: list[tuple[str, str]] = []  # (filename, text)

    # ─ abstract ────────────────────────────────────────────────────
    abstract_text = _write_abstract(
        direction=direction, framework_outline=outline,
        stats_json=stats_json, surveys_brief=surveys_brief,
        runtime=runtime,
    ).strip()
    abstract_block = (
        f"# {direction}: A Literature Review\n\n"
        f"## Abstract\n\n{abstract_text}\n"
    )
    (sections_dir / "00_abstract.md").write_text(abstract_block, encoding="utf-8")
    pieces.append(("abstract", abstract_block))

    # ─ §1 introduction ─────────────────────────────────────────────
    intro_text = _strip_leading_heading_dupes(
        _write_introduction(
            direction=direction, framework_outline=outline,
            surveys_brief=surveys_brief, runtime=runtime,
        ),
        "## 1. Introduction",
    )
    if not intro_text.lstrip().startswith("## 1."):
        intro_text = f"## 1. Introduction\n\n{intro_text}"
    (sections_dir / "01_introduction.md").write_text(intro_text + "\n", encoding="utf-8")
    pieces.append(("introduction", intro_text))

    # ─ §2 taxonomy overview ────────────────────────────────────────
    tax_text = _strip_leading_heading_dupes(
        _write_taxonomy_overview(
            direction=direction, framework_outline=outline,
            counts_json=counts_json, runtime=runtime,
        ),
        "## 2. Taxonomy",
    )
    if not tax_text.lstrip().startswith("## 2."):
        tax_text = f"## 2. Taxonomy\n\n{tax_text}"
    (sections_dir / "02_taxonomy.md").write_text(tax_text + "\n", encoding="utf-8")
    pieces.append(("taxonomy", tax_text))

    # ─ §3 per top-level branch (one LLM call each) ─────────────────
    branches = _top_level_branches(framework)
    section3_header = "## 3. Per-topic detailed review\n"
    pieces.append(("section3_header", section3_header))
    (sections_dir / "03_section3_header.md").write_text(section3_header, encoding="utf-8")

    branch_summaries: list[dict] = []
    for idx, (bnode, bprefix) in enumerate(branches, 1):
        bname = (bnode.get("name") or "").strip()
        bnumber = f"3.{idx}"
        b_outline = _branch_outline_md(bnode, bprefix, counts, bnumber)
        b_papers = _papers_under_branch(state, bnode, bprefix)
        b_papers_compact = [_compact_paper(p) for p in b_papers]
        branch_papers_json = json.dumps(b_papers_compact, ensure_ascii=False)

        text = _strip_leading_heading_dupes(
            _write_branch_detail(
                direction=direction, branch_name=bname,
                branch_number=bnumber, branch_outline=b_outline,
                papers_json=branch_papers_json, runtime=runtime,
            ),
            f"### {bnumber} {bname}",
        )
        expected = f"### {bnumber} "
        if not text.lstrip().startswith(expected):
            text = f"### {bnumber} {bname}\n\n{text}"

        slug = _slug(bname).lower().replace(" ", "_")
        fname = f"03_branch_{idx:02d}_{slug}.md"
        (sections_dir / fname).write_text(text + "\n", encoding="utf-8")
        pieces.append((f"branch_{idx}", text))
        branch_summaries.append({
            "number": bnumber, "name": bname,
            "papers": len(b_papers),
        })

    # ─ §4 cross-cutting ────────────────────────────────────────────
    xcut = _cross_cutting_subtree(framework)
    xcut_outline = (
        _branch_outline_md(
            xcut, (framework.get("name") or "").strip(), counts, "4.x"
        )
        if xcut else ""
    )
    xcut_text = _strip_leading_heading_dupes(
        _write_cross_cutting(
            direction=direction, framework_outline=outline,
            xcut_outline=xcut_outline,
            papers_json=json.dumps(papers_compact, ensure_ascii=False),
            surveys_brief=surveys_brief, runtime=runtime,
        ),
        "## 4. Cross-cutting synthesis",
    )
    if not xcut_text.lstrip().startswith("## 4."):
        xcut_text = f"## 4. Cross-cutting synthesis\n\n{xcut_text}"
    (sections_dir / "04_cross_cutting.md").write_text(xcut_text + "\n", encoding="utf-8")
    pieces.append(("cross_cutting", xcut_text))

    # ─ §5 research gaps ────────────────────────────────────────────
    gaps_text = _strip_leading_heading_dupes(
        _write_research_gaps(
            direction=direction, framework_outline=outline,
            papers_json=json.dumps(papers_compact, ensure_ascii=False),
            runtime=runtime,
        ),
        "## 5. Research gaps",
    )
    if not gaps_text.lstrip().startswith("## 5."):
        gaps_text = f"## 5. Research gaps\n\n{gaps_text}"
    (sections_dir / "05_research_gaps.md").write_text(gaps_text + "\n", encoding="utf-8")
    pieces.append(("gaps", gaps_text))

    # ─ §6 references placeholder ───────────────────────────────────
    refs_block = f"## 6. References\n\n{_BIB_PLACEHOLDER_LINE}\n"
    (sections_dir / "06_references_placeholder.md").write_text(refs_block, encoding="utf-8")
    pieces.append(("references", refs_block))

    # ─ assemble review.md ──────────────────────────────────────────
    body = "\n\n".join(text.strip() for _name, text in pieces) + "\n"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(body, encoding="utf-8")

    word_count = len(body.split())
    return {
        "artifact": str(review_path),
        "stats": {
            "papers": stats["papers"],
            "surveys": stats["surveys"],
            "leaves_with_papers": stats["leaves"],
            "branches": len(branch_summaries),
            "words": word_count,
        },
        "branches": branch_summaries,
        "done": True,
    }
