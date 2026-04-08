"""
Shared reference documents for the research pipeline.

These are structured guidelines that can be loaded into @agentic_function
prompts as additional context. They are NOT standalone skills — they are
reference material that writing/review/submission functions can import.

Usage:
    from research_harness.references import WRITING_PRINCIPLES
    from research_harness.references import CITATION_DISCIPLINE
    from research_harness.references import VENUE_CHECKLISTS
"""

from research_harness.references.writing_principles import WRITING_PRINCIPLES
from research_harness.references.citation_discipline import CITATION_DISCIPLINE
from research_harness.references.venue_checklists import VENUE_CHECKLISTS

__all__ = [
    "WRITING_PRINCIPLES",
    "CITATION_DISCIPLINE",
    "VENUE_CHECKLISTS",
]
