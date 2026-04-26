from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def search_papers_for_topic(topic_path: str, topic_description: str,
                            k: int, existing_ids: str, papers_dir: str,
                            top_k_pdf: int,
                            runtime: Runtime) -> str:
    """Find papers for a specific topic, downloading PDFs for the most-cited
    and extracting related-work excerpts for the rest.

    Use real searches — do NOT fabricate.

    Workflow:
    1. Understand the target:
       - `topic_path`: e.g. "retrieval/dense/multi-vector"
       - `topic_description`: one-sentence scope
    2. Search 2–3 query variants (topic name, method names, benchmarks).
       Sources: Semantic Scholar (for citation count + venue),
       arXiv (for preprints + latest), web fallback.
       Skip any paper id in `existing_ids`.
       Target up to `k` NEW papers. Prefer a mix of high-cited foundations
       and recent (<=3 yrs) work.

    3. Rank found papers by citation count (desc). Split them:

       TIER 1 — top `top_k_pdf` by citation:  DOWNLOAD PDF.
         Download to `papers_dir/<arxiv_id>.pdf` (or slugified DOI).
         Verify PDF (> 20 KB, starts with "%PDF"). Retry once on HTTP 429
         after 5 s. If still broken, record `pdf_path: null` and note it.
         Rate limit: 1 s between downloads.

       TIER 2 — the rest:  TRY HTML FIRST.
         Open `arxiv.org/html/<id>/v<N>` (or the publisher HTML page).
         If it loads, extract `context_excerpt` = concatenation of:
            (a) the last paragraph of the Introduction (positioning), and
            (b) the full Related Work / Background section (500–2000 words
                total — truncate gracefully if longer).
         Set `pdf_path: null`.
         If HTML is UNAVAILABLE (old paper, no arxiv html, 404, paywalled
         without excerpt), FALL BACK to downloading the PDF as in Tier 1.

       In both tiers, ALWAYS record:
         - full `abstract`
         - `citation_count` if known (null if not)

    4. For each paper, return:
       - `id` (arXiv id / DOI / S2 id)
       - `title`, `authors`, `year`, `venue`
       - `abstract` (FULL, do not paraphrase)
       - `citation_count` (int or null)
       - `tentative_topic_path`: the given `topic_path`
       - `pdf_path`: absolute path, or null
       - `context_excerpt`: string (Tier 2 html excerpt), or null
       - `tier`: "pdf" if pdf_path is set, "html" if only context_excerpt,
                  "abstract_only" if both null (explain in notes).

    5. Return ONE JSON object, nothing else:
    ```json
    {
      "topic_path": "...",
      "papers": [
        { "id": "arXiv:...", "title": "...", "authors": [...], "year": 2023,
          "venue": "NeurIPS", "abstract": "...", "citation_count": 120,
          "tentative_topic_path": "...",
          "pdf_path": "/abs/path/papers/2310.xxxxx.pdf",
          "context_excerpt": null,
          "tier": "pdf"
        },
        { "id": "...", "pdf_path": null,
          "context_excerpt": "...intro + related work...",
          "tier": "html", ... }
      ],
      "notes": "sources used, HTML misses, download failures"
    }
    ```

    Rules:
    - Output ONLY the JSON.
    - No fabrication — paper or file path.
    - Never invent context_excerpt — if you didn't actually fetch it, set null.
    - Rate limit: 1 s between any arxiv/s2 requests.

    Args:
        topic_path:        "/"-joined path into the framework.
        topic_description: Scope of the target topic.
        k:                 Max new papers this round.
        existing_ids:      Newline-joined paper ids already in state.
        papers_dir:        Absolute dir to save PDFs.
        top_k_pdf:         How many top-cited papers to download as PDF
                           (typical: 3).
        runtime:           LLM runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Topic path: {topic_path}\n"
            f"Topic description: {topic_description}\n"
            f"Max new papers: {k}\n"
            f"Tier-1 PDF downloads (top by citation): {top_k_pdf}\n"
            f"PDF destination: {papers_dir}\n\n"
            f"Papers already in state (skip):\n{existing_ids or '(none)'}"
        )},
    ])
