from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"siblings": -1})
def synthesize_literature(direction: str, framework_json: str,
                          papers_json: str, surveys_json: str,
                          output_dir: str,
                          runtime: Runtime) -> str:
    """Produce ONE strict survey-paper-style markdown file.

    Output: a single file at `<output_dir>/synthesis/review.md` with the
    structure of an academic survey paper. The orchestrator appends the
    programmatic bibliography to the same file after you finish — leave
    a placeholder section for it (see workflow step 9).

    Inputs:
    - `direction`: overall research direction (root of the tree).
    - `framework_json`: the stabilized topic tree.
    - `papers_json`: all annotated papers with per-topic contribution_summary.
    - `surveys_json`: all surveys with TOC + key claims.
    - `output_dir`: base directory; you write to `<output_dir>/synthesis/review.md`.

    ## Mode

    If `<output_dir>/synthesis/review.md` already exists, this is a
    refinement pass:
    - Read the existing file with the Read tool first.
    - Overwrite it in place with an updated version that integrates new
      evidence (added papers, refined topics, upgraded tiers). Preserve
      sections still supported by the evidence; rewrite only what
      changed. Keep the narrative flow.

    Otherwise, write from scratch.

    ## Required structure for review.md

    Output ONE markdown file with these top-level sections, in this
    exact order, using `#` and `##` headings:

    ```
    # <direction>: A Literature Review

    ## Abstract
    150-250 words. What the field is, what problem it addresses, the
    scope of this review (what is and is not covered), the main
    organizing axes, the key findings or trends, and the gaps highlighted.

    ## 1. Introduction
    - Problem framing: 2-3 paragraphs. Define the field, state why it
      matters, and surface the central tension or open question that
      structures the review.
    - Scope: bounded statement of what counts as in-scope (which sub-
      problems, time range, methodologies). 1 paragraph.
    - Roadmap: 1 paragraph mapping each later section to a part of the
      story.

    ## 2. Taxonomy
    The stabilized topic tree as nested subsections (`### 2.1`, `#### 2.1.1`,
    etc), one node per heading. For each node: a 1-2 sentence
    description, the source tag (survey / llm-induced / paper-induced),
    open questions if any, and the count of papers placed in that node
    (or in any descendant if non-leaf).

    Do not list every paper here — that goes in section 3. Keep this
    section a structural map.

    ## 3. Per-topic detailed review
    One subsection per leaf in the taxonomy that has >=1 placed paper.
    Use 2.X.Y numbering aligned with section 2 where natural; or just
    sequential 3.1, 3.2, ... if alignment is awkward. For each subsection:

    - **Overview** (2-4 sentences): the sub-problem and what makes it
      hard.
    - **Methods** (paragraph-per-paper, ordered by method lineage —
      foundations first, then refinements, then recent work):
      Each paper paragraph has, in order:
        1. Citation as `[<id>]` where `<id>` is the paper's id field
           verbatim (e.g. `[arXiv:2409.12917]`).
        2. Problem framing: what the paper specifically targets.
        3. Method: the technical core, in 2-4 sentences. If the paper's
           `pdf_path` is non-null, use the Read tool on the PDF to enrich
           the method description with architecture / equations / setup
           details that the summary alone misses.
        4. Evidence: datasets, metrics, headline numbers (only numbers
           that appear in the paper or in `contribution_summary`; do NOT
           invent).
        5. Limitation: what this paper acknowledges or what later work
           identified as a weakness. One sentence.
    - **Trends** (1 paragraph): what has shifted over time within this
      sub-problem.
    - **Open questions** (bullet list): pulled from the framework node
      plus anything multiple papers identify as unresolved.

    Leaves with 0 placed papers should NOT appear here. The orchestrator
    has already pruned empty leaves with no survey support; survey-only
    leaves (no primary papers in state) may still be referenced briefly
    in section 4 instead.

    ## 4. Cross-cutting synthesis
    - **How the sub-problems connect**: 2-3 paragraphs on shared
      primitives, conflicting goals, pipeline stages — what makes the
      taxonomy a coherent field rather than a list of unrelated topics.
    - **Consensus vs contested claims**: two short subsections.
        - Consensus: claims most surveys / multiple primary papers
          agree on. Cite at least 2 sources per claim.
        - Contested or open: claims where surveys disagree or where
          recent work challenges older consensus. Cite the disagreeing
          sources.
    - **Historical arc**: 1-2 paragraphs. Where was the field 3-5 years
      ago, what changed, what is the current frontier.

    ## 5. Research gaps
    Concrete, actionable gaps. Not "more research needed". Organize as
    `### 5.1`, `### 5.2`, ... numbered. Each gap has the structure:
    - **Gap <n>.<m> — <short title>**
    - **What's missing** (1 sentence, specific).
    - **Why existing work doesn't address it** (cite specific papers
      and what they do / don't do — not just generic gestures at the
      literature).
    - **What would plausibly fix it** (method sketch in 2-4 sentences;
      not a full design).

    Group gaps by framework branch where natural — gaps under section
    5.1 aligned with branch 1 of the taxonomy, etc.

    ## 6. References
    Leave EXACTLY this single line in this section:

        <!-- bibliography appended programmatically -->

    Do not write any references yourself. The orchestrator appends the
    bibliography to this section after you finish, derived from
    `state["papers"]` and `state["surveys"]` directly. If you write
    references here, they will be overwritten.
    ```

    ## Citation style

    Inline citations use the paper's id verbatim, in square brackets:
    `[arXiv:2409.12917]`, `[arXiv:2308.03188]`, etc. The orchestrator
    audits these against state — IDs not in state are flagged in
    `_citation_audit.md` next to the review file.

    ## Writing rules

    - Output ONLY the final JSON summary (after writing the file).
    - Do not fabricate papers, numbers, citations, or method details.
      If `contribution_summary` is thin and the paper has no
      `pdf_path`, write what you can and explicitly say "the abstract
      reports X but the method details are not available in the
      retrieved metadata".
    - When citing surveys, cite their id like any other paper.
    - Use plain markdown. No LaTeX, no HTML. Inline math like `$x$` is
      fine for variable names but no equations.
    - Length: aim for 8000-15000 words total in review.md. The
      Per-topic detailed review (section 3) is normally the longest;
      sections 4 and 5 are 1500-2500 words each.
    - Use the Write tool to save to `<output_dir>/synthesis/review.md`.
    - Do NOT write any other markdown files. The previous version
      produced framework.md / topic_*.md / synthesis.md / gaps.md as
      separate files; this is now consolidated into review.md.

    ## Return

    After writing the file, return ONE short JSON object:
    ```json
    {
      "artifact": "<output_dir>/synthesis/review.md",
      "stats": {
        "topics": 0, "leaves_with_papers": 0, "papers": 0,
        "surveys": 0, "gaps": 0, "words": 0
      },
      "done": true
    }
    ```

    Args:
        direction:       Research direction.
        framework_json:  Stabilized topic tree.
        papers_json:     All annotated papers.
        surveys_json:    All surveys.
        output_dir:      Base directory; output written to
                         `<output_dir>/synthesis/review.md`.
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
