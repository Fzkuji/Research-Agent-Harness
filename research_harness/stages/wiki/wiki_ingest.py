"""wiki_ingest — universal single-source ingest.

Accepts any source: arXiv id, http(s) URL (HuggingFace, blog,
GitHub raw, vendor whitepaper), or a local PDF path. Python
detects which, prepares whatever pre-work is cheap (arXiv API
fetch for arXiv ids), and the LLM handles fetch + parse + place
for everything else.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.stages.wiki._helpers import (
    download_arxiv_pdf,
    ensure_git_repo,
    fetch_arxiv_metadata,
    folder_tree,
    git_commit_all,
    last_name,
    slugify,
)


_ARXIV_ID_RE = re.compile(r"^(?:arXiv:)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
_ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", re.IGNORECASE)


def _extract_figures(pdf_path: Path, out_dir: Path) -> list[str]:
    """Best-effort PDF figure extraction via the pdf tool. Returns list
    of extracted absolute paths. Silent on failure."""
    try:
        from openprogram.functions.tools.pdf import execute as pdf_execute
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_execute(
            file_path=str(pdf_path),
            extract_images=True,
            image_out_dir=str(out_dir),
            max_chars=1000,  # we only want figures here, not the text dump
        )
        return [str(p) for p in sorted(out_dir.glob("*.png"))]
    except Exception:
        return []


def _figures_block(figures_dir: Optional[Path], staged: list[str], slug: str) -> str:
    if not figures_dir or not staged:
        return "figures: (none extracted)"
    lines = [
        f"figures_staged_at: {figures_dir}",
        f"After creating the paper folder at <topic-path>/{slug}/, "
        "create a `figures/` subfolder inside it, then `mv` the "
        "1-8 figures you find most informative (architecture diagrams, "
        "key result plots) into it. `rm -rf` the rest. Embed kept "
        "figures into the paper page with `![](figures/<filename>)` "
        "and a 1-3 sentence caption explaining what each figure shows.",
        "",
        "Available staged figures:",
    ]
    lines.extend(f"  - {p}" for p in staged)
    return "\n".join(lines)


def _detect(source: str) -> tuple[str, Optional[str]]:
    """Classify the source. Returns (kind, normalized) where kind is
    one of 'arxiv', 'url', 'file', 'unknown' and normalized is the
    arxiv id when kind=='arxiv', else the cleaned source string.
    """
    s = source.strip()
    m = _ARXIV_ID_RE.match(s)
    if m:
        return "arxiv", m.group(1)
    m = _ARXIV_URL_RE.search(s)
    if m:
        return "arxiv", m.group(1)
    if s.startswith(("http://", "https://")):
        return "url", s
    if Path(s).expanduser().exists():
        return "file", str(Path(s).expanduser().resolve())
    return "unknown", s


@agentic_function()
def wiki_ingest(source: str, wiki_root: str, runtime: Runtime) -> str:
    """Ingest any source into the wiki — arXiv id, URL, or local PDF.

    The function decides what `source` is and either:
    - For an arXiv id: Python fetches metadata + PDF, then the LLM
      writes the paper page and integrates the parent topic.
    - For any other URL or PDF file: the LLM fetches via web_fetch
      or the pdf tool, extracts metadata, picks a topic, writes the
      paper page and integrates the parent topic.

    Regardless of source kind, the on-disk schema is identical:
    `<canonical-topic-folder>/<slug>/<slug>.md` with
    `type: paper` frontmatter, body sections (One-line thesis /
    Problem / Method / Key Results / Limitations), and a paragraph
    integration into the parent topic.

    ═══════════════════════════════════════════════════════════════
    YOUR JOB
    ═══════════════════════════════════════════════════════════════

    Read the task header in the next message — it tells you the
    `kind` (arxiv / url / file / unknown) and any pre-fetched
    metadata. Then:

    1. If kind == arxiv, all metadata is already provided in the
       header (title, authors, year, abstract, slug). Skip to step 3.

       If kind == url, use web_fetch (or pdf tool for direct .pdf
       URLs) on the source. Extract title, authors (first 4-8),
       year, venue, abstract / executive summary.

       If kind == file, use the pdf tool to extract text from the
       local PDF. Extract the same metadata fields.

       If kind == unknown, try web_fetch on the source string anyway
       — it might still be a URL the heuristic missed. If that
       fails, report and stop.

    2. Generate slug: `<lastauthor><year>_<keyword>` — lowercase
       last name + 4-digit year + 1-3 title keywords joined by
       underscores. (Already provided when kind == arxiv.)

    3. Choose canonical topic path. Read the folder tree in the
       message header. Path must be HIERARCHICAL (≥3 levels from
       broad → narrow). If the vault has a matching prefix, extend
       it (e.g. add a new leaf folder under an existing parent
       chain). If empty, propose a 3-level path appropriate to the
       paper. Title case English, no decimal prefixes.

       Example paths:
       - `Large Language Models/Pretraining/Mixture of Experts`
       - `Large Language Models/Reasoning/Reinforcement learning from verifier`
       - `Computer Vision/Diffusion models/Score-based generation`

    4. Create the paper folder and page at
       `<topic-path>/<slug>/<slug>.md`. Frontmatter:

       ```yaml
       ---
       type: paper
       arxiv: "<id or empty>"
       url: "<source url or empty>"
       year: <year>
       title: "<full title>"
       authors:
         - "<author 1>"
       venue: "<venue>"
       topics: []
       ---
       ```

       Body sections to fill:
       - `## One-line thesis`
       - `## Problem`
       - `## Method`
       - `## Key Results`
       - `## Limitations`

       Use only what the source actually states. Mark inferences
       drawn solely from an abstract / executive summary with
       "(from abstract; verify against full text)" rather than
       fabricating numbers.

    5. Integrate into the parent topic's same-named `.md` — add a
       paragraph discussing this paper in context, referencing it
       via `[[<slug>]]`. If the topic page is empty or a stub
       (<200 words body), write a short opening paragraph.

    6. Report: canonical topic path, slug, one-line thesis, any
       caveats.

    Args:
        source:    arXiv id, URL, or local PDF path.
        wiki_root: Vault root.
        runtime:   LLM runtime (auto-injected).
    """
    root = Path(wiki_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    ensure_git_repo(root)

    kind, normalized = _detect(source)

    header_parts = [
        f"=== Source kind ===\n{kind}",
        f"=== Source normalized ===\n{normalized}",
    ]

    import tempfile
    figures_staged: list[str] = []
    figures_dir: Optional[Path] = None

    if kind == "arxiv":
        try:
            meta = fetch_arxiv_metadata(normalized)
        except RuntimeError as e:
            return f"Error: arXiv fetch failed: {e}"
        author1 = last_name(meta["authors"][0]) if meta["authors"] else ""
        slug = slugify(meta["title"], author1, meta["year"])
        pdf_dest = Path(tempfile.gettempdir()) / f"wiki-ingest-{slug}.pdf"
        pdf_ok = download_arxiv_pdf(meta["arxiv_id"], pdf_dest)

        # Extract figures from the staged PDF.
        if pdf_ok:
            figures_dir = Path(tempfile.gettempdir()) / f"wiki-ingest-figs-{slug}"
            figures_staged = _extract_figures(pdf_dest, figures_dir)

        authors_yaml = "\n".join(f'  - "{a}"' for a in meta["authors"][:8])
        pdf_line = (
            f"pdf_staged_at: {pdf_dest} (mv into <paper-folder>/{slug}.pdf)"
            if pdf_ok else "pdf: download failed (skip)"
        )
        figs_line = _figures_block(figures_dir, figures_staged, slug)
        header_parts.append(
            "=== arXiv metadata (use verbatim) ===\n"
            f"arxiv_id: {meta['arxiv_id']}\n"
            f"slug: {slug}\n"
            f"title: {meta['title']}\n"
            f"year: {meta['year']}\n"
            f"venue: {meta['venue']}\n"
            f"primary_category: {meta['primary_category']}\n"
            f"authors:\n{authors_yaml}\n\n"
            f"abstract:\n{meta['abstract']}\n\n"
            f"{pdf_line}\n\n{figs_line}"
        )
    elif kind == "file" and normalized and normalized.lower().endswith(".pdf"):
        # Local PDF source — pre-extract figures so the LLM has a
        # ready inventory.
        local_pdf = Path(normalized)
        figures_dir = Path(tempfile.gettempdir()) / f"wiki-ingest-figs-{local_pdf.stem}"
        figures_staged = _extract_figures(local_pdf, figures_dir)
        figs_line = _figures_block(figures_dir, figures_staged, local_pdf.stem)

        # Detect "drop folder": source is inside the vault, in a
        # folder dedicated to it (not a top-level subject folder).
        # In that case the whole folder + siblings (videos, slides,
        # etc.) should migrate into the new paper folder.
        drop_block = ""
        try:
            rel = local_pdf.relative_to(root)
            if len(rel.parts) >= 2:
                drop_folder = local_pdf.parent
                siblings = sorted(p for p in drop_folder.iterdir() if p != local_pdf)
                drop_block = (
                    f"\n\n=== Drop folder detected ===\n"
                    f"This PDF sits inside `{drop_folder}` which appears "
                    f"to be a drop folder for related materials.\n"
                    f"After creating the paper folder, also `mv` these "
                    f"sibling files into the paper folder and then "
                    f"`rmdir` the empty drop folder:\n"
                    + "\n".join(f"  - {s}" for s in siblings)
                )
        except ValueError:
            pass  # not under vault root

        header_parts.append(
            "=== Note ===\nLocal PDF. Use the pdf tool to read text. "
            "Extract title/authors/year/abstract from the first 1-2 "
            f"pages.\n\n{figs_line}{drop_block}"
        )
    else:
        header_parts.append(
            "=== Note ===\nNo arXiv metadata available. You must "
            "fetch the source yourself (web_fetch / pdf tool) and "
            "extract title/authors/year/abstract before writing the "
            "paper page. For PDF sources, the pdf tool now supports "
            "extract_images=True + image_out_dir=<some tmp path> to "
            "pull figures alongside the text."
        )

    header_parts.append(f"=== Vault root ===\n{root}")
    header_parts.append(f"=== Existing topic folder tree ===\n{folder_tree(root) or '(empty)'}")
    header_parts.append(
        "Proceed with the 6-step workflow. Use the existing topic "
        "tree where possible — extend it with new leaf folders rather "
        "than starting fresh trees."
    )

    prompt = "\n\n".join(header_parts)
    llm_summary = runtime.exec(content=[{"type": "text", "text": prompt}])

    committed = git_commit_all(root, f"wiki: ingest {source[:80]}")
    suffix = " (committed)" if committed else " (no changes to commit)"
    return f"{llm_summary}\n\n[ingest done | kind={kind}]{suffix}"
