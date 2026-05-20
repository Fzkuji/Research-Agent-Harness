# Wiki — Obsidian-style global research knowledge base

A persistent, cross-project subject wiki. Each topic and each paper
is a folder containing a same-named `.md`; the folder tree is the
taxonomy; cross-topic links are Obsidian `[[wikilinks]]`. Default
vault root: `~/Documents/Research-Wiki/`.

Inspired by Karpathy's LLM Wiki pattern, the user's existing
`~/Documents/awesome-AI/` notes, and the ARIS per-project
`research-wiki/` skill.

## Design principles

1. **Filename is the canonical node id.** `[[Preference optimization]]`
   resolves by filename anywhere in the tree. No slug + frontmatter
   id indirection.
2. **Folder hierarchy is the taxonomy.** Path = parent chain.
3. **Folder = topic with children; bare `.md` = leaf topic.** A leaf
   gets promoted to a folder when it grows children.
4. **Folder name == inner `.md` stem, verbatim.** No prefix
   stripping, no case smoothing.
5. **Topic page is a Wikipedia-style article**, not a list of papers.
6. **Relationships via wikilinks**, not via `graph/edges.jsonl`.
7. **Wiki is subject-only.** Per-project lifecycle artifacts
   (ideas/experiments/claims) belong in the project's own ARIS-style
   `research-wiki/` directory inside the project, not in this wiki.

## Directory layout

```
~/Documents/Research-Wiki/
  AGENTS.md                    # schema (governance — read before editing)
  README.md
  lint-report.md               # written by wiki_lint
  Attachments/                 # flat, all images and PDFs

  1. Philosophy/
    1. Philosophy.md
  4. Artificial intelligence/
    4. Artificial intelligence.md
    2. Approaches/
      2. Approaches.md
      Artificial neural network/
        Artificial neural network.md
        Large language model/
          Large language model.md
          Post-training/
            Post-training.md
            Preference optimization/
              Preference optimization.md
              rafailov2023_direct_preference_optimization/
                rafailov2023_direct_preference_optimization.md
              meng2024_simpo_simple/
                meng2024_simpo_simple.md
```

## Frontmatter

Every `.md` MUST declare `type:`, one of `topic` or `paper`. This is
the single source of truth distinguishing nodes, since paper and
topic pages live at the same path level.

**Topic page** — minimal:
```yaml
---
type: topic
---
```

**Paper page** — full schema:
```yaml
---
type: paper
arxiv: "2305.18290"
year: 2023
title: "Direct Preference Optimization: ..."
authors:
  - "Rafael Rafailov"
  - "..."
venue: "arXiv"
topics: []        # optional wikilinks to additional topics this
                  # paper belongs to beyond its canonical location
---
```

## Wikilinks

- Always filename-only: `[[Preference optimization]]`. Never with
  path. Obsidian and the rewriter both resolve by filename.
- Alias: `[[rafailov2023_direct_preference_optimization|DPO]]`.
- Section anchor: `[[Post-training#Open questions]]`.

## Cross-topic membership (Wikipedia categories model)

A paper has ONE canonical folder. To declare it also belongs to
other topics, list them in the paper's frontmatter `topics:`. The
non-canonical topic pages do not contain duplicate files; they list
papers via Obsidian Dataview or the native backlinks panel.

## Operations

Nine entry points, all registered under the `knowledge` stage in
`research_harness/registry.py`. Three are pure Python (deterministic
file ops); six are agentic (drive an LLM with tool access to read
and edit pages).

### `wiki_init(wiki_root)`

Pure Python. Create the vault directory, write `AGENTS.md` and
`README.md` if absent, create `Attachments/`, init a git repo,
commit the scaffolding. Idempotent.

### `wiki_import(source, wiki_root, mode)`

Pure Python. Two modes:

- `link`: use `source` directly as vault root. Requires
  `wiki_root == source`. No file copy. Edits land in the source.
