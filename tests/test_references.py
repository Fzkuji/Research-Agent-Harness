"""Tests for research_harness.references — reference document constants."""

import pytest

from research_harness.references import (
    CITATION_DISCIPLINE,
    VENUE_CHECKLISTS,
    WRITING_PRINCIPLES,
)


class TestWritingPrinciples:
    """Verify writing principles reference document."""

    def test_is_nonempty_string(self):
        assert isinstance(WRITING_PRINCIPLES, str)
        assert len(WRITING_PRINCIPLES) > 500

    def test_contains_key_topics(self):
        # Should cover core writing guidance
        text = WRITING_PRINCIPLES.lower()
        assert "abstract" in text
        assert "introduction" in text
        assert "figure" in text


class TestCitationDiscipline:
    """Verify citation discipline reference document."""

    def test_is_nonempty_string(self):
        assert isinstance(CITATION_DISCIPLINE, str)
        assert len(CITATION_DISCIPLINE) > 500

    def test_anti_hallucination(self):
        text = CITATION_DISCIPLINE.lower()
        assert "hallucin" in text or "never generate" in text.lower()

    def test_has_verification_workflow(self):
        text = CITATION_DISCIPLINE.lower()
        assert "verify" in text
        assert "dblp" in text or "semantic scholar" in text


class TestVenueChecklists:
    """Verify venue checklists reference document."""

    def test_is_nonempty_string(self):
        assert isinstance(VENUE_CHECKLISTS, str)
        assert len(VENUE_CHECKLISTS) > 500

    def test_covers_major_venues(self):
        text = VENUE_CHECKLISTS
        for venue in ["NeurIPS", "ICML", "ICLR", "CVPR", "ACL"]:
            assert venue in text, f"Missing venue: {venue}"

    def test_has_page_limits(self):
        # Should mention page limits somewhere
        text = VENUE_CHECKLISTS.lower()
        assert "page" in text
