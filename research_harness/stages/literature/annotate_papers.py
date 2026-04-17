from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def annotate_papers(papers_json: str, framework_json: str,
                    runtime: Runtime) -> str:
    """Place each paper in the framework and annotate its contribution.

    You are deciding: where does this paper belong in the topic tree, and
    what did it concretely contribute there?

    Source material per paper (use the most detailed available):
    1. `pdf_path` (if non-null) — read the PDF for method, experiments,
       limitations. This is the richest source — prioritize it.
    2. `context_excerpt` (if non-null) — intro + related work. Good for
       positioning and method framing.
    3. `abstract` — always present. Use as base + fill gaps with 1 or 2.

    Workflow for each paper:
    1. Read available sources in the order above. If `pdf_path` is set, use
       the Read tool (it handles PDF extraction) to open it and scan
       method + experiment sections.
    2. Look at the framework. Pick the BEST-matching leaf topic_path.
       A paper may belong to multiple paths if it genuinely straddles
       sub-fields (surveys, hybrid methods).
       If NO existing leaf fits, mark as orphan with an `orphan_suggested_topic`.
    3. Write a 4–6 sentence `contribution_summary` per (paper, topic_path):
       - Problem framing in THIS topic (what gap does it target?)
       - Method / key insight (concrete — name the mechanism)
       - Empirical evidence (dataset, benchmark, headline numbers, baselines)
       - Limitations / open issues the paper itself notes or you observe
       - If you only had the abstract, state so — do not invent numbers.

    4. Return ONE JSON object, nothing else:
    ```json
    {
      "annotations": [
        {
          "paper_id": "arXiv:...",
          "placements": [
            {"topic_path": "a/b/c", "contribution_summary": "..."}
          ],
          "is_orphan": false,
          "orphan_suggested_topic": null,
          "source_used": "pdf" | "context_excerpt" | "abstract"
        },
        {
          "paper_id": "arXiv:...",
          "placements": [],
          "is_orphan": true,
          "orphan_suggested_topic": "new topic name + one-sentence scope",
          "source_used": "abstract"
        }
      ],
      "notes": "free-form decisions and confusion"
    }
    ```

    Rules:
    - Output ONLY the JSON.
    - Every input paper must appear by paper_id.
    - Orphans: `placements: []` and non-null `orphan_suggested_topic`.
    - Non-orphans: `placements` with >=1 entry.
    - Never invent a `topic_path` that does not exist in the framework (use
      orphan flow instead).
    - Never fabricate numbers or methods — if the source was thin, say so.
    - The orchestrator persists state — do NOT write extra files.

    Args:
        papers_json:     JSON array of papers to annotate. Each record has
                         id/title/abstract plus optional pdf_path and
                         context_excerpt (non-null when available).
        framework_json:  JSON tree of the current topic framework.
        runtime:         LLM runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Framework:\n{framework_json}\n\n"
            f"Papers to annotate:\n{papers_json}"
        )},
    ])
