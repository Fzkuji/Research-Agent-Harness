"""Wiki stage — Obsidian-style global research knowledge base.

See README.md in this directory for design rationale.

Entry points:
  wiki_init           — create a new vault
  wiki_import         — bring an external notes dir into the wiki
  wiki_migrate        — backfill `type:` frontmatter on legacy notes
  wiki_ingest         — universal single-source ingest (arxiv id / URL / PDF)
  wiki_survey         — rewrite a topic page as a Wikipedia article
  wiki_research       — multi-paper exploration of a new direction
  wiki_refactor       — split a crowded topic into subtopics
  wiki_rename         — rename a node and rewrite all wikilinks
  wiki_lint           — scan the vault for schema and link health
"""

from research_harness.stages.wiki.wiki_init import wiki_init
from research_harness.stages.wiki.wiki_import import wiki_import
from research_harness.stages.wiki.wiki_import_litreview import wiki_import_litreview
from research_harness.stages.wiki.wiki_migrate import wiki_migrate
from research_harness.stages.wiki.wiki_ingest import wiki_ingest
from research_harness.stages.wiki.wiki_survey import wiki_survey
from research_harness.stages.wiki.wiki_research import wiki_research
from research_harness.stages.wiki.wiki_refactor import wiki_refactor
from research_harness.stages.wiki.wiki_rename import wiki_rename
from research_harness.stages.wiki.wiki_lint import wiki_lint
from research_harness.stages.wiki.wiki_dedup import wiki_dedup

__all__ = [
    "wiki_init",
    "wiki_import",
    "wiki_import_litreview",
    "wiki_migrate",
    "wiki_ingest",
    "wiki_survey",
    "wiki_research",
    "wiki_refactor",
    "wiki_rename",
    "wiki_lint",
    "wiki_dedup",
]
