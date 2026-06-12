"""wiki_import_litreview — bulk import an existing literature review project.

A `stages/literature/` project produces:
  litreview_root/
    papers/<arxiv_id>.pdf
    topics/<framework_path>/_overview.md
    topics/<framework_path>/arXiv_<id>.md     (one per paper)
    synthesis/

This importer mirrors the topics/ subtree into the wiki at a chosen
target prefix, preserving the annotations and survey content already
there. Pure Python, no LLM. Idempotent (skips already-present slugs).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from research_harness.stages.wiki._helpers import (
    dump_frontmatter,
    ensure_git_repo,
    git_commit_all,
    last_name,
    slugify,
)


_HEADER_RE = re.compile(r"^- \*\*([A-Z][A-Za-z ]*)\*\*: (.+)$", re.MULTILINE)
_TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)
_SECTION_RE = re.compile(r"^## ([^\n]+)$", re.MULTILINE)


def _parse_annotation(path: Path) -> dict:
    """Parse a `arXiv_<id>.md` annotation into a dict.

    Returns: {title, authors, year, venue, citations, topic, arxiv_id,
              pdf_rel, abstract, contribution, raw}
    """
    text = path.read_text(errors="ignore")
    out: dict = {"raw": text, "title": "", "authors": [], "year": 0,
                 "venue": "", "citations": 0, "topic": "", "arxiv_id": "",
                 "pdf_rel": "", "abstract": "", "contribution": ""}

    m = _TITLE_RE.search(text)
    if m:
        out["title"] = m.group(1).strip()

    # Parse the bullet header lines.
    bullets: dict[str, str] = {}
    for m in _HEADER_RE.finditer(text):
        bullets[m.group(1).strip()] = m.group(2).strip()
    if "ID" in bullets:
        aid = bullets["ID"].replace("arXiv:", "").strip().split()[0]
        out["arxiv_id"] = aid
    if "Authors" in bullets:
        out["authors"] = [a.strip() for a in bullets["Authors"].split(",") if a.strip()]
    if "Year" in bullets:
        # Year may have ", Venue: X" suffix on the same bullet.
        y = re.match(r"\s*(\d{4})", bullets["Year"])
        if y:
            out["year"] = int(y.group(1))
    if "Venue" in bullets:
        out["venue"] = bullets["Venue"].strip()
    elif "Year" in bullets:
        ven = re.search(r"Venue:\s*([^,]+)", bullets["Year"])
        if ven:
            out["venue"] = ven.group(1).strip()
    if "Citations" in bullets:
        try:
            out["citations"] = int(re.sub(r"\D", "", bullets["Citations"]))
        except ValueError:
            pass
    if "Topic" in bullets:
        out["topic"] = bullets["Topic"].strip()
    if "PDF" in bullets:
        out["pdf_rel"] = bullets["PDF"].strip("` ")

    # Split sections.
    sections = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(sections):
        head = m.group(1).strip().lower()
        start = m.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[start:end].strip()
        if head.startswith("abstract"):
            out["abstract"] = body
        elif head.startswith("contribution"):
            out["contribution"] = body

    return out


def _parse_overview(path: Path) -> dict:
    """Parse `_overview.md` into {description, open_questions, raw}."""
    text = path.read_text(errors="ignore")
    out = {"raw": text, "description": "", "open_questions": ""}
    sections = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(sections):
        head = m.group(1).strip().lower()
        start = m.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[start:end].strip()
        if head.startswith("description"):
            out["description"] = body
        elif "open question" in head:
            out["open_questions"] = body
    return out


def _write_topic_page(target_dir: Path, name: str, overview: dict, paper_slugs: list[str]):
    """Write the topic same-named .md from overview + paper slug list."""
    target_dir.mkdir(parents=True, exist_ok=True)
    page = target_dir / f"{name}.md"
    if page.exists():
        # Don't overwrite an LLM-written topic page; just append the paper list.
        existing = page.read_text(encoding="utf-8")
        if "## Papers" not in existing:
            with page.open("a") as f:
                f.write("\n\n## Papers\n\n")
                for s in paper_slugs:
                    f.write(f"- [[{s}]]\n")
        return

    fm = {"type": "topic"}
    body_parts = [f"\n# {name}\n"]
    if overview.get("description"):
        body_parts.append(overview["description"] + "\n")
    if overview.get("open_questions"):
        body_parts.append(f"## Open questions\n\n{overview['open_questions']}\n")
    if paper_slugs:
        body_parts.append("## Papers\n")
        for s in paper_slugs:
            body_parts.append(f"- [[{s}]]")
        body_parts.append("")
    page.write_text(dump_frontmatter(fm, "\n".join(body_parts)), encoding="utf-8")


def _write_paper_page(target_dir: Path, slug: str, ann: dict):
    paper_dir = target_dir / slug
    paper_dir.mkdir(parents=True, exist_ok=True)
    page = paper_dir / f"{slug}.md"
    if page.exists():
        return False
    fm = {
        "type": "paper",
        "arxiv": ann["arxiv_id"],
        "year": ann["year"],
        "title": ann["title"],
        "authors": ann["authors"][:8],
        "venue": ann["venue"],
        "citations": ann["citations"],
        "topics": [],
    }
    body = "\n".join([
        f"\n# {ann['title']}\n",
        "## One-line thesis\n",
        f"{(ann['contribution'].split('.')[0] + '.').strip() if ann['contribution'] else '(imported; see Contribution below)'}\n",
        "## Abstract\n",
        f"{ann['abstract'] or '(no abstract captured in source)'}\n",
        "## Contribution\n",
        f"{ann['contribution'] or '(no contribution annotation in source)'}\n",
    ])
    page.write_text(dump_frontmatter(fm, body), encoding="utf-8")
    return True


def wiki_import_litreview(
    litreview_root: str,
    wiki_root: str,
    target_topic_prefix: str,
) -> str:
    """Import a literature-review project's topics/ subtree into the wiki.

    Args:
        litreview_root:      Directory containing `topics/`, `papers/`,
                             `synthesis/`. Typically a path like
                             `<project>/literature review/`.
        wiki_root:           Vault root.
        target_topic_prefix: Where to mount the imported subtree under
                             the wiki, e.g.
                             `Large Language Models/Post-Training/Trajectory Provenance`.

    Pure Python. Preserves the original Abstract and Contribution
    annotations on each paper. Idempotent: papers whose slug folders
    already exist are skipped.
    """
    src = Path(litreview_root).expanduser().resolve()
    dst_root = Path(wiki_root).expanduser().resolve()
    dst_root.mkdir(parents=True, exist_ok=True)
    ensure_git_repo(dst_root)

    topics_dir = src / "topics"
    if not topics_dir.exists():
        return f"Error: no topics/ folder at {src}"

    # Walk the framework — there's usually ONE top-level framework
    # folder under topics/. Find it, then mirror its subtree.
    top_folders = [p for p in topics_dir.iterdir() if p.is_dir()]
    if not top_folders:
        return f"Error: topics/ is empty at {src}"
    # Pick the deepest-content one (largest by descendant count).
    framework_root = max(top_folders, key=lambda p: len(list(p.rglob("*.md"))))

    papers_added = 0
    topics_added = 0
    pdfs_copied = 0
    skipped = 0

    for topic_dir in [framework_root] + sorted(
        [p for p in framework_root.rglob("*") if p.is_dir()]
    ):
        relative = topic_dir.relative_to(framework_root.parent)
        # relative is e.g.
        #   "Off-Policy and On-Policy Learning in LLM Post-Training/Off-Policy Post-Training"
        # We strip the topmost segment (the framework name) so the import
        # mounts ITS CHILDREN at target_topic_prefix, not under another
        # nested folder with the framework's long name.
        if len(relative.parts) == 1:
            target_dir = dst_root / target_topic_prefix
        else:
            sub = Path(*relative.parts[1:])
            target_dir = dst_root / target_topic_prefix / sub

        # Collect paper annotations in this topic_dir.
        paper_slugs: list[str] = []
        for paper_md in sorted(topic_dir.glob("arXiv_*.md")):
            ann = _parse_annotation(paper_md)
            if not ann["arxiv_id"] or not ann["title"]:
                skipped += 1
                continue
            author1 = last_name(ann["authors"][0]) if ann["authors"] else ""
            slug = slugify(ann["title"], author1, ann["year"])

            paper_slugs.append(slug)
            if _write_paper_page(target_dir, slug, ann):
                papers_added += 1
            else:
                skipped += 1

            # Copy PDF into the paper's own folder, next to its .md.
            arxiv_id = ann["arxiv_id"]
            src_pdf = src / "papers" / f"{arxiv_id}.pdf"
            if src_pdf.exists():
                dst_pdf = target_dir / slug / f"{slug}.pdf"
                if not dst_pdf.exists():
                    shutil.copy2(src_pdf, dst_pdf)
                    pdfs_copied += 1

        # Write the topic page from _overview.md.
        overview_md = topic_dir / "_overview.md"
        overview = _parse_overview(overview_md) if overview_md.exists() else {}
        _write_topic_page(target_dir, target_dir.name, overview, paper_slugs)
        topics_added += 1

    committed = git_commit_all(
        dst_root,
        f"wiki: import litreview from {src.parent.name} "
        f"({papers_added} papers, {topics_added} topics)",
    )
    return (
        f"Imported {papers_added} papers, {topics_added} topics, "
        f"{pdfs_copied} PDFs (skipped {skipped} dupes/invalid)"
        + (" — committed" if committed else " — nothing to commit")
    )
