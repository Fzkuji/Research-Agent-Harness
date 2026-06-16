"""wiki_survey — rewrite a topic page as a Wikipedia-style article."""

from __future__ import annotations

from pathlib import Path

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.stages.wiki._helpers import (
    find_node,
    git_commit_all,
    parse_frontmatter,
)


@agentic_function()
def wiki_survey(topic: str, wiki_root: str, depth: int, runtime: Runtime) -> str:
    """Rewrite a topic page as a Wikipedia-style article from its papers.

    Given a topic node (by filename stem) that already has child paper
    pages, regenerate the topic's same-named `.md` so that it reads
    like a Wikipedia entry: an introductory section, then sub-sections
    organized by method / sub-area, with the individual paper pages
    referenced via `[[wikilinks]]`.

    ═══════════════════════════════════════════════════════════════
    INPUT (in the next message)
    ═══════════════════════════════════════════════════════════════

    - topic_name: the filename stem of the topic to survey
    - topic_md_path: absolute path to the same-named `.md`
    - paper_pages: list of absolute paths to every paper page
      (direct children) under this topic folder
    - subtopic_pages: list of paths to any subtopic same-named `.md`
      directly under this topic folder
    - current_body: the existing body of the topic page (may be
      empty or partial)

    ═══════════════════════════════════════════════════════════════
    YOUR JOB
    ═══════════════════════════════════════════════════════════════

    1. Read each paper page (Read tool). Note their One-line thesis,
       Method, Key Results. Group papers into 2–5 natural clusters
       by approach / lineage / sub-area.

    2. Read each subtopic page's first paragraph to understand what
       belongs under each.

    3. Rewrite the topic same-named `.md`. Preserve the existing
       frontmatter exactly (only the body changes). The new body
       should have:

       - An opening 1–3 paragraph introduction defining the topic
         and outlining the major directions covered here.
       - Sub-sections (## headings) per cluster you identified. In
         each cluster, discuss the relevant papers in prose
         (not bullet lists), citing each with `[[<slug>]]`.
       - A `## Subtopics` section listing subtopic wikilinks if any
         subtopic pages exist. Skip this section if none.
       - Style: factual, terse, no marketing language. Mirror
         Wikipedia's tone. Cite specific papers for specific claims.

    4. Use the Edit or Write tool to save the rewritten page. Do not
       create any new files outside the topic's same-named `.md`.

    5. Return a brief summary: how many clusters, how many papers
       integrated, any papers that did not fit naturally.

    Args:
        topic:     Filename stem of the topic page (e.g.
                   "Preference optimization").
        wiki_root: Absolute path to the wiki vault root.
        depth:     How many levels of subtopics to recurse into.
                   0 = just this topic (default). 1 = also rewrite
                   each direct subtopic page. N = recurse N levels.
        runtime:   LLM runtime (auto-injected).
    """
    root = Path(wiki_root).expanduser().resolve()
    topic_md = find_node(root, topic)
    if topic_md is None:
        return f"Error: topic '{topic}' not found in {root}"

    topic_dir = topic_md.parent
    paper_pages: list[Path] = []
    subtopic_pages: list[Path] = []
    for child in sorted(topic_dir.iterdir()):
        if not child.is_dir():
            continue
        child_md = child / f"{child.name}.md"
        if not child_md.exists():
            continue
        # Distinguish paper vs subtopic by frontmatter `type:`.
        fm, _ = parse_frontmatter(child_md.read_text(errors="ignore"))
        if fm.get("type") == "paper":
            paper_pages.append(child_md)
        else:
            subtopic_pages.append(child_md)

    if not paper_pages and not subtopic_pages:
        return (
            f"Topic '{topic}' has no child paper or subtopic pages yet. "
            f"Ingest papers under {topic_dir} before running survey."
        )

    current_body = topic_md.read_text(encoding="utf-8")

    prompt = (
        f"=== Topic ===\n"
        f"topic_name: {topic}\n"
        f"topic_md_path: {topic_md}\n"
        f"recurse_depth: {depth}\n\n"
        f"=== Paper pages ({len(paper_pages)}) ===\n"
        + "\n".join(str(p) for p in paper_pages)
        + "\n\n"
        f"=== Subtopic pages ({len(subtopic_pages)}) ===\n"
        + ("\n".join(str(p) for p in subtopic_pages) or "(none)")
        + "\n\n"
        f"=== Current topic page (entire file) ===\n{current_body}\n\n"
        f"Read each paper page, cluster them, rewrite the topic page "
        f"body. Preserve frontmatter.\n\n"
        f"If recurse_depth > 0, after rewriting this topic page, "
        f"recursively rewrite each subtopic's same-named .md the same "
        f"way, decrementing depth each level. Apply the same Wikipedia "
        f"prose conventions throughout."
    )

    llm_summary = runtime.exec(content=[{"type": "text", "text": prompt}])
    committed = git_commit_all(root, f"wiki: survey {topic}")
    suffix = " (committed)" if committed else " (no changes to commit)"
    return f"{llm_summary}\n\n[survey done]{suffix}"
