from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def pdf_to_markdown(pdf_path: str, runtime: Runtime) -> str:
    """Convert a paper PDF to clean Markdown for downstream review.

    You have shell access. Use the **font-size based** algorithm below
    (validated on real ACL papers — text-only heuristics produce too many
    false-positive headings):

    ```python
    import fitz, re
    from collections import Counter

    doc = fitz.open(pdf_path)

    # 1. Extract per-line text + max font size + bold flag
    all_lines = []
    for page in doc:
        for blk in page.get_text("dict")["blocks"]:
            if blk.get("type") != 0: continue
            for line in blk["lines"]:
                text = " ".join(s["text"] for s in line["spans"]).strip()
                if not text: continue
                max_size = max(s["size"] for s in line["spans"])
                is_bold = any(s.get("flags", 0) & 16 for s in line["spans"])
                all_lines.append((text, max_size, is_bold))

    # 2. Identify body vs title vs heading by font histogram
    size_counter = Counter(round(l[1], 1) for l in all_lines)
    body_size  = size_counter.most_common(1)[0][0]    # most common = body
    title_size = max(size_counter)                     # largest = title

    # CRITICAL: heading must be at least 0.8pt larger than body, otherwise
    # variants of the body font (captions, etc.) get misclassified.
    HEADING_MIN_DELTA = 0.8
    heading_sizes = {
        sz for sz, cnt in size_counter.items()
        if sz >= body_size + HEADING_MIN_DELTA and sz < title_size and cnt >= 2
    }

    # 3. Title = concatenate all lines at title_size
    title_lines = [l[0] for l in all_lines if round(l[1], 1) == title_size]
    title = re.sub(r'\\s+', ' ', " ".join(title_lines)).strip()

    # 4. Walk lines, emit markdown
    out_paragraphs, buf = [], []
    def flush():
        if buf:
            joined = " ".join(buf)
            joined = re.sub(r'(\\w)-\\s+(\\w)', r'\\1\\2', joined)  # de-hyphenate
            joined = re.sub(r'\\s+', ' ', joined).strip()
            if joined: out_paragraphs.append(joined)
            buf.clear()

    for txt, sz, bold in all_lines:
        sz_r = round(sz, 1)
        if sz_r == title_size:
            continue  # skip; will be prepended as # Title
        if sz_r in heading_sizes:
            flush()
            out_paragraphs.append(f"## {txt.strip()}")
            continue
        buf.append(txt.strip())
    flush()

    md = "\\n\\n".join(out_paragraphs)
    ```

    Then run these post-processing passes (in order):

    1. Drop References / Bibliography section and everything after:
       ```python
       m = re.search(r'(?im)^##\\s+(?:\\d+\\s+)?(References?|Bibliography)\\s*$', md)
       if m: md = md[:m.start()].rstrip() + "\\n"
       ```

    2. Drop standalone page numbers:
       ```python
       md = re.sub(r'(?m)^\\s*\\d{1,3}\\s*$\\n?', '', md)
       ```

    3. Merge split numbered headings ("## 1\\n\\n## Introduction" → "## 1 Introduction"):
       ```python
       md = re.sub(
           r'^(##\\s+\\d+(?:\\.\\d+){0,2})\\n\\n(##\\s+[A-Z][\\w \\-:&,/]{1,60})$',
           lambda m: f"{m.group(1)} {m.group(2)[3:]}",
           md, flags=re.MULTILINE,
       )
       ```

    4. Collapse runs of 3+ blank lines to 2:
       ```python
       md = re.sub(r'\\n{3,}', '\\n\\n', md)
       ```

    5. Prepend the H1 title:
       ```python
       md = f"# {title}\\n\\n" + md if title else "# UNKNOWN_TITLE\\n\\n" + md
       ```

    Fallbacks (in order if PyMuPDF is unavailable):
      a. `pdftotext -layout "$PDF" -` — text only, no font info, falls back
         to the older text-heuristic heading detection (less accurate).
      b. `mutool draw -F txt` — third option.
      Both fallbacks lose the font-based heading detection; expect more noise.

    Sanity checks before returning:
    - Output length must be >= 1500 characters; if smaller, the PDF likely
      failed to extract — try the next extractor.
    - At least one heading must be detected. If zero, font-size detection
      probably failed (e.g. uniform-font PDF); the fallback prepends
      `# UNKNOWN_TITLE` so downstream stages can detect lossy extraction.

    Output file:
    - Save to `<pdf_path with .pdf replaced by .md>`. If the same path exists,
      append `.v2`, `.v3`, ... so prior conversions are not overwritten.

    Return value (string):
    `Saved to <md_path>. Extracted <N> chars from <pages> pages, <H> headings.`


    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    The filename is dictated by the rules above (mirror the pdf_path with .md).
    After saving, return the one-line summary described in "Return value".
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"PDF path: {pdf_path}"},
    ])
