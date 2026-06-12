"""citation_gate — deterministic citation-existence verification.

Checks every entry of a BibTeX file against four bibliographic indexes
(Crossref, OpenAlex, Semantic Scholar, arXiv) and reduces the per-index
outcomes to a 3-class verdict per citation:

  true         — at least one index matched: the citation exists
  false        — a DOI / arXiv ID provably failed to resolve: fabrication
                 evidence (a title-only miss NEVER produces false)
  unresolvable — coverage gap or index outage: advisory, not proof

Zero-config entry point::

    from research_harness.citation_gate import verify_bib
    result = verify_bib("paper/references.bib")

Lookups are cached (SQLite, 90-day TTL, ~/.cache/research_harness/) so
review-loop reruns don't re-hit the rate-limited APIs.

Resolver clients, reducer semantics and cache are vendored from
academic-research-skills (c) Cheng-I Wu, CC BY-NC 4.0 — see LICENSE in this
directory. No network credentials required; set S2_API_KEY /
CITATION_GATE_EMAIL for higher rate tiers.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from research_harness.citation_gate.arxiv_client import (
    ArxivClient, ArxivUnavailable,
)
from research_harness.citation_gate.cache import VerificationCache
from research_harness.citation_gate.crossref_client import (
    CrossrefClient, CrossrefUnavailable,
)
from research_harness.citation_gate.openalex_client import (
    OpenAlexClient, OpenAlexUnavailable,
)
from research_harness.citation_gate.semantic_scholar_client import (
    SemanticScholarClient, SemanticScholarUnavailable,
)
from research_harness.citation_gate.bib import parse_bib
from research_harness.citation_gate.reducer import reduce_lookup_verified
from research_harness.citation_gate._resolve import (
    resolve_arxiv,
    resolve_doi_then_title,
    resolve_semantic_scholar,
)

__all__ = ["verify_bib", "verify_entry", "verify_citations", "make_clients"]


def make_clients() -> dict[str, Any]:
    """Build the four resolver clients. Optional env: CITATION_GATE_EMAIL
    (Crossref/OpenAlex polite pool), S2_API_KEY (Semantic Scholar tier)."""
    email = os.environ.get("CITATION_GATE_EMAIL") or None
    return {
        "crossref": CrossrefClient(polite_email=email),
        "openalex": OpenAlexClient(polite_email=email),
        "semantic_scholar": SemanticScholarClient(
            api_key=os.environ.get("S2_API_KEY") or None),
        "arxiv": ArxivClient(),
    }


def _outcome(status: str, queried_by: str | None) -> dict:
    return {"status": status, "queried_by": queried_by}


def _run(resolver, unavailable_exc) -> dict:
    try:
        result = resolver()
    except unavailable_exc:
        return _outcome("unreachable", None)
    if result is None:
        return _outcome("skipped", None)
    unmatched, queried_by = result
    return _outcome("unmatched" if unmatched else "matched", queried_by)


def verify_entry(entry: Mapping[str, Any], clients: Mapping[str, Any],
                 cache: VerificationCache | None = None) -> dict:
    """Verify one citation across the four resolvers.

    `entry` needs citation_key + title; doi / arxiv_id when available make
    the verdict much stronger (id-keyed misses are fabrication evidence).
    """
    outcomes = {
        "crossref": _run(
            lambda: resolve_doi_then_title(
                entry, clients["crossref"], resolver_name="crossref",
                cache=cache),
            CrossrefUnavailable),
        "openalex": _run(
            lambda: resolve_doi_then_title(
                entry, clients["openalex"], resolver_name="openalex",
                cache=cache),
            OpenAlexUnavailable),
        "semantic_scholar": _run(
            lambda: resolve_semantic_scholar(
                entry, clients["semantic_scholar"], cache=cache),
            SemanticScholarUnavailable),
        "arxiv": _run(
            lambda: resolve_arxiv(entry, clients["arxiv"], cache=cache),
            ArxivUnavailable),
    }
    return {
        "citation_key": entry.get("citation_key"),
        "lookup_verified": reduce_lookup_verified(outcomes),
        "resolver_outcomes": outcomes,
        "verification_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def verify_bib(bib_path: str, *, report_path: str | None = None,
               cache_path: str | None = None,
               use_cache: bool = True,
               clients: Mapping[str, Any] | None = None) -> dict:
    """Verify every entry of a .bib file. Returns a summary dict and writes
    a markdown report next to the .bib (or at report_path).

    Summary: {"total", "true", "false", "unresolvable", "problems",
    "results", "report_path"} — "false" / "unresolvable" list citation keys.
    """
    bib_path = os.path.abspath(os.path.expanduser(bib_path))
    entries, problems = parse_bib(bib_path)
    clients = clients or make_clients()
    cache = VerificationCache(cache_path) if use_cache else None

    results = []
    for entry in entries:
        results.append(verify_entry(entry, clients, cache=cache))

    by_verdict: dict[str, list[str]] = {"true": [], "false": [],
                                        "unresolvable": []}
    for r in results:
        by_verdict[r["lookup_verified"]].append(r["citation_key"])

    if report_path is None:
        report_path = str(Path(bib_path).with_name("citation_gate_report.md"))
    _write_report(report_path, bib_path, results, problems)

    return {
        "total": len(results),
        "true": by_verdict["true"],
        "false": by_verdict["false"],
        "unresolvable": by_verdict["unresolvable"],
        "problems": problems,
        "results": results,
        "report_path": report_path,
    }


def _write_report(report_path: str, bib_path: str,
                  results: list[dict], problems: list[str]) -> None:
    lines = [
        "# Citation existence report",
        "",
        f"Source: `{bib_path}`  ",
        f"Verified: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        "against Crossref / OpenAlex / Semantic Scholar / arXiv",
        "",
    ]
    fabricated = [r for r in results if r["lookup_verified"] == "false"]
    unresolved = [r for r in results if r["lookup_verified"] == "unresolvable"]
    lines.append(f"**{len(results)} citations: "
                 f"{len(results) - len(fabricated) - len(unresolved)} verified, "
                 f"{len(fabricated)} LIKELY FABRICATED, "
                 f"{len(unresolved)} unresolvable.**\n")
    if fabricated:
        lines.append("## Likely fabricated (id-keyed lookup failed)\n")
        lines.append("A DOI or arXiv ID that provably fails to resolve is "
                     "strong fabrication evidence. Remove or replace these:\n")
        for r in fabricated:
            misses = [n for n, o in r["resolver_outcomes"].items()
                      if o["status"] == "unmatched"]
            lines.append(f"- `{r['citation_key']}` — unmatched in: "
                         f"{', '.join(misses)}")
        lines.append("")
    if unresolved:
        lines.append("## Unresolvable (advisory)\n")
        lines.append("Not found by title in any index — could be a coverage "
                     "gap (regional / non-English / pre-digital venue) or a "
                     "fabrication without a checkable id. Verify manually:\n")
        for r in unresolved:
            lines.append(f"- `{r['citation_key']}`")
        lines.append("")
    if problems:
        lines.append("## Parser warnings\n")
        lines.extend(f"- {p}" for p in problems)
        lines.append("")
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")


def verify_citations(bib_path: str) -> str:
    """Verify every citation in a BibTeX file against four bibliographic indexes (Crossref/OpenAlex/Semantic Scholar/arXiv) — deterministic check that flags fabricated DOIs/arXiv IDs and unresolvable references; writes a report next to the .bib.

    Args:
        bib_path: Path to the references.bib file (or any .bib).

    Returns:
        Summary string naming the report path and any fabricated keys.
    """
    try:
        summary = verify_bib(bib_path)
    except FileNotFoundError:
        return f"ERROR: no such .bib file: {bib_path}"
    parts = [
        f"Checked {summary['total']} citations: "
        f"{len(summary['true'])} verified, "
        f"{len(summary['false'])} likely fabricated, "
        f"{len(summary['unresolvable'])} unresolvable.",
    ]
    if summary["false"]:
        parts.append("LIKELY FABRICATED: " + ", ".join(summary["false"]))
    if summary["unresolvable"]:
        parts.append("Unresolvable (verify manually): "
                     + ", ".join(summary["unresolvable"]))
    parts.append(f"Report saved to {summary['report_path']}.")
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Verify .bib citations against 4 bibliographic indexes")
    parser.add_argument("bib", help="Path to .bib file")
    parser.add_argument("-o", "--report", help="Report output path")
    parser.add_argument("--no-cache", action="store_true",
                        help="Skip the SQLite lookup cache")
    args = parser.parse_args(argv)
    summary = verify_bib(args.bib, report_path=args.report,
                         use_cache=not args.no_cache)
    print(f"{summary['total']} citations: {len(summary['true'])} verified, "
          f"{len(summary['false'])} likely fabricated, "
          f"{len(summary['unresolvable'])} unresolvable")
    for key in summary["false"]:
        print(f"  FABRICATED? {key}")
    for key in summary["unresolvable"]:
        print(f"  unresolvable {key}")
    print(f"report: {summary['report_path']}")
    return 1 if summary["false"] else 0


if __name__ == "__main__":
    sys.exit(main())