- `copy`: copy `source` contents into `wiki_root` (which must be
  empty or contain only scaffolding). Source untouched; vault
  diverges.

After import, run `wiki_migrate` to add `type:` to legacy pages.

### `wiki_migrate(wiki_root, default_type)`

Pure Python. Walks the vault, finds `.md` files without `type:`
frontmatter, inserts one. Default = caller's `default_type`
(`"topic"` for hierarchical notes import, `"paper"` for a flat dump);
overridden to `paper` when the existing frontmatter has paper-ish
fields (`arxiv` / `authors` / `venue`).

### `wiki_ingest_paper(arxiv_id, wiki_root, force, download_pdf)`

Agentic. Pipeline:

1. **Python**: fetch arXiv metadata (Atom API), generate slug
   `<author><year>_<keyword>`, check existence (`force=False` →
   skip), optionally download PDF to `Attachments/<slug>.pdf`,
   compute folder tree.
2. **LLM**: read the folder tree, optionally Read 1–3 candidate
   topic pages, pick the deepest topic that comfortably covers the
   paper (no new topic creation — that's `wiki_refactor`'s job).
3. **LLM**: Write `<canonical-topic>/<slug>/<slug>.md` with the
   required frontmatter + the 5-section body (One-line thesis /
   Problem / Method / Key Results / Limitations). LLM is instructed
   to mark "from abstract; verify against full text" on uncertain
   claims rather than fabricate.
4. **LLM**: Edit the parent topic page to integrate a paragraph
   about this paper into the prose (not bullet append). Stub topics
   (<200 words) get a short opening paragraph instead.
5. **LLM**: optionally insert a one-sentence cross-reference in
   another topic and add that topic to the paper's `topics:`
   frontmatter — only when relevance is obvious.
6. **Python**: stage + commit all changes as
   `wiki: ingest <slug> (<arxiv_id>)`.

### `wiki_survey(topic, wiki_root, depth)`

Agentic. Rewrites a topic page as a Wikipedia-style article from
its child paper and subtopic pages.

1. **Python**: locate the topic by filename, list direct paper and
   subtopic children (distinguish by `type:` in their frontmatter).
2. **LLM**: Read each paper page (one-line thesis + method), cluster
   them into 2–5 natural sub-areas.
3. **LLM**: rewrite the topic's `.md` body — opening intro + one
   `##` section per cluster discussing relevant papers in prose with
   `[[wikilinks]]` + a `## Subtopics` section if any. Frontmatter
   preserved verbatim.
4. **LLM**: if `depth > 0`, recurse into each subtopic with
   `depth - 1`.
5. **Python**: commit.

### `wiki_research(direction, wiki_root, k)`

Agentic. Multi-paper exploration of a new direction. Composition of
ingest + survey:

1. Map the direction to the closest existing topic.
2. Search the web (arXiv, Semantic Scholar, Google Scholar) for up
   to `k` papers; prefer seminal then recent. Skip duplicates.
3. For each picked paper, run the ingest schema inline (fetch
   metadata via `web_fetch`, slug, write paper page) — skip
   per-paper parent-page integration to avoid churn.
4. After all ingests, run a survey-style rewrite of the affected
   topic page so all newly added papers integrate into the article.
5. Commit.

This is the equivalent of running `stages/literature/`'s loop with
wiki as the output sink.

### `wiki_refactor(topic, wiki_root)`

Agentic. When a topic has accumulated ≥6 direct paper children, the
LLM proposes 2–4 subtopic clusters, creates the subtopic folders
(with `type: topic` and short intros), moves each paper folder
into the right subtopic, and rewrites the parent topic page to
mention the new subtopics. Wikilinks to the papers stay valid
because they use filename stems, not paths.

### `wiki_rename(old_name, new_name, wiki_root)`

Pure Python.

