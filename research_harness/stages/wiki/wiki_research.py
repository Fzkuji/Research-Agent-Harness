"""wiki_research — structured multi-paper exploration of a direction.

Schema is enforced by Python, not by LLM trust. The LLM does two
bounded jobs:

1. Search the web for relevant arXiv papers, emit a JSON list with
   the canonical topic-path the user wants for this direction.
2. After Python writes the paper folders, rewrite the topic page
   body as a Wikipedia-style article from the ingested papers.

Python handles all folder creation, slug generation, frontmatter
emission, PDF download, and git commits — so the LLM cannot create
flat `Papers/` directories or otherwise drift from the schema.
"""

from __future__ import annotations

import re
from pathlib import Path

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.stages.wiki._helpers import (
    download_arxiv_pdf,
    dump_frontmatter,
    ensure_git_repo,
    fetch_arxiv_metadata,
    folder_tree,
    git_commit_all,
    last_name,
    slugify,
)
from research_harness.utils import parse_json


_PAPER_BODY_TEMPLATE = """# {title}

## One-line thesis

{thesis}

## Problem

{problem}

## Method

{method}

## Key Results

{results}

## Limitations

{limitations}
"""


def _write_topic_chain(root: Path, topic_path: str, summaries: dict[str, str]) -> Path:
    """Ensure every folder in `topic_path` exists with its same-named `.md`.

    Returns the leaf topic's `.md` path. `summaries` maps each folder
    name to a 1-3 sentence summary (used when creating new pages;
    existing pages are left alone).
    """
    cur = root
    leaf_md = root
    for part in topic_path.strip("/").split("/"):
        cur = cur / part
        cur.mkdir(exist_ok=True)
        leaf_md = cur / f"{part}.md"
        if not leaf_md.exists():
            body = summaries.get(part, "")
            leaf_md.write_text(
                f"---\ntype: topic\n---\n\n# {part}\n\n{body}\n"
, encoding="utf-8")
    return leaf_md


def _write_paper(root: Path, topic_dir: Path, paper: dict, pdf: bool) -> Path:
    """Write a paper folder under `topic_dir`. Returns the paper `.md` path."""
    meta = fetch_arxiv_metadata(paper["arxiv_id"])
    author1 = last_name(meta["authors"][0]) if meta["authors"] else ""
    slug = paper.get("slug") or slugify(meta["title"], author1, meta["year"])

    paper_dir = topic_dir / slug
    paper_dir.mkdir(exist_ok=True)
    paper_md = paper_dir / f"{slug}.md"

    fm = {
        "type": "paper",
        "arxiv": meta["arxiv_id"],
        "year": meta["year"],
        "title": meta["title"],
        "authors": list(meta["authors"][:8]),
        "venue": meta["venue"],
        "topics": [],
    }
    body = _PAPER_BODY_TEMPLATE.format(
        title=meta["title"],
        thesis=paper.get("thesis", "").strip() or "(to be filled)",
        problem=paper.get("problem", "").strip() or "(to be filled)",
        method=paper.get("method", "").strip() or "(to be filled)",
        results=paper.get("results", "").strip() or "(to be filled)",
        limitations=paper.get("limitations", "").strip() or "(to be filled)",
    )
    paper_md.write_text(dump_frontmatter(fm, "\n" + body), encoding="utf-8")

    if pdf:
        download_arxiv_pdf(meta["arxiv_id"], root / "Attachments" / f"{slug}.pdf")

    return paper_md


