"""wiki_migrate — backfill `type:` frontmatter on legacy notes."""

from __future__ import annotations

from pathlib import Path

from research_harness.stages.wiki._helpers import (
    dump_frontmatter,
    git_commit_all,
    iter_md_files,
    parse_frontmatter,
)


def wiki_migrate(wiki_root: str, default_type: str) -> str:
    """Add `type:` frontmatter to every page that lacks it.

    Walks the vault, finds `.md` files with no `type:` field, and
    inserts one. Folder + same-named pages are treated as topics
    unless a heuristic flags them as papers (frontmatter contains
    `arxiv:` / `year:` / `authors:` is the only signal — without
    these, we can't tell, so we default to the caller's choice).

    Use `default_type="topic"` when importing a hierarchical notes
    folder (e.g. an awesome-AI-style subject tree). Use
    `default_type="paper"` only for a flat dump of paper notes.

    Args:
        wiki_root:    Vault root.
        default_type: `"topic"` or `"paper"` — what to write when
                      heuristics give nothing.

    Returns:
        Status string with count of pages migrated.
    """
    if default_type not in ("topic", "paper"):
        return f"Error: default_type must be 'topic' or 'paper', got {default_type!r}"

    root = Path(wiki_root).expanduser().resolve()
    if not root.exists():
        return f"Error: {root} does not exist"

    migrated = 0
    skipped = 0
    for md in iter_md_files(root):
        text = md.read_text(errors="ignore")
        fm, body = parse_frontmatter(text)
        if fm.get("type"):
            skipped += 1
            continue
        # Paper heuristic: existing frontmatter carries paper-ish fields.
        inferred = default_type
        if any(k in fm for k in ("arxiv", "authors", "venue")):
            inferred = "paper"
        new_fm = {"type": inferred, **fm}
        md.write_text(dump_frontmatter(new_fm, body if body.startswith("\n") else "\n" + body), encoding="utf-8")
        migrated += 1

    committed = git_commit_all(
        root, f"wiki: migrate {migrated} legacy pages (default type={default_type})"
    ) if migrated else False

    return (
        f"Migrated {migrated} pages (skipped {skipped} already-typed)"
        + (" — committed" if committed else "")
    )
