"""writing_lint — deterministic LaTeX writing lints (no LLM).

Two checks:

  uncited_assertions — quantified/empirical claims (percentages, counts,
      p-values, outperforms/showed verbs) that carry no \\cite and no
      own-result Table/Figure reference. Adapted from ARS's D4-c detector
      (c) Cheng-I Wu, CC BY-NC 4.0 — see LICENSE in this directory.
  citation_context — bare citation dumps, \\cite-as-noun misuse, and
      cargo-cult cites (original code, inspired by ARS's three-layer
      citation lint failure classes).

Zero-config entry points::

    from research_harness.writing_lint import (
        uncited_assertion_check, citation_context_check,
    )
    print(uncited_assertion_check("paper/"))
    print(citation_context_check("paper/"))

Fine-grained layer: check_tex / check_citations accept a path or a LaTeX
string and return ``[{"line", "sentence", "reason"}, ...]``.
"""
from research_harness.writing_lint.citation_context import (
    check_citations, citation_context_check,
)
from research_harness.writing_lint.uncited_assertions import (
    check_tex, detect_uncited, uncited_assertion_check,
)

__all__ = [
    "check_tex", "detect_uncited", "uncited_assertion_check",
    "check_citations", "citation_context_check",
]
