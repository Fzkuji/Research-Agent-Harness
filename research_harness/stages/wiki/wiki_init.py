"""wiki_init — initialize a new wiki vault."""

from __future__ import annotations

from pathlib import Path

from research_harness.stages.wiki._helpers import (
    ensure_git_repo,
    git_commit_all,
)

try:
    from wiki_agent_harness import Wiki as _WAHWiki
    _HAS_WAH = True
except ImportError:
    _HAS_WAH = False

_AGENTS_MD = """# AGENTS.md — Wiki Schema

This file governs page structure, naming, and link conventions for the
wiki. Edit this file to change behavior; the code reads it as the
single source of truth.

## Node shape

Every entity — topic or paper — is a folder containing a same-named
`.md` file. Folder name and filename stem are identical. Children
(subtopics, contained papers) are sibling folders inside the parent.

## Required frontmatter

Every `.md` MUST start with YAML frontmatter declaring `type:`:

- Topic page: `type: topic`
- Paper page: `type: paper`

Paper pages additionally have: `arxiv`, `year`, `authors`, `title`,
`venue`, `topics` (list of `[[wikilinks]]` to topic pages this paper
belongs to beyond its canonical location).

## Naming

- **Folder name and the same-named `.md` inside it must match
  verbatim.** No prefix stripping, no case smoothing. If a folder is
  called `4. AI/`, its page is `4. AI/4. AI.md`, not `4. AI/AI.md`.
- Topics: prefer English, title case, space-separated words (e.g.,
  `Preference optimization`). Decimal prefixes for sort order are
  optional; if used, apply them consistently to both folder and file
  stem.
- Papers: slug `<lastname><year>_<keyword>` — e.g.,
  `rafailov2023_direct_preference_optimization`.

## Wikilinks

- Always filename-only: `[[Preference optimization]]`, never with path.
- Alias allowed: `[[rafailov2023_direct_preference_optimization|DPO]]`.
- Section anchor allowed: `[[Post-training#Open questions]]`.

## Cross-topic membership (Wikipedia categories model)

A paper lives in **one** canonical folder. To declare it also belongs
to other topics, list them in the paper's frontmatter `topics:`. The
non-canonical topic pages render their paper list via Obsidian
Dataview / backlinks; they do not contain duplicate files.

## Attachments

Images live in `Attachments/` at the vault root, flat. Reference them
by relative path from any page: `![](Attachments/<slug>-1.png)`.

## Disambiguation

Filename collisions are resolved manually with parenthetical
qualifiers: `Inference (statistics)`, `Inference (neural networks)`.
A disambiguation page at the bare name is optional.
"""

_README_MD = """# Research Wiki

A persistent, Obsidian-friendly research knowledge base. Open this
directory as an Obsidian vault.

- `AGENTS.md` — schema and conventions (read before editing)
- Top-level folders — subject taxonomy
- `Attachments/` — images

Maintained by `research_harness/stages/wiki/`. See that module's
`README.md` for the design.
"""


def wiki_init(wiki_root: str) -> str:
    """Initialize a new wiki vault at the given path.

    When ``wiki_agent_harness`` is installed the vault is initialized
    via :class:`wiki_agent_harness.Wiki` (which handles directory
    creation, AGENTS.md, and git scaffolding internally).  Otherwise
    the local scaffolding logic is used.

    Idempotent: re-running on an existing vault is a no-op.

    Args:
        wiki_root: Absolute path to the wiki vault root.

    Returns:
        A one-line status string.
    """
    root = Path(wiki_root).expanduser().resolve()

    # wiki_agent_harness.Wiki only mkdirs the root. We always do our
    # own minimal scaffolding (README + git) regardless of WAH.
    if _HAS_WAH:
        _WAHWiki(root=root)
    else:
        root.mkdir(parents=True, exist_ok=True)

    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(_README_MD)

    ensure_git_repo(root)
    committed = git_commit_all(root, "wiki: init vault scaffolding")
    suffix_src = " (via wiki_agent_harness)" if _HAS_WAH else ""
    return (
        f"Wiki initialized at {root}{suffix_src}"
        + (" (committed scaffolding)" if committed else " (already up to date)")
    )
