# literature stage

Iteratively build a literature review from a free-text research
direction. The output is a directory of markdown artifacts (framework
tree, per-topic folders, per-paper cards, audit log, final synthesis
review) plus a `state.json` that lets the run resume.

Entry point: `run_literature(direction, output_dir, runtime, ...)`.
Same `output_dir` → resume; new path → fresh run.

---

## What this stage does

Given a research direction, the stage:

1. Finds a few survey / review papers on the topic.
2. Extracts a topic-tree taxonomy from those surveys (under design
   axioms — see `extract_framework.py`).
3. Searches for primary papers under each leaf of the tree.
4. Annotates each paper: places it in the tree and writes a
   contribution summary grounded in the paper's text (PDF when
   available, abstract otherwise).
5. Periodically restructures the tree (merge redundant siblings, drop
   empty leaves, split overgrown ones) as evidence accumulates.
6. Synthesizes a single review.md combining everything: introduction,
   taxonomy, per-topic detailed review, cross-cutting synthesis,
   research gaps, and a programmatic bibliography.

The loop converges when the framework is stable, every leaf has
enough coverage, and no orphans remain. The picker LLM may also call
`done` early to stop.

---

## The two-level loop

```
for outer in 1..max_outer:
  for inner in 1..max_inner:
    LLM picks ONE action ∈ {seed_surveys, extract_framework,
                            search_papers, annotate_papers,
                            evolve_framework, done}
    leaf runs → result merged into state
    if action == "done" (scope=cycle): break inner
    if action == "done" (scope=all):   break inner AND outer
  end-of-cycle compensation: evolve_framework (unconditional)
end-of-run finalization: synthesize_literature (unconditional)
```

The picker LLM (`_lit_decide`) sees a compact state summary +
truncated framework preview at every tick and picks the next action.
This is the single decision point — no multi-step plans, no agent
chain.

---

## Action reference

| Action | Purpose |
|---|---|
| `seed_surveys` | Fetch survey/review papers on the direction. Adds to `state.surveys`. |
| `extract_framework` | Build / refresh the taxonomy tree from surveys. Subject to design axioms (orthogonal axes, no sibling overlap, no empty/starved nodes). |
| `search_papers` | Find primary papers under one specific leaf path. Adds to `state.papers`. |
| `annotate_papers` | For each unannotated paper: place it in the tree and write a 4-6 sentence paper-grounded contribution summary. **Batched** (6 papers/call, 18 papers/tick) to keep stdout under the asyncio readline cap. |
| `evolve_framework` | Refactor the tree based on evidence: `merge` overlapping siblings, `split` heavy leaves, `rename`, `drop` starved leaves, with `paper_relocations`. |
| `done` | Stop. `scope="cycle"` exits the inner loop; `scope="all"` ends the run. |

End-of-cycle compensation runs `evolve_framework` once unconditionally
so structural cleanup happens at least once per outer cycle (the
inner loop tends to favor search/annotate).

End-of-run finalization runs `synthesize_literature` once. It writes
`synthesis/review.md`, then a programmatic bibliography is spliced in
(walking `state.papers` + `state.surveys` directly, NOT the LLM —
this catches hallucinated citations). A citation audit then flags any
arXiv IDs in the prose that are not in state.

---

## State schema

`state.json` (in `output_dir`):

```python
{
  "direction":       str,           # the user's research direction
  "surveys":         [SurveyDict],  # survey papers (toc + key claims)
  "papers":          [PaperDict],   # primary papers + placements
  "framework":       FrameworkTree, # current taxonomy
  "audit":           [AuditEntry],  # one entry per action
  "iter":            int,           # global iteration counter
  "outer":           int,           # outer-loop counter
  "no_delta_streak": int,           # consecutive evolves with no
                                    # non-trivial change → drives
                                    # convergence
}
```

`PaperDict` has: id, title, authors, year, venue, abstract,
citation_count, pdf_path / context_excerpt, tier (`pdf`/`html`/
`abstract_only`), placements (list of `{topic_path,
contribution_summary}`), annotated, is_orphan, source_used.

`FrameworkTree` is recursive: `{name, description, source, children,
open_questions}`. `source` is `survey` (from a survey TOC),
`llm-induced` (added by the LLM from its own knowledge), or
`paper-induced` (forced by a placed paper).

---

## Output layout

