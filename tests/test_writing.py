"""Tests for research_harness.stages.writing — gather_context and structure."""

import os

import pytest

from research_harness.stages.writing import (
    gather_context,
    _clean_title,
    _strip_own_header,
)


class TestLatexAssembly:
    """write_paper helpers that prevent doubled headers / junk titles."""

    def test_title_from_quoted_task_prompt(self):
        task = ('Optimize the existing paper in this project: "Deterministic '
                'Control-Flow Guardrails for Long-Horizon LLM Agents". Use the '
                'existing literature review and draft.')
        assert (_clean_title(task)
                == "Deterministic Control-Flow Guardrails for Long-Horizon LLM Agents")

    def test_title_empty_falls_back(self):
        assert _clean_title("") == "Research Paper"

    def test_title_plain_short_passthrough(self):
        assert _clean_title("A Study of Widgets") == "A Study of Widgets"

    def test_strip_doubled_section_header(self):
        body = "\\section{Introduction}\n\\section{Introduction}\n\nText here."
        out = _strip_own_header("Introduction", body)
        assert "\\section" not in out
        assert out.startswith("Text here.")

    def test_strip_clean_body_untouched(self):
        body = "Long-horizon agents fail when control compounds."
        assert _strip_own_header("Method", body) == body

    def test_strip_nested_abstract_env(self):
        body = ("\\begin{abstract}\n\\begin{abstract}\nWe study guardrails.\n"
                "\\end{abstract}\n\\end{abstract}")
        out = _strip_own_header("Abstract", body)
        assert "\\begin{abstract}" not in out
        assert "\\end{abstract}" not in out
        assert out.strip() == "We study guardrails."

    def test_strip_markdown_fences_and_header(self):
        # MiniMax-style: ```latex fence + the model's own \section + ``` close.
        # Both the fences and the duplicate header must go (else literal fences
        # break compile and the assembler's wrap doubles the heading).
        body = "```latex\n\\section{Introduction}\n\nAgents operate long.\n```"
        out = _strip_own_header("Introduction", body)
        assert "```" not in out
        assert not out.startswith("\\section")
        assert out.startswith("Agents operate long.")

    def test_strip_fences_on_abstract(self):
        body = "```latex\nWe survey memory.\n```"
        out = _strip_own_header("Abstract", body)
        assert "```" not in out
        assert out.strip() == "We survey memory."


class TestGatherContext:
    """Test context gathering from project directories."""

    def test_with_outline_and_notes(self, project_dir):
        ctx = gather_context(project_dir, "introduction")
        assert "## Outline" in ctx
        assert "Test Paper Outline" in ctx
        assert "## Notes: notes.md" in ctx
        assert "testing is important" in ctx

    def test_missing_section_dir(self, project_dir):
        ctx = gather_context(project_dir, "nonexistent_section")
        # Should still have outline
        assert "## Outline" in ctx

    def test_no_context_at_all(self, tmp_dir):
        # Empty dir with no outline or section dirs
        ctx = gather_context(tmp_dir, "introduction")
        assert ctx == "No context available yet."

    def test_skips_readme(self, project_dir):
        """README.md in section dirs should be skipped."""
        readme_path = os.path.join(project_dir, "introduction", "README.md")
        with open(readme_path, "w") as f:
            f.write("This is a section README.")

        ctx = gather_context(project_dir, "introduction")
        assert "This is a section README" not in ctx

    def test_multiple_notes_files(self, project_dir):
        """Multiple files in section dir should all be included."""
        with open(os.path.join(project_dir, "method", "design_v1.md"), "w") as f:
            f.write("First design iteration")
        with open(os.path.join(project_dir, "method", "design_v2.md"), "w") as f:
            f.write("Second design iteration")

        ctx = gather_context(project_dir, "method")
        assert "First design iteration" in ctx
        assert "Second design iteration" in ctx

    def test_outline_truncated(self, project_dir):
        """Very long outlines should be truncated to 3000 chars."""
        outline_path = os.path.join(project_dir, "outline", "outline.md")
        with open(outline_path, "w") as f:
            f.write("X" * 5000)

        ctx = gather_context(project_dir, "introduction")
        # The outline portion should be at most 3000 chars
        # (plus the "## Outline\n" header)
        outline_section = ctx.split("## Notes")[0] if "## Notes" in ctx else ctx
        assert len(outline_section) < 3100

    def test_handles_binary_files(self, project_dir):
        """Binary files in section dirs should be skipped gracefully."""
        bin_path = os.path.join(project_dir, "experiments", "data.bin")
        with open(bin_path, "wb") as f:
            f.write(bytes(range(256)))

        # Should not raise
        ctx = gather_context(project_dir, "experiments")
        assert isinstance(ctx, str)
