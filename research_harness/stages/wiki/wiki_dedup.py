"""wiki_dedup — collapse cross-listed paper copies to a canonical location."""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path

from research_harness.stages.wiki._helpers import (
    git_commit_all,
    iter_md_files,
    parse_frontmatter,
)


def wiki_dedup(wiki_root: str) -> str:
    """Collapse duplicate paper folders to a single canonical location.

    When a paper folder (`<slug>/<slug>.md` with `type: paper`)
    appears in more than one place in the vault, keep the deepest
    path (most specific subtopic) and remove the other copies.
    Wikilinks elsewhere in the vault continue to resolve because
    wikilinks reference by filename only.

    Idempotent — running on an already-deduped vault is a no-op.

    Args:
        wiki_root: Vault root.

    Returns:
        Status string.
    """
    root = Path(wiki_root).expanduser().resolve()
    if not root.exists():
        return f"Error: {root} does not exist"

    # Group paper folders by slug.
    by_slug: dict[str, list[Path]] = defaultdict(list)
    for md in iter_md_files(root):
        if md.parent == root:
            continue
        if md.stem != md.parent.name:
            continue
        fm, _ = parse_frontmatter(md.read_text(errors="ignore"))
        if fm.get("type") != "paper":
            continue
        by_slug[md.stem].append(md.parent)

    removed = 0
    kept_canonical: list[tuple[str, Path]] = []
    for slug, dirs in by_slug.items():
        if len(dirs) <= 1:
            continue
        # Pick deepest path as canonical; tie-break by lexicographic.
        canonical = max(dirs, key=lambda p: (len(p.parts), str(p)))
        kept_canonical.append((slug, canonical))
        for d in dirs:
            if d == canonical:
                continue
            shutil.rmtree(d)
            removed += 1

    if removed == 0:
        return f"No duplicates to dedup (scanned {len(by_slug)} paper slugs)"

    summary = "\n".join(
        f"- {slug} kept at {c.relative_to(root)}"
        for slug, c in sorted(kept_canonical)
    )
    committed = git_commit_all(
        root, f"wiki: dedup {removed} duplicate paper folders"
    )
    return (
        f"Removed {removed} duplicate paper folders, kept {len(kept_canonical)} "
        f"canonical copies.\n{summary}"
        + ("\n(committed)" if committed else "\n(nothing to commit)")
    )