```
<output_dir>/
├── state.json              # canonical machine state
├── README.md               # snapshot (regenerated each tick)
├── audit.md                # chronological action log
├── surveys/<id>.md         # one card per survey (incremental)
├── topics/<path>/
│   ├── _overview.md        # topic description + paper list
│   └── <paper-id>.md       # per-paper card with contribution
├── orphans/<id>.md         # papers not yet placed
├── papers/<id>.pdf         # downloaded PDFs (when fetched)
└── synthesis/
    ├── review.md           # final review (written by synthesize)
    └── _citation_audit.md  # only if unknown arXiv IDs detected
```

`topics/` and `orphans/` are wiped and regenerated each tick so
`evolve_framework` ops (merge / split / rename / drop) are reflected
immediately. `surveys/` and `papers/` (PDFs) are append-only.
`synthesis/` is only written at end of run.

---

## Anti-hallucination measures

1. **Programmatic bibliography.** The references section in
   `review.md` is generated from `state.papers` + `state.surveys`
   metadata directly — the LLM does not write bib entries. Catches
   the bug class where the model confidently invents arXiv IDs,
   years, or authors from half-remembered facts.

2. **Citation audit.** After synthesis, the prose (sections 1–5) is
   scanned for arXiv IDs not in state. Mismatches are written to
   `synthesis/_citation_audit.md` and printed to stderr — they are
   either hallucinations or references to important work the search
   step missed.

3. **Hard prune.** The deterministic `_prune_empty_leaves` walk drops
   any leaf with zero placed papers and no survey-TOC backing,
   regardless of what `evolve_framework` decided. The LLM tends to
   hedge against churn and leave stub leaves around.

4. **Taxonomy axioms.** `extract_framework` and `evolve_framework`
   prompts enforce: (a) orthogonal method-design axes vs cross-cutting
   concerns at separate levels, (b) same-level abstraction
   consistency, (c) no sibling overlap (a paper that lands under two
   siblings = merge signal), (d) no empty / starved (1–2 paper)
   nodes. Without these, surveys with messy TOCs propagate into
   messy trees.

5. **Paper-grounding in annotations.** `annotate_papers` is told to
   prefer `pdf_path` > `context_excerpt` > `abstract`. When only the
   abstract was used, the annotation declares it (`source_used:
   "abstract"`). Numbers and method names from the paper are required;
   inventing them is forbidden.

---

## Source layout (this package)

```
literature/
├── __init__.py            # orchestrator (run_literature) + re-exports
├── README.md              # this file
├── _state.py              # state schema, IO, slug, paper_id, framework
│                          # walks, count summaries
├── _artifacts.py          # md writers, bibliography, citation audit,
│                          # empty-leaf prune, dispatcher state summary
├── _actions.py            # catalog + decide LLM, per-action mergers,
│                          # dispatcher (incl. batched annotate)
├── seed_surveys.py        # leaf @agentic_function
├── extract_framework.py   # leaf @agentic_function (taxonomy axioms)
├── search_papers_for_topic.py  # leaf @agentic_function
├── annotate_papers.py     # leaf @agentic_function
├── evolve_framework.py    # leaf @agentic_function
├── synthesize_literature.py    # leaf @agentic_function
├── search/                # search backends (called by
│   ├── arxiv.py           # search_papers_for_topic)
│   └── semantic_scholar.py
└── tools/                 # standalone helpers, NOT in the loop
    ├── survey_topic.py    #   (kept for backward-compat with older
    ├── identify_gaps.py   #    workflows that called them directly)
    └── comprehensive_lit_review.py
```

The four underscore-prefixed modules (`_state`, `_artifacts`,
`_actions`, `__init__`) split what used to be a single 1500-line
`__init__.py`. The split is by concern, not by section length:
data → rendering → action lifecycle → orchestration.

---

## Resuming a run

Pass the same `output_dir` you used the first time. The orchestrator
loads `state.json`, overrides `state["direction"]` with the new
incoming direction (so phrasing tweaks flow into the dispatcher
prompt), and continues from where the previous run left off.

To force a clean re-extraction of the framework while keeping fetched
papers / surveys, set `state["framework"] = None`, clear `audit`, and
reset `iter`. To force re-annotation of all papers under a new
framework, also set every paper's `annotated = False` and clear
`placements`.

---

## Pre-existing one-shot helpers (`tools/`)

Three callables under `tools/` predate the `run_literature` loop and
are used by older workflows that walk through stages by hand:

- `survey_topic` — produce a single-topic survey from scratch
- `identify_gaps` — extract research gaps from a survey
- `comprehensive_lit_review` — full standalone review pipeline

These are exported from the package for backward compatibility but
the loop does not call them.
