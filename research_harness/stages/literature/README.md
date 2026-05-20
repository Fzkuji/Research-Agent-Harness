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

## End-to-end flow

```
┌──────────────────────────────────────────────────────────────────────┐
│  user 调用: run_literature(direction, output_dir, runtime, ...)      │
└──────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
       ┌────────────────────┐
       │ _load_or_init_state│  state.json 存在则恢复，覆盖 direction
       └────────────────────┘
                  │
                  ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │   for outer in 1..max_outer:                                    │
   │   ┌────────────────────────────────────────────────────────┐    │
   │   │ for inner in 1..max_inner:                             │    │
   │   │                                                        │    │
   │   │   ┌──────────────┐                                     │    │
   │   │   │ _lit_decide  │ ← 喂入 state_summary +              │    │
   │   │   │  (picker LLM)│   framework_preview + 动作 catalog  │    │
   │   │   └──────────────┘                                     │    │
   │   │          │                                             │    │
   │   │          ▼  返回 {"call":"<action>","args":{...}}      │    │
   │   │   ┌────────────────────────────────────────────┐       │    │
   │   │   │ _dispatch  ──按 action 分发──→             │       │    │
   │   │   │   • seed_surveys      (找 survey)          │       │    │
   │   │   │   • extract_framework (建/刷 taxonomy)     │       │    │
   │   │   │   • search_papers     (按 leaf 找 primary) │       │    │
   │   │   │   • annotate_papers   (落位 + 写贡献摘要)  │       │    │
   │   │   │   • evolve_framework  (重构树)             │       │    │
   │   │   │   • digest_paper      (单篇结构化解读)     │       │    │
   │   │   │   • done              (退出)               │       │    │
   │   │   └────────────────────────────────────────────┘       │    │
   │   │          │                                             │    │
   │   │          ▼                                             │    │
   │   │   ┌──────────────────────────┐                         │    │
   │   │   │ _merge_<action>(state,…) │ 写回 state +            │    │
   │   │   │                          │ audit log + 落盘        │    │
   │   │   └──────────────────────────┘                         │    │
   │   │          │                                             │    │
   │   │          ▼                                             │    │
   │   │   ┌──────────────────┐                                 │    │
   │   │   │ _flush_artifacts │ 重写 topics/ orphans/ surveys/  │    │
   │   │   │                  │ + audit.md + README snapshot    │    │
   │   │   └──────────────────┘                                 │    │
   │   │          │                                             │    │
   │   │          └─ action=="done" scope=cycle → break inner   │    │
   │   │             action=="done" scope=all   → stop_all=True │    │
   │   └────────────────────────────────────────────────────────┘    │
   │                                                                 │
   │   ┌─────────────────────────────────────────────┐               │
   │   │ end-of-cycle compensation:                  │               │
   │   │   evolve_framework (无条件跑一次)           │               │
   │   │   _reconcile_placements                     │               │
   │   │     (snap 失效 placement 到现存 leaf 祖先； │               │
   │   │      失败则 drop + 标 paper 重 annotate)    │               │
   │   └─────────────────────────────────────────────┘               │
   │                                                                 │
   │   if stop_all: break                                            │
   └─────────────────────────────────────────────────────────────────┘
                  │
                  ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ _run_final_synthesize  (Python 编排，不是单 LLM 调用)           │
   │                                                                 │
   │   ┌─────────────────────────────────────────────────────────┐   │
   │   │ 计算共享输入: framework_outline / counts / hierarchical │   │
   │   │   §3 outline / compact papers / surveys                 │   │
   │   └─────────────────────────────────────────────────────────┘   │
   │                          │                                      │
   │           ┌──────────────┼──────────────┬─────────────┐         │
   │           ▼              ▼              ▼             ▼         │
   │   _write_abstract  _write_intro  _write_taxonomy  ...           │
   │           │              │              │                       │
   │           ▼              ▼              ▼                       │
   │   00_abstract.md   01_intro.md    02_taxonomy.md (各 1 LLM 调用)│
   │                                                                 │
   │   for each top-level §3 branch (Off-Policy / On-Policy / ...):  │
   │       _write_branch_detail(branch_outline, branch_papers)       │
   │       → 03_branch_NN_<slug>.md  (每分支 1 LLM 调用)             │
   │                                                                 │
   │   _write_cross_cutting   → 04_cross_cutting.md                  │
   │   _write_research_gaps   → 05_research_gaps.md                  │
   │   placeholder            → 06_references_placeholder.md         │
   │                                                                 │
   │   拼接所有片段 → synthesis/review.md                            │
   │                                                                 │
   │   ┌──────────────────────────────────────┐                      │
   │   │ _splice_bibliography_into_review     │  程序化遍历          │
   │   │   把 §6 占位符替换为 bib block       │  state.papers /      │
   │   │   (placeholder 缺失时 fallback 找    │  surveys 直出，      │
   │   │    `## References` heading)          │  不让 LLM 写         │
   │   └──────────────────────────────────────┘                      │
   │                                                                 │
   │   ┌─────────────────────────────────────┐                       │
   │   │ _audit_section3_headings            │                       │
   │   │   每个 framework leaf 名是否在 §3   │                       │
   │   │   任意深度 heading 出现             │                       │
   │   └─────────────────────────────────────┘                       │
   │                                                                 │
   │   ┌─────────────────────────────────────┐                       │
   │   │ _audit_citations                    │                       │
   │   │   §1-5 出现的 arXiv id 是否都在     │                       │
   │   │   state；不在的写 _citation_audit.md│                       │
   │   └─────────────────────────────────────┘                       │
   └─────────────────────────────────────────────────────────────────┘
                  │
                  ▼
              return {direction, output_dir, iterations, done, ...}
