"""Tests for research_harness.registry — stages, entries, lazy loading, builders."""

import pytest

from research_harness.registry import (
    STAGES, AUTO_PARAMS,
    get_function, get_signature, get_user_params, get_stage,
    all_names, stage_functions,
    build_stage_list, build_stage_functions, build_function_list,
)


class TestStages:
    """STAGES dict is well-formed."""

    def test_stages_is_dict(self):
        assert isinstance(STAGES, dict)

    def test_known_stages_present(self):
        for name in ["literature", "idea", "experiment", "writing", "review",
                      "rebuttal", "presentation", "theory", "knowledge", "project"]:
            assert name in STAGES, f"Missing stage: {name}"

    def test_descriptions_are_nonempty_strings(self):
        for name, desc in STAGES.items():
            assert isinstance(desc, str) and len(desc) > 5, f"Bad desc for {name}"


class TestEntries:
    """Every registered entry resolves correctly."""

    def test_all_names_nonempty(self):
        names = all_names()
        assert len(names) > 30  # we have ~45 functions

    def test_every_name_has_stage(self):
        for name in all_names():
            stage = get_stage(name)
            assert stage is not None, f"{name} has no stage"
            assert stage in STAGES, f"{name} maps to unknown stage '{stage}'"

    def test_every_name_resolves(self):
        for name in all_names():
            func = get_function(name)
            assert callable(func), f"{name} did not resolve to callable"

    def test_unknown_name_returns_none(self):
        assert get_function("nonexistent_xyz") is None
        assert get_stage("nonexistent_xyz") is None


class TestStageFunctions:
    """stage_functions() returns correct membership."""

    def test_literature_has_survey(self):
        names = stage_functions("literature")
        assert "survey_topic" in names
        assert "search_arxiv" in names

    def test_literature_has_orchestrator(self):
        names = stage_functions("literature")
        assert "run_literature" in names

    def test_idea_has_orchestrator(self):
        names = stage_functions("idea")
        assert "run_idea" in names

    def test_experiment_has_orchestrator(self):
        names = stage_functions("experiment")
        assert "run_experiments" in names

    def test_review_has_orchestrators(self):
        names = stage_functions("review")
        assert "review_loop" in names
        assert "paper_improvement_loop" in names

    def test_writing_has_polish(self):
        names = stage_functions("writing")
        assert "polish_rigorous" in names
        assert "translate_zh2en" in names

    def test_empty_stage(self):
        assert stage_functions("nonexistent_stage") == []

    def test_all_functions_covered(self):
        """Every registered function appears in exactly one stage."""
        covered = set()
        for stage in STAGES:
            covered.update(stage_functions(stage))
        assert covered == set(all_names())


class TestAutoParams:
    """AUTO_PARAMS are stripped from signatures."""

    def test_auto_params_set(self):
        assert "runtime" in AUTO_PARAMS

    def test_signature_hides_runtime(self):
        sig = get_signature("survey_topic")
        assert "runtime" not in sig
        assert "topic" in sig

    def test_get_user_params_excludes_runtime(self):
        func = get_function("survey_topic")
        params = get_user_params(func)
        assert "runtime" not in params
        assert "topic" in params


class TestBuilders:
    """build_stage_list / build_stage_functions / build_function_list."""

    def test_stage_list_mentions_all_stages(self):
        text = build_stage_list()
        for stage in STAGES:
            assert stage in text

    def test_stage_list_has_counts(self):
        text = build_stage_list()
        # e.g. "literature (5 functions)"
        assert "functions)" in text

    def test_stage_functions_for_writing(self):
        text = build_stage_functions("writing")
        assert "[writing]" in text
        assert "polish_rigorous" in text

    def test_stage_functions_unknown(self):
        text = build_stage_functions("nonexistent")
        assert "no functions" in text

    def test_function_list_grouped(self):
        text = build_function_list()
        # Should have stage headers
        assert "[literature]" in text
        assert "[writing]" in text
        # Should list functions
        assert "survey_topic" in text
