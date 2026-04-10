"""Tests for research_harness.stages.writing — gather_context and structure."""

import os

import pytest

from research_harness.stages.writing import gather_context


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
