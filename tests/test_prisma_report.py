"""Tests for the PRISMA-style flow report (pure Python over state.json).

`prisma_report` reads <output_dir>/state.json and writes
<output_dir>/synthesis/PRISMA_FLOW.md with REAL counts:
  identification (papers + surveys, search rounds from audit) →
  screening (annotated; excluded with reasons: orphan / pruned-topic /
  abstract_only) → included (placed on current framework leaves),
plus a per-topic included-count table and an honesty footer. The
ledger identity identified = included + excluded + unscreened + surveys
is checked; corrupt states produce a "ledger mismatch" warning rather
than an exception.
"""

from __future__ import annotations

import json
import os

from research_harness.stages.literature.prisma import prisma_report


# ── Fixture helpers ──────────────────────────────────────────────────

FRAMEWORK = {
    "name": "dir", "description": "", "children": [
        {"name": "a", "description": "", "children": []},
        {"name": "b", "description": "", "children": []},
    ],
}


def _pl(topic: str) -> dict:
    return {"topic_path": topic, "contribution_summary": "cs"}


def _paper(pid, *, annotated=True, is_orphan=False, tier="pdf",
           placements=None):
    return {
        "id": pid, "title": f"Paper {pid}", "annotated": annotated,
        "is_orphan": is_orphan, "tier": tier,
        "placements": placements if placements is not None else [],
    }


def _state(**over) -> dict:
    base = {
        "direction": "test direction",
        "surveys": [],
        "papers": [],
        "framework": FRAMEWORK,
        "audit": [],
        "iter": 0,
        "no_delta_streak": 0,
    }
    base.update(over)
    return base


