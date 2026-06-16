"""Single-paper structured digest leaf.

`digest_paper` reads ONE paper from any input form (arXiv id, URL, local
PDF path, paper title, or a paper dict from state) and writes a
structured markdown digest to `<output_dir>/digests/<safe_id>.md`.

Usable in two ways:
  1. Picker action `digest_paper` — wired through `_actions._dispatch`,
     called from inside the literature loop on a paper already in state.
  2. Standalone — import and call directly with a `target` string and a
     runtime; useful for ad-hoc paper notes outside any literature run.
"""
from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function()
def digest_paper(target: str, paper_hint_json: str,
                 output_path: str, papers_dir: str,
                 runtime: Runtime) -> str:
    """Produce a structured single-paper digest.

    Inputs:
      - `target`: free-form pointer to the paper. May be any of:
          * arXiv id (`arXiv:2409.12917`, `2409.12917`, `arxiv.org/abs/...`)
          * paper title (exact or near-exact)
          * absolute local PDF path
          * URL to PDF / abstract page
          * a search query that uniquely identifies the paper
      - `paper_hint_json`: optional JSON dict with already-known fields
        (`id`, `title`, `authors`, `year`, `venue`, `abstract`,
        `pdf_path`, `context_excerpt`). Use this when called from the
        literature loop with a paper already in state. May be `"{}"` for
        ad-hoc standalone use.
      - `output_path`: absolute path to write the digest markdown to.
        Its parent directory is the paper's dedicated workspace
        (`<output_dir>/digests/<safe_id>/`). Any auxiliary artifacts
        you produce for this paper — figures pulled from the PDF,
        scratch notes, follow-up code, etc. — should live in that
        same folder. Use clear filenames (`figures/fig1.png`,
        `notes.md`, `followup_code.py`). Do NOT scatter them
        elsewhere.
      - `papers_dir`: shared PDF cache directory for the literature
        run. Save any PDF you have to fetch as
        `<papers_dir>/<safe_id>.pdf` so other steps (search,
        annotate) can reuse it. Do NOT duplicate the PDF inside the
        per-paper digest folder.

    Source resolution (do as much as needed, in order):
      1. If `paper_hint_json` has a usable `pdf_path`, read it directly
         (do not redownload).
      2. Else if `target` looks like a local path, Read it.
      3. Else if `target` looks like an arXiv id or arxiv URL, check
         whether `<papers_dir>/<safe_id>.pdf` already exists; if not,
         fetch from `https://arxiv.org/pdf/<id>` (Bash + curl is fine)
         and save it there. Then Read.
      4. Else if `target` looks like another URL, fetch it (WebFetch /
         curl) and treat as either PDF or HTML accordingly. PDFs go
         under `papers_dir`, never in the digests folder.
      5. Else use search tools (the runtime should have arxiv search /
         WebSearch / Bash) to find the paper, then go back to step 3.

    If after all of the above you still cannot get full text, you MAY
    fall back to abstract-only mode — but mark the digest header with
    `tier: abstract_only` and keep sections that depend on the method /
    experiments to a single sentence noting the limitation.

    ## Output structure

    Write a single markdown file to `output_path` with EXACTLY these
    sections, in this order, using these heading levels:

    ```
    # <title>

    **id**: <id (arXiv:... if available)>
    **authors**: <comma-separated>
    **venue / year**: <venue, year>
    **link**: <url to abstract page or pdf>
    **tier**: <pdf | html | abstract_only>
    **digested_at**: <YYYY-MM-DD>

    ## TL;DR
    2-3 sentences. What problem, what method, what result.

    ## 1. Problem & motivation
    What concrete problem does this paper target? Why does it matter?
    What was the prior state of the field that motivated it? 1-2
    paragraphs.

    ## 2. Method
    The technical core. Walk the reader through the algorithm /
    architecture. Include equations inline as `$...$` where they
    illuminate the method (do NOT invent equations). Mention the key
    design choices and what makes this method different from prior
    work. 2-4 paragraphs.

    ## 3. Experiments
    - **Setup**: datasets, models, baselines, evaluation protocol.
    - **Headline results**: the most important numbers, with the metric
      name and the comparison baseline. ONLY numbers that appear in the
      paper — do NOT round or paraphrase numerically.
    - **Ablations / analysis**: what the paper learned from breaking
      its own method apart. Bullet a few key takeaways.

    ## 4. Contributions
    Bulleted list of the paper's claimed contributions, in the paper's
    own framing. 3-6 bullets.

    ## 5. Limitations & open questions
    What the paper acknowledges as limitations, plus what a careful
    reader would flag as unaddressed (clearly mark which is which).

    ## 6. Connections
    Where this paper sits relative to neighboring work. Cite related
    papers by id where you know them; do NOT invent ids. If a hint
    paper dict mentions placements / topic_path, reference those.

    ## 7. Notes
    Anything worth remembering that did not fit above: surprising
    details from the appendix, undocumented assumptions, follow-ups
    you would run, reproducibility notes (code release, compute
    requirements). Be concrete.
    ```

    Writing rules:
    - Use the Write tool to save to `output_path` exactly. Do not write
      anywhere else. Create the parent directory if missing (Bash mkdir
      -p is fine).
    - Preserve the user's language preference: if `paper_hint_json`
      contains non-English content, match its language; otherwise use
      English.
    - No fabrication. If a section has no source material, write one
      sentence stating that.
    - Be concise. Target 1500-3500 words for a PDF-tier digest;
      400-800 words for abstract-only.

    ## Return

    Return ONE short JSON object — and nothing else — after writing:

    ```json
    {
      "artifact": "<output_path>",
      "id": "<resolved id, e.g. arXiv:2409.12917>",
      "title": "<resolved title>",
      "tier": "pdf | html | abstract_only",
      "words": <int>,
      "done": true
    }
    ```
    """
    return runtime.exec(content=[{"type": "text", "text": (
        f"Target: {target}\n\n"
        f"Paper hint (JSON, may be empty):\n{paper_hint_json}\n\n"
        f"Output path (digest md): {output_path}\n"
        f"PDF cache dir (reuse, do NOT create a new one): "
        f"{papers_dir}\n\n"
        f"Resolve the paper, write the digest to the output path "
        f"following the structure in your instructions, then return "
        f"the JSON summary."
    )}], web_search=True)
