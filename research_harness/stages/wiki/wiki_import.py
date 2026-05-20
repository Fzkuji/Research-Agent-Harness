"""wiki_import — bring an external notes directory into the wiki."""

from __future__ import annotations

import shutil
from pathlib import Path

from research_harness.stages.wiki._helpers import (
    git_commit_all,
)


def wiki_import(source: str, wiki_root: str, mode: str) -> str:
    """Import an existing notes directory into the wiki vault.

    Two modes:

    - `link`: the source directory becomes the vault root. No file is
      copied. Subsequent ingest/survey writes land in the source.
      Useful when you already maintain a notes tree (e.g. awesome-AI)
      and want the wiki to grow inside it.
    - `copy`: contents are copied into `wiki_root`. The source stays
      untouched; the vault diverges. Useful for a clean separation.

    After import, run `wiki_migrate(wiki_root, default_type="topic")`
    to backfill `type:` frontmatter on the imported pages, otherwise
    `wiki_lint` will flag them.

    Args:
        source:    Absolute path to the notes directory to import.
        wiki_root: Where the vault should live after this call.
                   - link mode: must equal `source`.
                   - copy mode: must be empty or non-existent (or
                     contain only `wiki_init` scaffolding files).
        mode:      `"link"` or `"copy"`.

    Returns:
        Status string.
    """
    src = Path(source).expanduser().resolve()
    dst = Path(wiki_root).expanduser().resolve()

    if not src.exists() or not src.is_dir():
        return f"Error: source {src} does not exist or is not a directory"

    if mode == "link":
        if src != dst:
            return (
                f"Error: link mode requires wiki_root == source. "
                f"Got wiki_root={dst}, source={src}."
            )
        # Vault is the source as-is. Ensure scaffolding exists.
        from research_harness.stages.wiki.wiki_init import wiki_init
        return wiki_init(str(dst)) + " (link mode)"

    if mode == "copy":
        if dst.exists():
            # Allow only when dst is empty or contains nothing but
            # wiki_init scaffolding.
            allowed = {".git", "AGENTS.md", "README.md", "Attachments"}
            extant = {p.name for p in dst.iterdir()}
            if not extant.issubset(allowed):
                return (
                    f"Error: copy mode requires {dst} to be empty or only "
                    f"contain init scaffolding. Found extra entries: "
                    f"{sorted(extant - allowed)}."
                )
        dst.mkdir(parents=True, exist_ok=True)

        copied = 0
        for item in src.iterdir():
            if item.name in (".git", ".obsidian"):
                continue
            target = dst / item.name
            if target.exists():
                continue
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
            copied += 1

        from research_harness.stages.wiki.wiki_init import wiki_init
        wiki_init(str(dst))
        committed = git_commit_all(
            dst, f"wiki: import {copied} entries from {src.name} (copy mode)"
        )
        return (
            f"Imported {copied} top-level entries from {src} into {dst} "
            f"(copy mode)" + (" — committed" if committed else "")
        )

    return f"Error: unknown mode {mode!r} (use 'link' or 'copy')"
