"""Tests for research_harness.citation_gate — bib parsing, verdict reduction,
resolver orchestration with stub clients, and cache behavior. No network."""

import os

import pytest

from research_harness.citation_gate import verify_bib, verify_entry
from research_harness.citation_gate.bib import parse_bib
from research_harness.citation_gate.cache import VerificationCache
from research_harness.citation_gate.reducer import reduce_lookup_verified
from research_harness.citation_gate.crossref_client import CrossrefUnavailable


# ── stub clients ─────────────────────────────────────────────────────

class StubIndexClient:
    """Stands in for Crossref/OpenAlex (doi_lookup_with_title_check +
    title_search) and arXiv (arxiv_id_lookup + title_search)."""

    def __init__(self, id_hit=False, title_hit=False, raise_exc=None):
        self.id_hit = id_hit
        self.title_hit = title_hit
        self.raise_exc = raise_exc
        self.calls = []

    def _maybe_raise(self):
        if self.raise_exc:
            raise self.raise_exc

    def doi_lookup_with_title_check(self, doi, title):
        self.calls.append(("doi", doi))
        self._maybe_raise()
        return {"matched": True} if self.id_hit else None

    def arxiv_id_lookup(self, arxiv_id, title):
        self.calls.append(("arxiv", arxiv_id))
        self._maybe_raise()
        return {"matched": True} if self.id_hit else None

    def title_search(self, title):
        self.calls.append(("title", title))
        self._maybe_raise()
        # Realistic candidate shape: exact-title hit passes the strict
        # 0.85 re-check in _resolve.
        return {"title": [title]} if self.title_hit else None


class StubS2Client:
    def __init__(self, matched=False):
        self.matched = matched
        self.calls = []

    def lookup(self, entry):
        self.calls.append(entry.get("citation_key"))
        return {"matched": self.matched}


def make_stub_clients(**kw):
    return {
        "crossref": kw.get("crossref", StubIndexClient()),
        "openalex": kw.get("openalex", StubIndexClient()),
        "semantic_scholar": kw.get("semantic_scholar", StubS2Client()),
        "arxiv": kw.get("arxiv", StubIndexClient()),
    }


# ── reducer semantics ────────────────────────────────────────────────

class TestReducer:
    def test_matched_wins(self):
        out = {
            "a": {"status": "matched", "queried_by": "id"},
            "b": {"status": "unmatched", "queried_by": "id"},
        }
        assert reduce_lookup_verified(out) == "true"

    def test_id_keyed_unmatched_is_false(self):
        out = {
            "a": {"status": "unmatched", "queried_by": "id"},
            "b": {"status": "unreachable", "queried_by": None},
        }
        assert reduce_lookup_verified(out) == "false"

    def test_title_only_miss_is_unresolvable_not_false(self):
        out = {
            "a": {"status": "unmatched", "queried_by": "title"},
            "b": {"status": "unmatched", "queried_by": "title"},
        }
        assert reduce_lookup_verified(out) == "unresolvable"

    def test_all_skipped_is_unresolvable(self):
        out = {"a": {"status": "skipped", "queried_by": None}}
        assert reduce_lookup_verified(out) == "unresolvable"


# ── verify_entry orchestration ───────────────────────────────────────

class TestVerifyEntry:
    def test_real_citation_verifies(self):
        clients = make_stub_clients(
            crossref=StubIndexClient(id_hit=True))
        r = verify_entry(
            {"citation_key": "good", "title": "T", "doi": "10.1/x"}, clients)
        assert r["lookup_verified"] == "true"

    def test_bogus_doi_is_false(self):
        clients = make_stub_clients()  # all miss
        r = verify_entry(
            {"citation_key": "fake", "title": "T", "doi": "10.9999/nope"},
            clients)
        assert r["lookup_verified"] == "false"
        assert r["resolver_outcomes"]["crossref"]["queried_by"] == "id"

    def test_no_id_no_hit_is_unresolvable(self):
        clients = make_stub_clients()
        r = verify_entry({"citation_key": "obscure", "title": "T"}, clients)
        assert r["lookup_verified"] == "unresolvable"

    def test_arxiv_skipped_without_id(self):
        clients = make_stub_clients()
        r = verify_entry({"citation_key": "x", "title": "T"}, clients)
        assert r["resolver_outcomes"]["arxiv"]["status"] == "skipped"
        assert clients["arxiv"].calls == []

    def test_outage_is_unreachable_not_unmatched(self):
        clients = make_stub_clients(
            crossref=StubIndexClient(raise_exc=CrossrefUnavailable()))
        r = verify_entry({"citation_key": "x", "title": "T"}, clients)
        assert r["resolver_outcomes"]["crossref"]["status"] == "unreachable"

    def test_fuzzy_title_match_rejected_at_strict_bar(self):
        # Regression: "Quantum Attention Fields" fuzzy-matched a real book
        # "Quantum Fields" at the clients' 0.70 bar and got verified.
        class FuzzyStub(StubIndexClient):
            def title_search(self, title):
                return {"title": ["Quantum Fields"]}  # 0.74 similarity

        clients = make_stub_clients(crossref=FuzzyStub())
        r = verify_entry(
            {"citation_key": "fake", "title": "Quantum Attention Fields",
             "doi": "10.9999/nope"},
            clients)
        assert r["lookup_verified"] == "false"

    def test_empty_record_title_is_not_fabrication_evidence(self):
        # Regression: Crossref/OpenAlex hold an EMPTY title for some real
        # papers (ACL Anthology deposits) — the resolved DOI must verify.
        from research_harness.citation_gate.crossref_client import (
            CrossrefClient,
        )
        from research_harness.citation_gate.openalex_client import (
            OpenAlexClient,
        )
        cr = CrossrefClient()
        cr._get = lambda path, query: {"message": {"title": [""]}}
        assert cr.doi_lookup_with_title_check("10.1/x", "Real Title") \
            is not None
        oa = OpenAlexClient()
        oa._get = lambda path, query: {"title": "", "id": "W1"}
        assert oa.doi_lookup_with_title_check("10.1/x", "Real Title") \
            is not None
        # ...but a true 404 still misses.
        oa._get = lambda path, query: {}
        assert oa.doi_lookup_with_title_check("10.1/x", "Real Title") is None