@agentic_function(render_range={"callers": 0})
def wiki_research(direction: str, wiki_root: str, k: int, runtime: Runtime) -> str:
    """Investigate a research direction end-to-end and grow the wiki.

    Python-enforced schema; LLM only produces content.

    ═══════════════════════════════════════════════════════════════
    YOUR JOB (single turn, may use web_fetch / web_search tools)
    ═══════════════════════════════════════════════════════════════

    1. Decide a canonical topic path as a HIERARCHY of nested
       categories, formatted as `Broad area/Sub-area/Specific topic`.
       Each `/` is a real folder boundary; each segment becomes a
       separate `.md` page that itself describes that level of the
       hierarchy.

       MANDATORY: the path MUST have at least 3 segments, going from
       broad → narrow. The narrowest (last) segment names the
       specific direction; the broader segments name its parent
       fields. Examples of correct paths:

         - "Artificial intelligence/Machine learning/Reinforcement learning"
         - "Large language model/Post-training/Preference optimization"
         - "Computer vision/Object detection/Anchor-free detectors"

       INCORRECT (single long compound name — never do this):
         - "LLM Post-Training Methods by Trajectory Provenance"
         - "Off-policy and on-policy preference optimization for LLMs"

       If the vault has an existing path you can extend, reuse the
       matching prefix segments and only add new leaf segments.
       Title case English, space-separated words. No decimal prefixes.

    2. Search the web for up to k arXiv papers that fit this exact
       direction. Use web_fetch on arxiv.org listings or
       semanticscholar.org. INTERPRET the direction strictly — if
       it mentions LLM / language models, restrict to LLM papers;
       do not substitute classical RL papers.

    3. For each paper, gather arxiv id and write a 1-3 sentence
       summary per section: One-line thesis, Problem, Method, Key
       Results, Limitations. Use the abstract as ground truth; mark
       uncertain bits with "(from abstract; verify against full
       text)".

    4. Emit a JSON object as your FINAL message (no other text after
       it, no markdown fence). Schema:

       {
         "topic_path": "Foo/Bar/Leaf",
         "topic_summaries": {
            "Foo": "1-3 sentence summary of Foo",
            "Bar": "...",
            "Leaf": "..."
         },
         "papers": [
            {
              "arxiv_id": "2305.18290",
              "thesis": "...",
              "problem": "...",
              "method": "...",
              "results": "...",
              "limitations": "..."
            },
            ...
         ]
       }

    Python parses this JSON and writes all files at schema-conformant
    paths — you do NOT need to call Write/Edit/Bash tools for file
    creation. A separate survey-rewrite call follows in Python.

    Args:
        direction: Research direction in natural language.
        wiki_root: Vault root.
        k:         Target number of papers (typical 5–10).
        runtime:   LLM runtime (auto-injected).
    """
    root = Path(wiki_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "Attachments").mkdir(exist_ok=True)
    ensure_git_repo(root)
    tree = folder_tree(root) or "(vault is empty)"

    prompt = (
        f"=== Research direction ===\n{direction}\n\n"
        f"=== Vault root ===\n{root}\n\n"
        f"=== Existing topic tree ===\n{tree}\n\n"
        f"=== Target ===\nk = {k}\n\n"
        f"Output ONLY the JSON object as your final message."
    )

    raw = runtime.exec(content=[{"type": "text", "text": prompt}])
    # Persist raw output for debugging — regardless of parse success.
    (root / ".runs").mkdir(exist_ok=True)
    (root / ".runs" / "last_research_raw.txt").write_text(str(raw), encoding="utf-8")
    try:
        data = parse_json(raw)
    except (ValueError, Exception) as e:
        return f"Error: failed to parse LLM JSON output ({e}). Raw saved to .runs/last_research_raw.txt"

    # Lenient key resolution — models tend to rename fields.
    def _first(d: dict, *keys, default=None):
        for k in keys:
            if k in d and d[k]:
                return d[k]
        return default

    topic_path = _first(
        data,
        "topic_path", "topic", "topic_name", "canonical_topic",
        "topic_path_string", default="",
    )
    if isinstance(topic_path, list):
        topic_path = "/".join(str(p) for p in topic_path)
    topic_path = str(topic_path).strip("/").strip()

    summaries = _first(
        data, "topic_summaries", "summaries", "topic_descriptions", default={}
    ) or {}
    if not isinstance(summaries, dict):
        summaries = {}

    papers = _first(data, "papers", "arxiv_papers", "ingest_list", default=[]) or []

    # If LLM only returned arxiv IDs (list of strings) without bodies,
    # convert to dicts so _write_paper still works.
    normalized: list[dict] = []
    for item in papers:
        if isinstance(item, str):
            normalized.append({"arxiv_id": item})
        elif isinstance(item, dict):
            # Try multiple key spellings for arxiv_id.
            aid = (
                item.get("arxiv_id") or item.get("arxiv") or item.get("id")
                or item.get("arxiv_url") or ""
            )
            if aid:
                item["arxiv_id"] = aid
                normalized.append(item)
    papers = normalized

    if not papers:
        return (
            f"Error: no usable papers in LLM JSON. Top-level keys: "
            f"{list(data.keys())}. Raw at .runs/last_research_raw.txt."
        )

    # If LLM didn't emit a usable hierarchical path, fire a focused
    # follow-up call asking ONLY for the path. Keep it narrow so the
    # model is more likely to comply.
    if not topic_path or topic_path.count("/") < 2:
        path_prompt = (
            f"Given the research direction:\n{direction}\n\n"
            f"What hierarchical taxonomy path should this work live "
            f"under in a research wiki? Output ONLY a slash-separated "
            f"path with AT LEAST 3 levels going from broad field to "
            f"narrow direction. Title case English, no decimal "
            f"prefixes. Examples:\n"
            f"  Large language model/Post-training/Preference optimization\n"
            f"  Computer vision/Object detection/Anchor-free detectors\n"
            f"  Reinforcement learning/Policy gradient/Trust region methods\n\n"
            f"Output the path string ONLY, no JSON, no quotes, no "
            f"explanation. Use slashes, not arrows."
        )
        path_raw = runtime.exec(content=[{"type": "text", "text": path_prompt}])
        candidate = str(path_raw).strip().strip('"').strip("'")
        # Take only the first line in case the model added prose.
        candidate = candidate.split("\n")[0].strip()
        if candidate.count("/") >= 2:
            topic_path = candidate.strip("/")
        else:
            topic_path = "Unsorted/" + (topic_path or "Direction")

    leaf_md = _write_topic_chain(root, topic_path, summaries)
    topic_dir = leaf_md.parent

    written_slugs: list[str] = []
    failures: list[str] = []
    for paper in papers:
        try:
            paper_md = _write_paper(root, topic_dir, paper, pdf=True)
            written_slugs.append(paper_md.parent.name)
        except RuntimeError as e:
            failures.append(f"{paper.get('arxiv_id', '?')}: {e}")

    if not written_slugs:
        return f"Error: no papers written. Failures: {failures}"

    paper_listing = "\n".join(
        f"- [[{slug}]] ({(topic_dir / slug / f'{slug}.md').relative_to(root)})"
        for slug in written_slugs
    )
    current_topic_body = leaf_md.read_text(encoding="utf-8")

    survey_prompt = (
        f"=== Topic page to rewrite ===\n{leaf_md}\n\n"
        f"=== Direction ===\n{direction}\n\n"
        f"=== Papers under this topic ({len(written_slugs)}) ===\n"
        f"{paper_listing}\n\n"
        f"=== Current topic page contents ===\n{current_topic_body}\n\n"
        f"Read each paper page (Read tool). Rewrite the topic page "
        f"body as a Wikipedia-style article: opening intro, 2-5 "
        f"sub-sections (## headings) clustering the papers by approach "
        f"or sub-area, each discussing the relevant papers in prose "
        f"with `[[<slug>]]` wikilinks. PRESERVE the frontmatter "
        f"verbatim. Use the Edit tool to update the topic page; do not "
        f"create any other files."
    )
    survey_summary = runtime.exec(content=[{"type": "text", "text": survey_prompt}])

    committed = git_commit_all(root, f"wiki: research direction: {direction[:60]}")
    suffix = " (committed)" if committed else " (no changes to commit)"
    report = (
        f"Topic: {topic_path}\n"
        f"Papers written: {len(written_slugs)}\n"
        + (f"Failures: {failures}\n" if failures else "")
        + f"\nSurvey LLM summary:\n{survey_summary}\n"
    )
    return f"{report}\n[research done]{suffix}"