def _write_state(d: str, state: dict) -> None:
    with open(os.path.join(d, "state.json"), "w",
              encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def _read_report(d: str) -> str:
    path = os.path.join(d, "synthesis", "PRISMA_FLOW.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _full_state() -> dict:
    """Canonical fixture: 6 papers + 2 surveys = 8 identified.

    P1, P2 included (P2 multi-placed); P3 excluded abstract_only;
    P4 excluded orphan; P5 excluded pruned-topic; P6 not yet screened.
    """
    return _state(
        surveys=[{"id": "S1", "title": "Survey One"},
                 {"id": "S2", "title": "Survey Two"}],
        papers=[
            _paper("P1", placements=[_pl("dir/a")], tier="pdf"),
            _paper("P2", placements=[_pl("dir/a"), _pl("dir/b")],
                   tier="html"),
            _paper("P3", placements=[_pl("dir/b")],
                   tier="abstract_only"),
            _paper("P4", is_orphan=True),
            _paper("P5", placements=[_pl("dir/gone")]),
            _paper("P6", annotated=False),
        ],
        audit=[
            {"iter": 1, "action": "seed_surveys", "summary": "s"},
            {"iter": 2, "action": "search_papers", "summary": "s"},
            {"iter": 3, "action": "search_papers", "summary": "s"},
            {"iter": 4, "action": "annotate_papers", "summary": "s"},
            {"iter": 5, "action": "evolve_framework", "summary": "s"},
        ],
        iter=5,
    )


# ── Missing / unreadable state ───────────────────────────────────────

class TestMissingState:
    def test_missing_state_returns_error_string(self, tmp_dir):
        out = prisma_report(tmp_dir)
        assert out.startswith("error:")
        assert "state.json" in out
        # no report written
        assert not os.path.exists(
            os.path.join(tmp_dir, "synthesis", "PRISMA_FLOW.md")
        )

    def test_unparseable_state_returns_error_string(self, tmp_dir):
        with open(os.path.join(tmp_dir, "state.json"), "w",
                  encoding="utf-8") as f:
            f.write("{not json")
        out = prisma_report(tmp_dir)
        assert out.startswith("error:")


# ── Full flow on the canonical fixture ───────────────────────────────

class TestFullFlow:
    def test_report_written_and_summary_names_path(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        out = prisma_report(tmp_dir)
        report_path = os.path.join(
            tmp_dir, "synthesis", "PRISMA_FLOW.md",
        )
        assert os.path.isfile(report_path)
        assert report_path in out

    def test_summary_headline_counts(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        out = prisma_report(tmp_dir)
        assert "identified 8" in out
        assert "papers 6 + surveys 2" in out
        assert "screened 5" in out
        assert "excluded 3" in out
        assert "included 2" in out
        assert "WARNING" not in out

    def test_identification_counts_in_report(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "Records identified: **8** (papers: 6, surveys: 2)" in md
        # search rounds derived from audit (1 seed + 2 search = 3)
        assert "seed_surveys: 1, search_papers: 2" in md
        assert "Search rounds (from the audit log): 3" in md

    def test_screening_counts_in_report(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "Records screened (LLM-annotated): **5**" in md
        assert "Records not yet screened (unannotated): 1" in md
        assert "Records excluded: **3**" in md

    def test_exclusion_reasons_with_counts(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert (
            "Orphan — annotated but never absorbed into the framework "
            "(n = 1)" in md
        )
        assert (
            "Placements dropped — topic pruned from the framework "
            "(n = 1)" in md
        )
        assert (
            "Full text not retrieved — abstract-only tier (n = 1)"
            in md
        )

    def test_included_counts_in_report(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "**2**" in md  # included papers
        assert "Surveys seeding the framework: **2**" in md

    def test_no_mismatch_warning_on_consistent_state(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "ledger mismatch" not in md

    def test_honesty_footer_present(self, tmp_dir):
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "systematic-review compliance claim" in md
        assert "duplicate" in md.lower()
        assert "double-screening" in md.lower()


# ── Per-topic table ──────────────────────────────────────────────────

class TestPerTopicTable:
    def test_table_matches_placements_of_included_papers(self, tmp_dir):
        # P1 → dir/a; P2 → dir/a + dir/b; P3 (abstract_only, excluded)
        # placed on dir/b must NOT count.
        _write_state(tmp_dir, _full_state())
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "| Topic path | Included papers |" in md
        assert "| dir/a | 2 |" in md
        assert "| dir/b | 1 |" in md

    def test_zero_count_leaf_listed(self, tmp_dir):
        state = _state(
            papers=[_paper("P1", placements=[_pl("dir/a")])],
        )
        _write_state(tmp_dir, state)
        prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "| dir/a | 1 |" in md
        assert "| dir/b | 0 |" in md

    def test_no_framework_no_table(self, tmp_dir):
        # Without a framework there are no current leaves: a placed,
        # annotated paper counts as excluded (placements dropped).
        state = _state(
            framework=None,
            papers=[_paper("P1", placements=[_pl("dir/a")])],
        )
        _write_state(tmp_dir, state)
        out = prisma_report(tmp_dir)
        md = _read_report(tmp_dir)
        assert "no framework leaves" in md
        assert (
            "Placements dropped — topic pruned from the framework "
            "(n = 1)" in md
        )
        assert "included 0" in out
        assert "WARNING" not in out  # still internally consistent


# ── Corrupted state → warning, not crash ─────────────────────────────

class TestLedgerMismatch:
    def test_orphan_without_annotation_double_counts(self, tmp_dir):
        # is_orphan=True with annotated=False lands in two buckets
        # (unscreened AND orphan) — the report must flag it instead of
        # silently re-balancing or crashing.
        state = _state(
            papers=[_paper("P_bad", annotated=False, is_orphan=True)],
        )
        _write_state(tmp_dir, state)
        out = prisma_report(tmp_dir)
        assert "WARNING: ledger mismatch" in out
        md = _read_report(tmp_dir)
        assert "ledger mismatch" in md

    def test_non_dict_paper_entry_flags_mismatch(self, tmp_dir):
        state = _state(papers=["garbage entry"])
        _write_state(tmp_dir, state)
        out = prisma_report(tmp_dir)
        assert "WARNING: ledger mismatch" in out
        assert "identified 1" in out
        md = _read_report(tmp_dir)
        assert "ledger mismatch" in md


# ── Empty / minimal state ────────────────────────────────────────────

class TestEmptyState:
    def test_empty_state_zero_counts_consistent(self, tmp_dir):
        _write_state(tmp_dir, _state(framework=None))
        out = prisma_report(tmp_dir)
        assert "identified 0" in out
        assert "WARNING" not in out
        md = _read_report(tmp_dir)
        assert "Records identified: **0** (papers: 0, surveys: 0)" in md