# ── cache behavior ───────────────────────────────────────────────────

class TestCache:
    def test_second_run_skips_network(self, tmp_path):
        cache = VerificationCache(str(tmp_path / "c.db"))
        entry = {"citation_key": "k", "title": "T", "doi": "10.1/x"}
        c1 = make_stub_clients(crossref=StubIndexClient(id_hit=True))
        verify_entry(entry, c1, cache=cache)
        c2 = make_stub_clients(crossref=StubIndexClient(id_hit=True))
        r2 = verify_entry(entry, c2, cache=cache)
        assert r2["lookup_verified"] == "true"
        assert c2["crossref"].calls == []  # served from cache

    def test_title_fallback_not_cached_under_id_key(self, tmp_path):
        # A title-keyed attempt and an id-keyed attempt must not share a
        # cache row: the query_form encodes both inputs.
        cache = VerificationCache(str(tmp_path / "c.db"))
        no_id = {"citation_key": "k", "title": "T"}
        with_id = {"citation_key": "k", "title": "T", "doi": "10.1/x"}
        c1 = make_stub_clients(crossref=StubIndexClient(title_hit=True))
        verify_entry(no_id, c1, cache=cache)
        c2 = make_stub_clients(crossref=StubIndexClient())
        verify_entry(with_id, c2, cache=cache)
        assert c2["crossref"].calls != []  # id form was a cache MISS


# ── bib parsing ──────────────────────────────────────────────────────

BIB = r"""
@comment{ignore me}
@article{vaswani2017,
  title   = {Attention Is All You Need},
  author  = {Vaswani, Ashish and others},
  year    = {2017},
  eprint  = {1706.03762},
  archivePrefix = {arXiv},
}
@inproceedings{fake2023,
  title = {Quantum {Attention} Fields},
  year  = {2023},
  doi   = {10.9999/fake.99},
}
@misc{notitle2024,
  year = {2024},
}
"""


class TestBibParse:
    def test_parse(self, tmp_path):
        p = tmp_path / "refs.bib"
        p.write_text(BIB, encoding="utf-8")
        entries, problems = parse_bib(str(p))
        assert len(entries) == 2
        v = next(e for e in entries if e["citation_key"] == "vaswani2017")
        assert v["title"] == "Attention Is All You Need"
        assert v["arxiv_id"] == "1706.03762"
        assert v["year"] == 2017
        f = next(e for e in entries if e["citation_key"] == "fake2023")
        assert f["doi"] == "10.9999/fake.99"
        assert f["title"] == "Quantum Attention Fields"
        assert any("notitle2024" in p for p in problems)


# ── end-to-end over a bib with stub clients ──────────────────────────

class TestVerifyBib:
    def test_report_written_and_fabricated_flagged(self, tmp_path):
        p = tmp_path / "refs.bib"
        p.write_text(BIB, encoding="utf-8")

        class RoutingStub(StubIndexClient):
            def doi_lookup_with_title_check(self, doi, title):
                return {"m": 1} if doi.startswith("10.1") else None

            def arxiv_id_lookup(self, arxiv_id, title):
                return {"m": 1} if arxiv_id == "1706.03762" else None

            def title_search(self, title):
                return None

        clients = make_stub_clients(
            crossref=RoutingStub(), openalex=RoutingStub(),
            arxiv=RoutingStub())
        summary = verify_bib(str(p), use_cache=False, clients=clients)
        assert summary["total"] == 2
        assert summary["true"] == ["vaswani2017"]
        assert summary["false"] == ["fake2023"]
        assert os.path.exists(summary["report_path"])
        report = open(summary["report_path"], encoding="utf-8").read()
        assert "fake2023" in report and "FABRICATED" in report
