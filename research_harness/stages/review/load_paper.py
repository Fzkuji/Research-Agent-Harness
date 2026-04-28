"""Unified paper loader.

Accepts any reasonable input format and returns the paper's text content as a
single string for downstream review stages. Dispatches by extension:

  .pdf                    → pdf_to_markdown (LLM-driven, with on-disk cache)
  .docx / .doc            → docx_to_markdown (LLM-driven, with on-disk cache)
  .md / .markdown / .tex  → read directly
  .txt / .rst             → read directly
  .html / .htm            → strip tags, read text
  directory               → scan with priority: .tex (multi-file concat) →
                            .md (concat) → single .pdf → single .docx

Not an @agentic_function: this is plain Python dispatch logic, no LLM call of
its own. PDF / DOCX branches delegate to the agentic stages above.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from openprogram.agentic_programming.runtime import Runtime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLAINTEXT_EXTS = (".md", ".markdown", ".tex", ".txt", ".rst")
PDF_EXTS = (".pdf",)
DOCX_EXTS = (".docx", ".doc")
HTML_EXTS = (".html", ".htm")

MIN_USABLE_LENGTH = 200  # chars; below this we treat extraction as failed


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_paper(path: str, runtime: Optional[Runtime] = None) -> str:
    """Load paper text from a file or directory of any supported format.

    Args:
        path:    Absolute or ~-expandable path. May be a file or directory.
        runtime: Required for .pdf and .docx inputs (they call agentic stages).
                 May be None for plaintext / directory-of-tex inputs.

    Returns:
        The paper's text content as a single string. For multi-file directories
        (e.g. paper/ with N .tex files), files are concatenated in sorted order
        with `% === fname ===` separators (LaTeX) or `<!-- === fname === -->`
        (markdown) so downstream stages can attribute snippets back to files.

    Raises:
        FileNotFoundError: path does not exist.
        ValueError:        unsupported extension or empty directory.
        RuntimeError:      a converter (pdf/docx) was needed but failed.
    """
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if os.path.isfile(path):
        return _load_file(path, runtime)
    if os.path.isdir(path):
        return _load_dir(path, runtime)
    raise ValueError(f"Path is neither file nor directory: {path}")


# ---------------------------------------------------------------------------
# File dispatch
# ---------------------------------------------------------------------------

def _load_file(path: str, runtime: Optional[Runtime]) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext in PLAINTEXT_EXTS:
        return _read_text(path)

    if ext in PDF_EXTS:
        return _load_pdf(path, runtime)

    if ext in DOCX_EXTS:
        return _load_docx(path, runtime)

    if ext in HTML_EXTS:
        return _load_html(path)

    raise ValueError(
        f"Unsupported file extension: {ext} (path: {path}). "
        f"Supported: .pdf .docx .doc .md .markdown .tex .txt .rst .html .htm"
    )


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if len(text) < MIN_USABLE_LENGTH:
        raise RuntimeError(
            f"File {path} has only {len(text)} chars; likely empty or corrupt."
        )
    return text


def _load_pdf(path: str, runtime: Optional[Runtime]) -> str:
    cached = path[:-4] + ".md"
    if os.path.exists(cached) and os.path.getsize(cached) > MIN_USABLE_LENGTH:
        return _read_text(cached)

    # Run PyMuPDF directly. The previous implementation delegated to an
    # LLM-driven pdf_to_markdown stage, but that's brittle (codex sometimes
    # echoes the prompt instead of executing it) and has no upside —
    # font-size-based heading detection is purely deterministic.
    md = _convert_pdf_to_markdown(path)
    if len(md) < MIN_USABLE_LENGTH:
        # Fall back to the LLM-driven stage for unusual layouts (encrypted,
        # heavily scanned, etc.) when we got too little text.
        if runtime is None:
            raise RuntimeError(
                f"PyMuPDF extracted only {len(md)} chars from {path}; "
                f"pass a runtime to fall back to LLM extraction."
            )
        from research_harness.stages.review.pdf_to_markdown import pdf_to_markdown
        pdf_to_markdown(pdf_path=path, runtime=runtime)
        if os.path.exists(cached):
            return _read_text(cached)
        sibling = _newest_sibling_md(path)
        if sibling is None:
            raise RuntimeError(
                f"PyMuPDF + pdf_to_markdown both failed for {path}."
            )
        return _read_text(sibling)

    with open(cached, "w", encoding="utf-8") as f:
        f.write(md)
    return md


def _convert_pdf_to_markdown(pdf_path: str) -> str:
    """Font-size-based heading extraction. Validated on real ACL papers."""
    import re
    from collections import Counter

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(
            "PyMuPDF not installed (pip install pymupdf)") from e

    doc = fitz.open(pdf_path)
    all_lines = []
    for page in doc:
        for blk in page.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for line in blk["lines"]:
                text = " ".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                max_size = max(s["size"] for s in line["spans"])
                all_lines.append((text, max_size))
    if not all_lines:
        return ""

    size_counter = Counter(round(l[1], 1) for l in all_lines)
    body_size = size_counter.most_common(1)[0][0]
    title_size = max(size_counter)

    HEADING_MIN_DELTA = 0.8
    heading_sizes = {
        sz for sz, cnt in size_counter.items()
        if sz >= body_size + HEADING_MIN_DELTA and sz < title_size and cnt >= 2
    }

    title_lines = [l[0] for l in all_lines if round(l[1], 1) == title_size]
    title = re.sub(r"\s+", " ", " ".join(title_lines)).strip()

    out = []
    if title:
        out.append(f"# {title}")
    buf: list[str] = []

    def flush() -> None:
        if buf:
            joined = " ".join(buf)
            joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)  # de-hyphenate
            joined = re.sub(r"\s+", " ", joined).strip()
            if joined:
                out.append(joined)
            buf.clear()

    for txt, sz in all_lines:
        sz_r = round(sz, 1)
        if sz_r == title_size:
            continue
        if sz_r in heading_sizes:
            flush()
            out.append(f"## {txt.strip()}")
            continue
        buf.append(txt.strip())
    flush()

    md = "\n\n".join(out)

    # Drop References / Bibliography section and everything after.
    m = re.search(
        r"(?im)^##\s+(?:\d+\s+)?(References?|Bibliography)\s*$", md)
    if m:
        md = md[:m.start()].rstrip() + "\n"

    return md


def _load_docx(path: str, runtime: Optional[Runtime]) -> str:
    base, ext = os.path.splitext(path)
    cached = base + ".md"
    if os.path.exists(cached) and os.path.getsize(cached) > MIN_USABLE_LENGTH:
        return _read_text(cached)

    if runtime is None:
        raise ValueError(
            f"DOCX input requires a runtime (to invoke docx_to_markdown). "
            f"Path: {path}"
        )

    from research_harness.stages.review.docx_to_markdown import docx_to_markdown
    docx_to_markdown(docx_path=path, runtime=runtime)

    if not os.path.exists(cached):
        sibling = _newest_sibling_md(path)
        if sibling is None:
            raise RuntimeError(
                f"docx_to_markdown did not produce {cached} or any .md sibling."
            )
        return _read_text(sibling)
    return _read_text(cached)


def _load_html(path: str) -> str:
    """Minimal HTML → text: strip tags, decode entities, collapse whitespace."""
    raw = _read_text(path)
    no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw,
                       flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", no_script)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if len(text) < MIN_USABLE_LENGTH:
        raise RuntimeError(f"HTML at {path} extracted only {len(text)} chars.")
    return text


def _newest_sibling_md(original_path: str) -> Optional[str]:
    """Find the newest .md file in the same directory as `original_path` whose
    name starts with the same stem (handles .v2/.v3 suffixes from converters)."""
    directory = os.path.dirname(original_path)
    stem = os.path.splitext(os.path.basename(original_path))[0]
    candidates = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.startswith(stem) and f.endswith(".md")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# Directory dispatch
# ---------------------------------------------------------------------------

def _load_dir(path: str, runtime: Optional[Runtime]) -> str:
    files = sorted(
        f for f in os.listdir(path)
        if not f.startswith(".") and os.path.isfile(os.path.join(path, f))
    )

    # Priority 1: .tex (preserves existing review_loop behavior; multi-file concat)
    tex_files = [f for f in files if f.endswith(".tex")]
    if tex_files:
        parts = []
        for fname in tex_files:
            with open(os.path.join(path, fname), encoding="utf-8",
                      errors="replace") as f:
                parts.append(f"% === {fname} ===\n{f.read()}")
        return "\n\n".join(parts)

    # Priority 2: .md / .markdown (concat with HTML-comment separator)
    md_files = [f for f in files if f.endswith((".md", ".markdown"))]
    if md_files:
        parts = []
        for fname in md_files:
            with open(os.path.join(path, fname), encoding="utf-8",
                      errors="replace") as f:
                parts.append(f"<!-- === {fname} === -->\n{f.read()}")
        return "\n\n".join(parts)

    # Priority 3: a single PDF in the directory
    pdfs = [f for f in files if f.endswith(".pdf")]
    if len(pdfs) == 1:
        return _load_file(os.path.join(path, pdfs[0]), runtime)
    if len(pdfs) > 1:
        # Pick the largest PDF (heuristic: the actual paper, not supplements)
        pdfs_full = [(f, os.path.getsize(os.path.join(path, f))) for f in pdfs]
        pdfs_full.sort(key=lambda x: x[1], reverse=True)
        return _load_file(os.path.join(path, pdfs_full[0][0]), runtime)

    # Priority 4: single .docx / .doc
    docxs = [f for f in files if f.endswith((".docx", ".doc"))]
    if docxs:
        # If multiple, pick the largest
        docxs_full = [(f, os.path.getsize(os.path.join(path, f))) for f in docxs]
        docxs_full.sort(key=lambda x: x[1], reverse=True)
        return _load_file(os.path.join(path, docxs_full[0][0]), runtime)

    # Priority 5: single .txt / .rst
    txts = [f for f in files if f.endswith((".txt", ".rst"))]
    if len(txts) == 1:
        return _load_file(os.path.join(path, txts[0]), runtime)

    raise ValueError(
        f"No paper files found in {path}. "
        f"Looked for: .tex .md .markdown .pdf .docx .doc .txt .rst"
    )
