"""wiki_lint — scan the vault for schema and link health."""

from __future__ import annotations

import re
from pathlib import Path

from research_harness.stages.wiki._helpers import (
    iter_md_files,
    parse_frontmatter,
)

_WIKILINK_RE = re.compile(r"\[\[([^\[\]\|#]+?)(\|[^\[\]]+)?(#[^\[\]]+)?\]\]")


def wiki_lint(wiki_root: str) -> str:
    """Scan the vault and report schema / link / structure issues.

    Read-only. Writes a `lint-report.md` at the vault root summarizing:

    1. Pages missing the required `type:` frontmatter.
    2. Pages with `type:` neither `paper` nor `topic`.
    3. Folders that contain a `.md` but the filename stem does not match
       the folder name (violates the same-named convention).
    4. Wikilinks that point to a target the vault does not contain.
    5. Orphan pages: no inbound wikilinks AND no outbound wikilinks.
    6. Paper pages missing required frontmatter keys (`arxiv`, `year`,
       `title`, `authors`).

    Returns a one-line status; the full report is the file.
    """
    root = Path(wiki_root).expanduser().resolve()
    if not root.exists():
        return f"Error: {root} does not exist"

    all_pages: dict[str, Path] = {}
    page_frontmatter: dict[Path, dict] = {}
    outbound: dict[Path, set[str]] = {}
    inbound_count: dict[str, int] = {}

    issues_missing_type: list[str] = []
    issues_bad_type: list[str] = []
    issues_naming: list[str] = []
    issues_paper_missing_fields: list[str] = []

    scaffolding = {root / "AGENTS.md", root / "README.md", root / "lint-report.md"}

    for md in iter_md_files(root):
        if md in scaffolding:
            continue
        all_pages[md.stem] = md
        text = md.read_text(errors="ignore")
        fm, _ = parse_frontmatter(text)
        page_frontmatter[md] = fm

        # Naming: file stem must equal parent folder name (except top-level vault docs).
        if md.parent != root and md.stem != md.parent.name:
            issues_naming.append(
                f"{md.relative_to(root)} — stem '{md.stem}' != folder '{md.parent.name}'"
            )

        # Type check.
        t = fm.get("type")
        if not t:
            issues_missing_type.append(str(md.relative_to(root)))
        elif t not in ("paper", "topic"):
            issues_bad_type.append(f"{md.relative_to(root)} — type={t!r}")

        # Paper required fields.
        if t == "paper":
            for k in ("arxiv", "year", "title", "authors"):
                if not fm.get(k):
                    issues_paper_missing_fields.append(
                        f"{md.relative_to(root)} — missing {k}"
                    )

        # Outbound wikilinks — skip content inside fenced code blocks.
        text_no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text_no_code = re.sub(r"`[^`]+`", "", text_no_code)
        outs: set[str] = set()
        for m in _WIKILINK_RE.finditer(text_no_code):
            outs.add(m.group(1).strip())
        # Also pick up frontmatter wikilink values (topics: [[Foo]]).
        for v in fm.values():
            if isinstance(v, list):
                for item in v:
                    m = _WIKILINK_RE.search(str(item))
                    if m:
                        outs.add(m.group(1).strip())
        outbound[md] = outs

    for outs in outbound.values():
        for t in outs:
            inbound_count[t] = inbound_count.get(t, 0) + 1

    issues_broken_links: list[str] = []
    for md, outs in outbound.items():
        for t in outs:
            if t not in all_pages:
                issues_broken_links.append(
                    f"{md.relative_to(root)} → [[{t}]] (no such page)"
                )

    issues_orphans: list[str] = []
    for md in outbound:
        stem = md.stem
        if not outbound[md] and inbound_count.get(stem, 0) == 0:
            if md.parent == root:
                continue  # README.md / AGENTS.md at root are not orphans
            issues_orphans.append(str(md.relative_to(root)))

    lines = [
        "# Wiki lint report",
        "",
        f"Pages scanned: {len(all_pages)}",
        "",
    ]

    def _section(title: str, items: list[str]):
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_None._")
        else:
            for it in items:
                lines.append(f"- {it}")
        lines.append("")

    _section("Pages missing `type:` frontmatter", issues_missing_type)
    _section("Pages with bad `type:` value", issues_bad_type)
    _section("Filename does not match folder", issues_naming)
    _section("Paper pages missing required fields", issues_paper_missing_fields)
    _section("Broken wikilinks", issues_broken_links)
    _section("Orphan pages (no inbound, no outbound)", issues_orphans)

    report = root / "lint-report.md"
    report.write_text("\n".join(lines))

    total = (
        len(issues_missing_type) + len(issues_bad_type) + len(issues_naming)
        + len(issues_paper_missing_fields) + len(issues_broken_links)
        + len(issues_orphans)
    )
    return (
        f"Lint complete: scanned {len(all_pages)} pages, {total} issues. "
        f"Report at {report.relative_to(root)}."
    )