```

**关键不变量**：
- `state.json` 是唯一真相源，每个 action 后立即落盘；`topics/` `orphans/` 每 tick 重写以与 framework 同步。
- `papers/` 是扁平 PDF 共享缓存（search / annotate / digest 共用 `<safe_id>.pdf`）。
- `digests/<safe_id>/digest.md` 单篇专属文件夹，同目录可放后续衍生物。
- `synthesis/sections/` 保留每节中间产物，便于单节重跑或 debug。
- bib 与 citation audit 是程序化反幻觉防线，不依赖 LLM 自律。

**两个收敛信号**（picker 自行决定 `done`）：
1. 框架稳定 + 每 leaf ≥5 papers + 无 orphan + 无 abstract_only → `done scope=all`
2. `no_delta_streak` 累积（每次 evolve 无非平凡变更 +1，有则归零），作为"已到稳态"的客观佐证。

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
| `digest_paper` | Produce a structured single-paper digest (problem / method / experiments / contributions / limitations / connections / notes). Input is a free-form `target` string (arXiv id, title, local pdf path, URL, or unique search query). Output goes to `digests/<safe_id>/digest.md`. Also callable standalone outside the loop. |
| `done` | Stop. `scope="cycle"` exits the inner loop; `scope="all"` ends the run. |

End-of-cycle compensation runs `evolve_framework` once unconditionally
so structural cleanup happens at least once per outer cycle (the
inner loop tends to favor search/annotate).

End-of-run finalization runs `synthesize_literature` once. It is a
**Python orchestrator** (not a single LLM call) that drives one leaf
per section to keep prompts tight and errors local:

| Sub-leaf | Section |
|---|---|
| `_write_abstract` | Abstract |
| `_write_introduction` | §1 Introduction |
| `_write_taxonomy_overview` | §2 Taxonomy (overview only — bullets + 2 short paragraphs, NOT detailed review) |
| `_write_branch_detail` | §3.X — one call per top-level method-side branch; the branch's nested outline (`3.X.Y`, `3.X.Y.Z`) is computed by the orchestrator and passed in as authoritative |
| `_write_cross_cutting` | §4 Cross-cutting synthesis |
| `_write_research_gaps` | §5 Research gaps |

Each piece is written to `synthesis/sections/*.md`, the orchestrator
concatenates them into `synthesis/review.md`, then a programmatic
bibliography is spliced into §6 (walking `state.papers` +
`state.surveys` directly, NOT the LLM — this catches hallucinated
citations). A citation audit then flags any arXiv IDs in the prose
that are not in state, and a §3 heading audit verifies every
framework leaf appears as a heading at any depth.

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
├── papers/<id>.pdf         # downloaded PDFs (flat shared cache —
│                           #   reused by search / annotate / digest)
├── digests/<safe_id>/      # one folder per digest_paper run
│   ├── digest.md           #   the structured paper digest
│   └── ...                 #   notes.md / figures/ / followup_code.py
│                           #   (any auxiliary files for that paper)
└── synthesis/
    ├── review.md           # final review (assembled from sections/)
    ├── sections/           # per-section md (abstract, §1, §2, §3.X
    │                       #   per branch, §4, §5, references stub)
    └── _citation_audit.md  # only if unknown arXiv IDs detected
```

`topics/` and `orphans/` are wiped and regenerated each tick so
`evolve_framework` ops (merge / split / rename / drop) are reflected
immediately. `surveys/`, `papers/` (PDFs), and `digests/` are
append-only. `synthesis/` is only written at end of run.

PDF cache (`papers/`) is flat by design — `search_papers`,
`annotate_papers`, and `digest_paper` all read from and write to the
same `<safe_id>.pdf` files so a paper is never downloaded twice.
The per-paper folder under `digests/` holds digest-specific
artifacts only; the PDF stays in `papers/`.

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
├── digest_paper.py        # leaf @agentic_function (standalone-
│                          #   callable single-paper digest)
├── synthesize_literature.py    # Python orchestrator + 6 section
│                          #   sub-leaves (abstract / §1 / §2 /
│                          #   §3 per top-level branch / §4 / §5)
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