1. Locate `<old>/<old>.md` anywhere in the vault.
2. Move the enclosing folder to `<new>/`.
3. Rename the inner file to `<new>.md`.
4. Scan every `.md` in the vault and rewrite `[[<old>]]` →
   `[[<new>]]` in both body and YAML frontmatter values. Preserves
   alias (`|...`) and anchor (`#...`) parts.
5. Commit. No redirect stub left behind (vault is self-contained;
   `git log` recovers old names if needed).

### `wiki_lint(wiki_root)`

Pure Python. Scans the vault and writes `lint-report.md` covering:

- Pages missing `type:` frontmatter
- Pages with bad `type:` (not `paper` or `topic`)
- Filenames that don't match their parent folder name
- Paper pages missing required fields (`arxiv` / `year` / `title` /
  `authors`)
- Broken wikilinks (target page does not exist)
- Orphan pages (no inbound, no outbound)

Code-block content (inside backticks or fences) is excluded from
wikilink scanning, so example links in prose don't trigger false
positives. `AGENTS.md` / `README.md` / `lint-report.md` at the
vault root are treated as scaffolding and skipped.

## Tool availability across providers

Each agentic function calls `runtime.exec(content=[...])` without
passing `tools=`. OpenProgram's runtime fallback resolves this to
`DEFAULT_TOOLS` (`bash / read / write / edit / apply_patch / glob /
grep / list / todo_*`) for every provider — so the wiki works
identically on `claude-max-proxy`, `openai-codex`, `anthropic`,
`openai`, `gemini`. No per-function tool declaration needed.

## Module layout

```
research_harness/stages/wiki/
  README.md                 # this file
  __init__.py               # exports the 9 entry points
  _helpers.py               # slugify, fetch_arxiv_metadata,
                            # parse/dump_frontmatter, iter_md_files,
                            # folder_tree, find_node,
                            # rewrite_wikilinks, git_commit_all
  wiki_init.py              # pure Python
  wiki_import.py            # pure Python
  wiki_migrate.py           # pure Python
  wiki_lint.py              # pure Python
  wiki_rename.py            # pure Python
  wiki_ingest_paper.py      # agentic
  wiki_survey.py            # agentic
  wiki_research.py          # agentic
  wiki_refactor.py          # agentic
```

The legacy stub at `research_harness/wiki/` (2026-04-08) is no
longer referenced from `registry.py`. Safe to delete.

## Invocation

Via the harness CLI (top-level LLM selects stage then function):

```bash
python -m research_harness "Ingest arXiv 2305.18290 into the wiki at \
  /Users/fzkuji/Documents/Research-Wiki" --work-dir /tmp/run
```

Or programmatically:

```python
from research_harness.stages.wiki import (
    wiki_init, wiki_import, wiki_migrate,
    wiki_ingest_paper, wiki_survey, wiki_research, wiki_refactor,
    wiki_rename, wiki_lint,
)

wiki_init("~/Documents/Research-Wiki")
# Agentic functions need an injected runtime; called via the harness
# main entry, not directly.
```

## Open issues / future work

1. **Embedding-based topic match** for very large vaults
   (500+ topic nodes) where folder-tree-string no longer fits in a
   prompt. Today's LLM-driven path scales fine for the foreseeable
   size.
2. **Concurrent Obsidian editing during CLI ingest**: MVP relies on
   the assumption that a user does not hand-edit pages while a CLI
   ingest is running. No file lock implemented. Git rollback if
   needed.
3. **Cross-vault import** from a finished `stages/literature/`
   project (`wiki ingest literature-project <path>`). Not built;
   would map literature/'s framework leaves to wiki topics and
   ingest each annotated paper.
4. **Naming disambiguation** for genuine same-name collisions
   (`Inference (statistics)` vs `Inference (neural networks)`): the
   wiki supports this via parenthetical suffix, but the workflow is
   manual — `wiki_ingest_paper` reports a collision error rather
   than auto-disambiguating.
