# Adapted from academic-research-skills v3.12.0 scripts/contamination_signals.py
# https://github.com/Imbad0202/academic-research-skills
# (c) Cheng-I Wu — CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/)
# Changes: ref_slug/anchor/passport plumbing removed; cache threaded through
# (ARS left cache-through unwired at the gate layer); see LICENSE here.
"""Per-resolver id-then-title flows with optional cache-through.

Each resolver attempt is keyed in the cache by (citation_key, resolver_name,
query_form) where query_form encodes BOTH the id and the title of the attempt
— a title-fallback hit must never be cached under the bare id key, or a later
run would falsely conclude the id itself resolved.

`queried_by` is the narrowed-false signal (C-V6(a)): 'id' when the entry
carries the resolver's exact identifier (so an id-keyed lookup was attempted,
even if it fell through to title search), else 'title'. An `unmatched` with
queried_by='id' is fabrication evidence; a title-only miss is a coverage gap.

Degradation exceptions (XxxUnavailable) propagate and are NEVER cached.
"""

from __future__ import annotations

from typing import Any, Mapping

from research_harness.citation_gate._text_similarity import _similarity

# The clients accept title-search candidates at 0.70 similarity — loose
# enough that a short fabricated title can match a different real work
# ("Quantum Attention Fields" vs "Quantum Fields" scores 0.74). Verdict-
# upgrading title hits are re-checked at this stricter bar; ID cross-checks
# keep the lenient 0.70 (strictness there would CREATE false fabrication
# flags instead of preventing false verifications).
_STRICT_TITLE_SIMILARITY = 0.85


def _candidate_title(candidate: Mapping[str, Any]) -> str:
    t = candidate.get("title")
    if isinstance(t, list):
        t = t[0] if t else ""
    return t or candidate.get("display_name") or ""


def _confident_title_hit(candidate, title: str) -> bool:
    """A title-search candidate counts only if its title re-checks at the
    strict bar. A candidate whose title cannot be extracted is NOT
    confident (rejection only downgrades toward 'unresolvable', advisory)."""
    if candidate is None:
        return False
    cand_title = _candidate_title(candidate)
    return bool(cand_title) and (
        _similarity(cand_title, title) >= _STRICT_TITLE_SIMILARITY
    )


def _query_form(id_label: str, id_value: str | None, title: str) -> str:
    return f"{id_label}:{id_value or ''}|title:{title}"


def _cached(cache, citation_key, resolver_name, query_form, compute):
    """Cache-through for a verdict computation. compute() -> unmatched: bool."""
    if cache is None:
        return compute()
    hit = cache.get(citation_key, resolver_name, query_form)
    if hit is not None and "matched" in hit:
        return not hit["matched"]
    unmatched = compute()
    cache.put(citation_key, resolver_name, query_form,
              {"matched": not unmatched})
    return unmatched


def resolve_doi_then_title(entry: Mapping[str, Any], client, *,
                           resolver_name: str,
                           cache=None) -> tuple[bool, str]:
    """Crossref/OpenAlex flow: DOI lookup (title cross-checked), then title
    search on miss. Returns (unmatched, queried_by)."""
    title = entry.get("title", "")
    doi = entry.get("doi")
    queried_by = "id" if doi else "title"

    def compute() -> bool:
        if doi and client.doi_lookup_with_title_check(doi, title) is not None:
            return False
        return not _confident_title_hit(client.title_search(title), title)

    qf = _query_form("doi", doi, title)
    return _cached(cache, entry.get("citation_key"), resolver_name, qf,
                   compute), queried_by


def resolve_arxiv(entry: Mapping[str, Any], client, *,
                  cache=None) -> tuple[bool, str] | None:
    """arXiv flow, applicable only when the entry carries an arXiv ID —
    a non-arXiv citation is not title-searched against arXiv (a miss there
    is a coverage gap, not non-existence evidence). Returns None when
    skipped, else (unmatched, queried_by)."""
    arxiv_id = entry.get("arxiv_id")
    if not arxiv_id:
        return None
    title = entry.get("title", "")

    def compute() -> bool:
        if client.arxiv_id_lookup(arxiv_id, title) is not None:
            return False
        return not _confident_title_hit(client.title_search(title), title)

    qf = _query_form("arxiv", arxiv_id, title)
    return _cached(cache, entry.get("citation_key"), "arxiv", qf,
                   compute), "id"


def resolve_semantic_scholar(entry: Mapping[str, Any], client, *,
                             cache=None) -> tuple[bool, str]:
    """S2 flow: client.lookup(entry) is a single entry-keyed call (DOI-first
    then title internally). Returns (unmatched, queried_by)."""
    title = entry.get("title", "")
    queried_by = "id" if entry.get("doi") else "title"

    def compute() -> bool:
        return not bool(client.lookup(entry).get("matched", False))

    qf = _query_form("doi", entry.get("doi"), title)
    return _cached(cache, entry.get("citation_key"), "semantic_scholar", qf,
                   compute), queried_by
