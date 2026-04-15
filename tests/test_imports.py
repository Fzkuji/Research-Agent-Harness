"""Tests for module imports and __all__ exports.

Ensures the entire package is importable and all advertised exports exist.
"""

import importlib

import pytest


class TestPackageImports:
    """Verify all modules can be imported without errors."""

    @pytest.mark.parametrize("module", [
        "research_harness",
        "research_harness.main",
        "research_harness.pipeline",
        "research_harness.evaluate",
        "research_harness.utils",
        "research_harness.references",
        "research_harness.references.writing_principles",
        "research_harness.references.citation_discipline",
        "research_harness.references.venue_checklists",
        "research_harness.wiki.research_wiki",
        "research_harness.wiki.wiki_agent",
        "research_harness.stages.init",
        "research_harness.stages.literature",
        "research_harness.stages.idea",
        "research_harness.stages.experiment",
        "research_harness.stages.writing",
        "research_harness.stages.review",
        "research_harness.stages.submission",
        "research_harness.stages.presentation",
        "research_harness.stages.rebuttal",
        "research_harness.stages.theory",
        "research_harness.stages.meta",
    ])
    def test_import(self, module):
        importlib.import_module(module)


class TestPackageExports:
    """Verify __all__ exports resolve to real objects."""

    def test_top_level_all(self):
        import research_harness
        for name in research_harness.__all__:
            assert hasattr(research_harness, name), f"Missing export: {name}"

    def test_top_level_key_functions(self):
        from research_harness import (
            research_agent,
            agentic_research,
            research_pipeline,
            STAGES,
        )
        assert callable(research_agent)
        assert callable(agentic_research)
        assert callable(research_pipeline)
        assert isinstance(STAGES, (list, dict))

    def test_references_exports(self):
        from research_harness.references import (
            WRITING_PRINCIPLES,
            CITATION_DISCIPLINE,
            VENUE_CHECKLISTS,
        )
        assert isinstance(WRITING_PRINCIPLES, str)
        assert isinstance(CITATION_DISCIPLINE, str)
        assert isinstance(VENUE_CHECKLISTS, str)
        assert len(WRITING_PRINCIPLES) > 100
        assert len(CITATION_DISCIPLINE) > 100
        assert len(VENUE_CHECKLISTS) > 100

    def test_writing_exports(self):
        from research_harness.stages.writing import __all__ as writing_all
        import research_harness.stages.writing as writing_mod
        for name in writing_all:
            assert hasattr(writing_mod, name), f"Missing writing export: {name}"

    def test_pipeline_stages_list(self):
        from research_harness.pipeline import STAGES
        expected = [
            "init", "literature", "idea", "experiment",
            "analysis", "writing", "review", "submission",
        ]
        assert STAGES == expected


class TestAgenticFunctionDecorator:
    """Verify @agentic_function decorated functions have expected attributes."""

    def test_agentic_research_is_callable(self):
        from research_harness.main import agentic_research
        assert callable(agentic_research)

    def test_wiki_agent_is_callable(self):
        from research_harness.wiki.wiki_agent import research_wiki
        assert callable(research_wiki)
