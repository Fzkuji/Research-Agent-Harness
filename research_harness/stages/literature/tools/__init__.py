"""Older standalone helpers that pre-date the `run_literature` loop.

These are independent `@agentic_function` callables not part of the
state-driven loop. Kept here for backward-compat with earlier
workflows that called them directly.

  - `survey_topic`            — produce a single-topic survey
  - `identify_gaps`           — extract gaps from a survey
  - `comprehensive_lit_review` — full standalone review pipeline
"""
from research_harness.stages.literature.tools.comprehensive_lit_review import (
    comprehensive_lit_review,
)
from research_harness.stages.literature.tools.identify_gaps import (
    identify_gaps,
)
from research_harness.stages.literature.tools.survey_topic import (
    survey_topic,
)

__all__ = [
    "comprehensive_lit_review",
    "identify_gaps",
    "survey_topic",
]
