from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"siblings": -1})
def synthesize_literature(direction: str, framework_json: str,
                          papers_json: str, surveys_json: str,
                          output_dir: str,
                          runtime: Runtime) -> str:
    """Produce the final, publication-ready literature synthesis.

    Produce six coherent artifacts that, taken together, let a reader (or
    downstream `run_idea` stage) understand the field, see where it's at,
    and pick promising directions.

    Inputs:
    - `direction`: overall research direction (tree root).
    - `framework_json`: the stabilized topic tree.
    - `papers_json`: all annotated papers with per-topic contribution_summary.
    - `surveys_json`: all surveys with TOC + key claims.
    - `output_dir`: directory to save artifacts into.

    MODE DETECTION — before writing, CHECK IF `<output_dir>/synthesis/`
    ALREADY HAS FILES:
    - If NO — write everything from scratch (instructions below).
    - If YES — this is a REFINEMENT pass. Do NOT overwrite blindly:
        a. Read each existing file with the Read tool first.
        b. Compare the existing content with the current state (framework +
           papers + surveys provided here). Identify what changed:
             * New topics added → extend framework.md + create new topic_*.md
             * Topics renamed/merged/split/dropped → rename/merge/rewrite the
               corresponding topic_*.md files and update framework.md
             * New papers in a topic → append new paragraphs to topic_*.md
               and bibliography.md
             * Papers upgraded tier (abstract_only → pdf) → rewrite that
               paper's paragraph with the richer PDF-derived detail
             * New gaps surfaced / gaps resolved → update gaps.md and
               ideas.md accordingly
        c. Preserve sections that are STILL CORRECT. Do not rewrite text just
           for stylistic reasons — only when the underlying evidence changed.
        d. Keep the narrative flow of synthesis.md; weave new evidence in,
           don't restart the story.
        e. At the end, write a short `CHANGELOG.md` in `<output_dir>/synthesis/`
           summarizing what this refinement pass changed. Append to it if it
           already exists.

    Workflow — write (or refine) these files under `<output_dir>/synthesis/`:

    1. `framework.md`
       Tree rendered as nested markdown headers (H1=direction, H2=branch, ...).
       Each node: description + source tag + open_questions + "N papers"
       count + 2–3 representative papers (title + 1-line takeaway).

    2. `topic_<slug>.md` (one per leaf topic)
       For each leaf with >=1 paper:
       - Overview of the sub-problem (2–4 sentences)
       - Papers ordered by method lineage (foundations → refinements → recent),
         each as a paragraph with: short citation, problem framing, method,
         evidence (datasets/numbers), limitation. Use `contribution_summary`
         as the backbone. If a paper has a non-null `pdf_path`, use the Read
         tool to open the PDF and enrich the paragraph with method details
         (architectures, key equations, experiment setup) that the summary
         alone wouldn't capture.
       - Trends paragraph: what has shifted over time in this sub-problem.
       - Open questions pulled from the framework node plus anything papers
         consistently identify as unresolved.

    3. `synthesis.md`
       Cross-topic narrative:
       - Opening: scope + why it matters.
       - How the sub-problems connect (shared primitives, conflicting goals,
         pipeline stages, etc.).
       - Consensus vs contested claims (what most papers agree on vs where
         surveys or recent work disagree).
       - Historical arc: where was the field 5 years ago, what changed.

    4. `gaps.md`
       Concrete, actionable gaps — not "more research needed".
       Organize under headings per framework branch.
       Each gap:
       - What's missing (1 sentence, specific)
       - Why existing work doesn't address it (evidence from papers)
       - What would plausibly fix it (method sketch — not full design)

    5. `ideas.md`
       Candidate research directions derived from gaps.
       Each idea:
       - Title
       - One-paragraph pitch (problem → approach → expected contribution)
       - Feasibility (easy / medium / hard + why)
       - Novelty (incremental / substantial / breakthrough + why, citing
         closest prior work by id)
       - Rough experiment sketch (2–3 bullets)

    6. `bibliography.md`
       All papers and surveys, unified format: `[id] Authors (year). Title.
       Venue.` Sorted by year desc, then author.

    After writing all six files, return ONE short JSON summary:
    ```json
    {
      "artifacts": {
        "framework_md": "<path>",
        "topic_files": ["<path>", "..."],
        "synthesis_md": "<path>",
        "gaps_md": "<path>",
        "ideas_md": "<path>",
        "bibliography_md": "<path>"
      },
      "stats": {
        "topics": 0, "leaves_with_papers": 0, "papers": 0,
        "surveys": 0, "ideas": 0, "gaps": 0
      },
      "done": true
    }
    ```

    Rules:
    - Output ONLY the final JSON (after files are written).
    - Do NOT fabricate papers, numbers, or citations.
    - If a paper has only a short abstract, write what you can and say so —
      do not invent results.
    - LaTeX is not required here — this is human-readable markdown. Leave
      LaTeX formatting for the writing stage.

    Args:
        direction:       Research direction.
        framework_json:  Stabilized topic tree.
        papers_json:     All annotated papers.
        surveys_json:    All surveys.
        output_dir:      Base directory (the function writes under `<output_dir>/synthesis/`).
        runtime:         LLM runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Direction: {direction}\n"
            f"Output directory: {output_dir}\n\n"
            f"Framework:\n{framework_json}\n\n"
            f"Papers:\n{papers_json}\n\n"
            f"Surveys:\n{surveys_json}"
        )},
    ])
