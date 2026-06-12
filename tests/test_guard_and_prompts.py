"""Tests for the ARS-port batch: skew advisory, knowledge-isolation
directive, and style profile persistence."""

from __future__ import annotations

import json
import os

from tests.conftest import MockRuntime


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ── Skew advisory fixtures ───────────────────────────────────────────

def _paper(year=None, venue="", **kw) -> dict:
    p = {"id": f"P{id(object())}", "title": "t", "annotated": True,
         "is_orphan": False, "placements": [], "year": year, "venue": venue}
    p.update(kw)
    return p


def _state(papers) -> dict:
    return {"papers": papers, "surveys": [], "framework": None,
            "audit": [], "iter": 1, "no_delta_streak": 0}


class TestSkewAdvisory:
    def test_fires_at_threshold(self):
        from research_harness.stages.literature._artifacts import (
            _skew_advisory,
        )
        # 7 of 10 papers (70%) from 2024 — exactly at threshold.
        papers = [_paper(year=2024, venue=f"V{i}") for i in range(7)]
        papers += [_paper(year=2020 + i, venue=f"W{i}") for i in range(3)]
        lines = _skew_advisory(_state(papers))
        assert any("70%" in l and "2024" in l and "year" in l
                   for l in lines)
        assert all("diversifying" in l for l in lines)

    def test_silent_below_share_threshold(self):
        from research_harness.stages.literature._artifacts import (
            _skew_advisory,
        )
        # 6 of 10 (60%) — below 70%, mixed venues, all published.
        papers = [_paper(year=2024, venue=f"V{i}") for i in range(6)]
        papers += [_paper(year=2020 + i, venue=f"W{i}") for i in range(4)]
        lines = _skew_advisory(_state(papers))
        assert not any("year" in l for l in lines)

    def test_silent_below_min_papers(self):
        from research_harness.stages.literature._artifacts import (
            _skew_advisory,
        )
        # 7 papers, all 2024 (100%) — below the 8-paper floor.
        papers = [_paper(year=2024, venue=f"V{i}") for i in range(7)]
        assert _skew_advisory(_state(papers)) == []

    def test_preprint_dimension(self):
        from research_harness.stages.literature._artifacts import (
            _skew_advisory,
        )
        papers = [_paper(year=2020 + i, venue="") for i in range(9)]
        papers.append(_paper(year=2019, venue="ICML"))
        lines = _skew_advisory(_state(papers))
        assert any("preprint" in l and "publication status" in l
                   for l in lines)

    def test_appears_in_state_summary(self):
        from research_harness.stages.literature._artifacts import (
            _build_state_summary,
        )
        papers = [_paper(year=2024, venue="") for _ in range(10)]
        summary = _build_state_summary(_state(papers))
        assert "skew:" in summary
        assert "consider diversifying search" in summary

    def test_summary_silent_without_skew(self):
        from research_harness.stages.literature._artifacts import (
            _build_state_summary,
        )
        papers = [_paper(year=2020 + i, venue=f"Venue{i}")
                  for i in range(8)]
        # All published — publication status is 100% "published"; that
        # advisory is expected. Year/venue must stay silent.
        summary = _build_state_summary(_state(papers))
        assert "(year)" not in summary
        assert "(venue family)" not in summary


# ── 3. Knowledge-isolation directive ─────────────────────────────────

class TestKnowledgeIsolation:
    def test_docstring_contains_material_gap_contract(self):
        from research_harness.stages.writing.write_section import (
            write_section,
        )
        doc = write_section.__doc__
        assert "Knowledge isolation" in doc
        assert "[MATERIAL GAP:" in doc
        assert "parametric memory" in doc


# ── 4. Style profile persistence ─────────────────────────────────────

PROFILE = {
    "avg_sentence_length_pref": "~20 words, varied",
    "hedging_style": ["suggests", "may"],
    "transition_preferences": ["However", "Yet"],
    "reporting_verbs": ["found", "argued"],
    "citation_narrative_ratio": 0.4,
    "register_notes": "moderate-formal, lean modifiers",
}


class TestStyleProfile:
    def test_build_calls_runtime(self):
        from research_harness.stages.writing.style_profile import (
            build_style_profile,
        )
        rt = MockRuntime("Saved to /tmp/style_profile.json. Lean prose.")
        out = build_style_profile("a.md, b.md", runtime=rt)
        assert "Saved to" in out
        assert len(rt.calls) == 1
        sent = rt.calls[0]["content"][0]["text"]
        assert "a.md" in sent
        assert "style_profile.json" in sent  # default path surfaced

    def test_loader_renders_voice_card(self, tmp_dir):
        from research_harness.stages.writing.style_profile import (
            load_style_profile,
        )
        path = os.path.join(tmp_dir, "style_profile.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(PROFILE, f)
        card = load_style_profile(path)
        assert "voice card" in card
        assert "suggests, may" in card
        assert "However, Yet" in card
        assert "0.4" in card

    def test_loader_handles_missing_and_broken(self, tmp_dir):
        from research_harness.stages.writing.style_profile import (
            load_style_profile,
        )
        assert load_style_profile("") == ""
        assert load_style_profile(os.path.join(tmp_dir, "none.json")) == ""
        broken = os.path.join(tmp_dir, "broken.json")
        with open(broken, "w", encoding="utf-8") as f:
            f.write("{not json")
        assert load_style_profile(broken) == ""
        empty = os.path.join(tmp_dir, "empty.json")
        with open(empty, "w", encoding="utf-8") as f:
            f.write("{}")
        assert load_style_profile(empty) == ""
