"""Tests for research_harness.stages.init — project initialization."""

import os

import pytest

from research_harness.stages.init import init_research, _sanitize_name


class TestSanitizeName:
    """Test LaTeX name sanitization."""

    def test_simple_name(self):
        assert _sanitize_name("MyProject") == "MyProject"

    def test_spaces_removed(self):
        assert _sanitize_name("LLM Uncertainty") == "LLMUncertainty"

    def test_special_chars_removed(self):
        assert _sanitize_name("Graph-Neural: v2.0") == "GraphNeuralv"

    def test_numbers_removed(self):
        # numbers are not [a-zA-Z]
        assert _sanitize_name("GPT4") == "GPT"


class TestInitResearch:
    """Test project directory initialization."""

    def test_creates_all_directories(self, tmp_dir):
        path = init_research("TestProject", base_dir=tmp_dir)

        expected_dirs = [
            "code", "outline", "introduction", "method",
            "experiments", "related_work", "paper", "references",
        ]
        for d in expected_dirs:
            assert os.path.isdir(os.path.join(path, d)), f"Missing directory: {d}"

    def test_creates_outline(self, tmp_dir):
        path = init_research("TestProject", base_dir=tmp_dir)

        outline_path = os.path.join(path, "outline", "outline.md")
        assert os.path.isfile(outline_path)
        with open(outline_path) as f:
            content = f.read()
        assert "TestProject" in content

    def test_creates_latex_scaffold(self, tmp_dir):
        path = init_research("TestProject", venue="NeurIPS", base_dir=tmp_dir)

        paper_dir = os.path.join(path, "paper")
        tex_files = [f for f in os.listdir(paper_dir) if f.endswith(".tex")]
        assert len(tex_files) >= 5  # main + intro + method + exp + related + conclusion + appendix

        bib_files = [f for f in os.listdir(paper_dir) if f.endswith(".bib")]
        assert len(bib_files) == 1

    def test_main_tex_has_inputs(self, tmp_dir):
        path = init_research("TestProject", venue="NeurIPS", base_dir=tmp_dir)

        paper_dir = os.path.join(path, "paper")
        main_tex = [f for f in os.listdir(paper_dir) if f.startswith("0")][0]
        with open(os.path.join(paper_dir, main_tex)) as f:
            content = f.read()
        assert "\\input{1Introduction}" in content
        assert "\\input{2Method}" in content
        assert "\\input{3Experiments}" in content
        assert "\\bibliography{9Reference}" in content

    def test_venue_in_latex(self, tmp_dir):
        path = init_research("TestProject", venue="ICML", base_dir=tmp_dir)

        paper_dir = os.path.join(path, "paper")
        main_tex = [f for f in os.listdir(paper_dir) if f.startswith("0")][0]
        assert "ICML" in main_tex

    def test_code_git_init(self, tmp_dir):
        path = init_research("TestProject", base_dir=tmp_dir)
        assert os.path.isdir(os.path.join(path, "code", ".git"))

    def test_section_readmes_created(self, tmp_dir):
        path = init_research("TestProject", base_dir=tmp_dir)

        for section in ["outline", "introduction", "method", "experiments", "related_work"]:
            readme = os.path.join(path, section, "README.md")
            assert os.path.isfile(readme), f"Missing README for {section}"

    def test_project_readme(self, tmp_dir):
        path = init_research("TestProject", venue="NeurIPS", base_dir=tmp_dir)

        readme = os.path.join(path, "README.md")
        assert os.path.isfile(readme)
        with open(readme) as f:
            content = f.read()
        assert "TestProject" in content
        assert "NeurIPS" in content

    def test_idempotent(self, tmp_dir):
        """Running init twice should not overwrite existing files."""
        path = init_research("TestProject", base_dir=tmp_dir)

        # Modify outline
        outline_path = os.path.join(path, "outline", "outline.md")
        with open(outline_path, "w") as f:
            f.write("Modified outline")

        # Re-init
        init_research("TestProject", base_dir=tmp_dir)

        with open(outline_path) as f:
            assert f.read() == "Modified outline"

    def test_returns_absolute_path(self, tmp_dir):
        path = init_research("TestProject", base_dir=tmp_dir)
        assert os.path.isabs(path)

    def test_bib_has_citation_discipline(self, tmp_dir):
        path = init_research("TestProject", base_dir=tmp_dir)
        bib_path = os.path.join(path, "paper", "9Reference.bib")
        with open(bib_path) as f:
            content = f.read()
        assert "NEVER generate BibTeX from LLM memory" in content
