"""wiki_rename — rename a node and rewrite all wikilinks in the vault."""

from __future__ import annotations

import shutil
from pathlib import Path

from research_harness.stages.wiki._helpers import (
    find_node,
    git_commit_all,
    rewrite_wikilinks,
)


def wiki_rename(old_name: str, new_name: str, wiki_root: str) -> str:
    """Rename a topic or paper node and rewrite all wikilinks pointing to it.

    Moves the `<old>/<old>.md` folder to `<new>/<new>.md`, renames the
    inner `.md` accordingly, then scans the entire vault and rewrites
    `[[old]]` → `[[new]]` in both markdown body and YAML frontmatter
    values. Commits the result.

    Args:
        old_name: Current filename stem (e.g., "Preference optimization").
        new_name: New filename stem.
        wiki_root: Absolute path to the wiki vault root.

    Returns:
        Status string describing what changed.
    """
    root = Path(wiki_root).expanduser().resolve()
    if not root.exists():
        return f"Error: wiki root {root} does not exist"

    old_md = find_node(root, old_name)
    if old_md is None:
        return f"Error: node '{old_name}' not found in {root}"

    old_dir = old_md.parent
    new_dir = old_dir.parent / new_name
    if new_dir.exists():
        return f"Error: target '{new_name}' already exists at {new_dir}"

    shutil.move(str(old_dir), str(new_dir))
    new_md = new_dir / f"{old_name}.md"
    if new_md.exists():
        new_md.rename(new_dir / f"{new_name}.md")

    changed = rewrite_wikilinks(root, old_name, new_name)
    committed = git_commit_all(
        root,
        f"wiki: rename {old_name} -> {new_name} (rewrote {changed} files)",
    )
    return (
        f"Renamed {old_name} -> {new_name}; rewrote wikilinks in {changed} files"
        + (" (committed)" if committed else "")
    )
