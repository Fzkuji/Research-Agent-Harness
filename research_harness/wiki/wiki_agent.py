"""
wiki_agent — @agentic_function entry point for Research Wiki operations.

The LLM reads the docstring, understands all wiki subcommands,
and decides which operations to perform based on the user's request.
"""

from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def research_wiki(task: str, runtime: Runtime) -> str:
    """You manage a persistent Research Wiki — a per-project knowledge base
    that accumulates papers, ideas, experiments, claims, and their
    relationships across the entire research lifecycle.

    The wiki lives in a `research-wiki/` directory inside the project.

    ═══════════════════════════════════════════════════════════════
    ENTITY TYPES
    ═══════════════════════════════════════════════════════════════

    | Entity      | Directory       | Node ID format   |
    |-------------|-----------------|------------------|
    | Paper       | papers/         | paper:<slug>     |
    | Idea        | ideas/          | idea:<id>        |
    | Experiment  | experiments/    | exp:<id>         |
    | Claim       | claims/         | claim:<id>       |

    ═══════════════════════════════════════════════════════════════
    RELATIONSHIP TYPES (stored in graph/edges.jsonl)
    ═══════════════════════════════════════════════════════════════

    extends, contradicts, addresses_gap, inspired_by,
    tested_by, supports, invalidates, supersedes

    ═══════════════════════════════════════════════════════════════
    SUBCOMMANDS
    ═══════════════════════════════════════════════════════════════

    init
      Create the wiki directory structure: papers/, ideas/,
      experiments/, claims/, graph/, index.md, log.md, gap_map.md,
      query_pack.md.
      Use: python -m research_harness.wiki.research_wiki init <wiki_root>

    ingest "<paper title>" — arxiv: <id>
      Add a paper to the wiki:
      1. Fetch metadata (arXiv/DBLP/Semantic Scholar)
      2. Generate slug: <author><year>_<keywords>
      3. Check dedup — update if exists
      4. Create papers/<slug>.md with full schema:
         - Frontmatter: type, node_id, title, authors, year, venue, tags, relevance
         - Sections: One-line thesis, Problem/Gap, Method, Key Results,
           Assumptions, Limitations, Reusable Ingredients, Open Questions,
           Claims, Connections, Relevance to This Project
      5. Extract and add relationship edges
      6. Update index.md, gap_map.md
      7. Rebuild query_pack.md
      8. Append to log.md

    query "<topic>"
      Generate query_pack.md — a compressed, context-friendly summary:
      - Project direction (300 chars)
      - Top 5 gaps (1200 chars)
      - Failed ideas — ALWAYS included, highest anti-repetition value (1400 chars)
      - Key papers (1800 chars)
      - Recent relationship chains (900 chars)
      Hard budget: max 8000 chars total.
      Use: python -m research_harness.wiki.research_wiki rebuild_query_pack <root>

    update <node_id> — <field>: <value>
      Update a specific entity's field. Examples:
        update paper:chen2025 — relevance: core
        update idea:001 — outcome: negative
        update claim:C1 — status: invalidated
      After update: rebuild query_pack, append to log.

    lint
      Health check:
      1. Orphan pages (zero edges)
      2. Stale claims (status: reported, older than 14 days)
      3. Contradictions (both supports + invalidates)
      4. Missing connections (papers sharing 2+ tags, no edge)
      5. Dead ideas (stage: proposed, never tested)
      6. Sparse pages (3+ empty sections)
      Output LINT_REPORT.md.

    stats
      Quick overview of wiki contents:
      papers, ideas (failed/succeeded), experiments, claims
      (supported/invalidated), edges count.
      Use: python -m research_harness.wiki.research_wiki stats <root>

    ═══════════════════════════════════════════════════════════════
    KEY RULES
    ═══════════════════════════════════════════════════════════════

    - graph/edges.jsonl is the single source of truth for relationships.
      Page "Connections" sections are auto-generated views.
    - Use canonical node IDs everywhere: paper:<slug>, idea:<id>, etc.
    - Failed ideas are the most valuable memory. Never prune them.
    - query_pack.md is hard-budgeted at 8000 chars.
    - Append to log.md for every mutation.

    ═══════════════════════════════════════════════════════════════
    CLI HELPER
    ═══════════════════════════════════════════════════════════════

    The Python helper at research_harness/wiki/research_wiki.py provides:
      init, slug, add_edge, rebuild_query_pack, stats, log

    Use it via: python -m research_harness.wiki.research_wiki <subcommand>

    Based on the user's task, perform the appropriate wiki operations.
    You can chain multiple operations (e.g., ingest a paper, add edges,
    rebuild query_pack).
    """
    return runtime.exec(content=[
        {"type": "text", "text": task},
    ])
