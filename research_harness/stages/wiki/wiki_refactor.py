"""wiki_refactor — split a crowded topic into subtopics."""

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
def wiki_refactor(topic: str, wiki_root: str, runtime: Runtime) -> str:
    """Split an over-crowded topic into subtopic folders.

    When a topic has accumulated too many direct paper children, this
    operation proposes a partitioning of those papers into 2–4
    natural subtopic clusters, creates the subtopic folders, and
    moves the paper folders into them. The wikilink rewriter keeps
    all references intact (paper slugs do not change, so wikilinks
    pointing to papers remain valid; what changes is the on-disk
    parent of each paper folder).

    ═══════════════════════════════════════════════════════════════
    INPUT (in the next message)
    ═══════════════════════════════════════════════════════════════

    - topic_name and absolute path to its same-named `.md`
    - List of paper folders currently directly under the topic
    - Existing subtopic folders (if any) — their names and one-line
      summaries

    ═══════════════════════════════════════════════════════════════
    YOUR JOB
    ═══════════════════════════════════════════════════════════════

    1. Read enough of each paper page (the `## One-line thesis` and
       `## Method` sections) to understand its specific area.
    2. Propose 2–4 subtopic names that cleanly partition the papers.
       Subtopic names must be English, title case, space-separated.
       Avoid creating a subtopic that would contain a single paper
       unless that paper is genuinely standalone.
    3. For each subtopic:
       a. Create the subtopic folder under the parent topic.
       b. Write the subtopic's same-named `.md` with frontmatter
          `type: topic` and a short opening paragraph.
       c. Use the bash `mv` tool (or list+move pattern via the Edit
          tools) to move each assigned paper folder from
          `<topic>/<paper>/` to `<topic>/<subtopic>/<paper>/`.
    4. Rewrite the parent topic's same-named `.md` body to mention
       the new subtopics as a `## Subtopics` section with wikilinks,
       and update the rest of the prose so paper discussions still
       make sense (they may now reference papers via wikilink that
       have moved).
    5. Return: subtopic names, papers in each, anything that didn't
       fit naturally.

    Args:
        topic:     Filename stem of the topic to refactor.
        wiki_root: Vault root.
        runtime:   LLM runtime (auto-injected).
    """
    root = Path(wiki_root).expanduser().resolve()
    topic_md = find_node(root, topic)
    if topic_md is None:
        return f"Error: topic '{topic}' not found in {root}"

    topic_dir = topic_md.parent
    paper_folders: list[Path] = []
    existing_subtopics: list[Path] = []
    for child in sorted(topic_dir.iterdir()):
        if not child.is_dir():
            continue
        child_md = child / f"{child.name}.md"
        if not child_md.exists():
            continue
        fm, _ = parse_frontmatter(child_md.read_text(errors="ignore"))
        if fm.get("type") == "paper":
            paper_folders.append(child)
        else:
            existing_subtopics.append(child)

    if len(paper_folders) < 3:
        return (
            f"Topic '{topic}' has only {len(paper_folders)} direct papers. "
            f"Refactor is for crowded topics (typically 10+ papers); "
            f"nothing to do."
        )

    paper_list = "\n".join(str(p) for p in paper_folders)
    subtopic_list = "\n".join(str(p) for p in existing_subtopics) or "(none)"

    prompt = (
        f"=== Topic to refactor ===\n"
        f"topic_name: {topic}\n"
        f"topic_md_path: {topic_md}\n"
        f"topic_dir: {topic_dir}\n\n"
        f"=== Direct paper folders ({len(paper_folders)}) ===\n{paper_list}\n\n"
        f"=== Existing subtopic folders ({len(existing_subtopics)}) ===\n"
        f"{subtopic_list}\n\n"
        f"Read each paper's one-line thesis and method, propose 2–4 "
        f"subtopics, create them, move the paper folders, and rewrite "
        f"the parent topic page."
    )

    llm_summary = runtime.exec(content=[{"type": "text", "text": prompt}])
    committed = git_commit_all(root, f"wiki: refactor {topic} into subtopics")
    suffix = " (committed)" if committed else " (no changes to commit)"
    return f"{llm_summary}\n\n[refactor done]{suffix}"
