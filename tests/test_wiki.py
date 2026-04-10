"""Tests for research_harness.wiki.research_wiki — pure Python wiki functions."""

import json
import os

import pytest

from research_harness.wiki.research_wiki import (
    VALID_EDGE_TYPES,
    add_edge,
    append_log,
    get_stats,
    init_wiki,
    rebuild_query_pack,
    slugify,
)


class TestSlugify:
    """Test canonical slug generation."""

    def test_basic(self):
        slug = slugify("Attention Is All You Need", "Vaswani", 2017)
        # "all" and "you" are not stop words (>2 chars, not in stop list)
        assert slug == "vaswani2017_attention_all_you"

    def test_stops_words_removed(self):
        slug = slugify("A Survey of the Methods for Deep Learning", "Smith", 2024)
        # "a", "of", "the", "for" are stop words
        assert "survey" in slug
        assert "methods" in slug
        assert slug.startswith("smith2024_")

    def test_no_author(self):
        slug = slugify("Neural Architecture Search")
        assert slug.startswith("unknown0000_")
        assert "neural" in slug

    def test_special_chars_stripped(self):
        slug = slugify("LLM-based Agents: A Survey!", "Chen", 2025)
        assert slug == "chen2025_llmbased_agents_survey"

    def test_max_three_keywords(self):
        slug = slugify("One Two Three Four Five Six", "A", 2000)
        keywords = slug.split("_", 1)[1]  # after "a2000_"
        assert len(keywords.split("_")) <= 3

    def test_empty_title(self):
        slug = slugify("", "Jones", 2025)
        assert slug == "jones2025_untitled"

    def test_all_stop_words(self):
        slug = slugify("a the of in on", "X", 2020)
        assert slug == "x2020_untitled"


class TestInitWiki:
    """Test wiki directory initialization."""

    def test_creates_structure(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        result = init_wiki(wiki_root)

        assert os.path.isdir(os.path.join(wiki_root, "papers"))
        assert os.path.isdir(os.path.join(wiki_root, "ideas"))
        assert os.path.isdir(os.path.join(wiki_root, "experiments"))
        assert os.path.isdir(os.path.join(wiki_root, "claims"))
        assert os.path.isdir(os.path.join(wiki_root, "graph"))

        assert os.path.isfile(os.path.join(wiki_root, "index.md"))
        assert os.path.isfile(os.path.join(wiki_root, "log.md"))
        assert os.path.isfile(os.path.join(wiki_root, "gap_map.md"))
        assert os.path.isfile(os.path.join(wiki_root, "query_pack.md"))
        assert os.path.isfile(os.path.join(wiki_root, "graph", "edges.jsonl"))

        assert result == wiki_root

    def test_idempotent(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)
        # Write something to index.md
        with open(os.path.join(wiki_root, "index.md"), "w") as f:
            f.write("Custom content")
        # Re-init should not overwrite existing files
        init_wiki(wiki_root)
        with open(os.path.join(wiki_root, "index.md")) as f:
            assert f.read() == "Custom content"

    def test_log_has_init_entry(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)
        with open(os.path.join(wiki_root, "log.md")) as f:
            content = f.read()
        assert "Wiki initialized" in content


class TestAddEdge:
    """Test edge addition to the relationship graph."""

    def test_add_valid_edge(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        ok = add_edge(wiki_root, "paper:foo", "idea:bar", "inspired_by", "Fig 3")
        assert ok is True

        edges_path = os.path.join(wiki_root, "graph", "edges.jsonl")
        with open(edges_path) as f:
            lines = [l for l in f.readlines() if l.strip()]
        assert len(lines) == 1
        edge = json.loads(lines[0])
        assert edge["from"] == "paper:foo"
        assert edge["to"] == "idea:bar"
        assert edge["type"] == "inspired_by"
        assert edge["evidence"] == "Fig 3"
        assert "added" in edge

    def test_duplicate_rejected(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        add_edge(wiki_root, "paper:a", "paper:b", "extends")
        ok = add_edge(wiki_root, "paper:a", "paper:b", "extends")
        assert ok is False

    def test_different_type_not_duplicate(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        add_edge(wiki_root, "paper:a", "paper:b", "extends")
        ok = add_edge(wiki_root, "paper:a", "paper:b", "contradicts")
        assert ok is True

    def test_all_valid_edge_types(self):
        expected = {
            "extends", "contradicts", "addresses_gap", "inspired_by",
            "tested_by", "supports", "invalidates", "supersedes",
        }
        assert VALID_EDGE_TYPES == expected


class TestGetStats:
    """Test wiki statistics."""

    def test_empty_wiki(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        stats = get_stats(wiki_root)
        assert stats["papers"] == 0
        assert stats["ideas"] == 0
        assert stats["experiments"] == 0
        assert stats["claims"] == 0
        assert stats["edges"] == 0

    def test_with_entities(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        # Add some paper files
        with open(os.path.join(wiki_root, "papers", "vaswani2017.md"), "w") as f:
            f.write("node_id: paper:vaswani2017\ntitle: Attention Is All You Need\n")
        with open(os.path.join(wiki_root, "papers", "devlin2019.md"), "w") as f:
            f.write("node_id: paper:devlin2019\ntitle: BERT\n")

        # Add an idea
        with open(os.path.join(wiki_root, "ideas", "idea1.md"), "w") as f:
            f.write("outcome: negative\nlesson: didn't work\n")
        with open(os.path.join(wiki_root, "ideas", "idea2.md"), "w") as f:
            f.write("outcome: positive\n")

        # Add edges
        add_edge(wiki_root, "paper:vaswani2017", "idea:1", "inspired_by")
        add_edge(wiki_root, "idea:1", "exp:1", "tested_by")

        stats = get_stats(wiki_root)
        assert stats["papers"] == 2
        assert stats["ideas"] == 2
        assert stats["ideas_failed"] == 1
        assert stats["ideas_succeeded"] == 1
        assert stats["edges"] == 2


class TestAppendLog:
    """Test wiki log appending."""

    def test_append_to_existing(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        append_log(wiki_root, "Added paper X")
        append_log(wiki_root, "Ran experiment Y")

        with open(os.path.join(wiki_root, "log.md")) as f:
            content = f.read()
        assert "Added paper X" in content
        assert "Ran experiment Y" in content

    def test_creates_log_if_missing(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        os.makedirs(wiki_root, exist_ok=True)

        append_log(wiki_root, "Fresh log")
        with open(os.path.join(wiki_root, "log.md")) as f:
            content = f.read()
        assert "Fresh log" in content


class TestRebuildQueryPack:
    """Test query_pack.md generation."""

    def test_empty_wiki(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        n = rebuild_query_pack(wiki_root)
        assert n > 0
        with open(os.path.join(wiki_root, "query_pack.md")) as f:
            content = f.read()
        assert "Research Wiki Query Pack" in content

    def test_respects_max_chars(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        # Add a long gap map
        with open(os.path.join(wiki_root, "gap_map.md"), "w") as f:
            f.write("# Gap Map\n\n" + "G1: Very important gap. " * 500)

        n = rebuild_query_pack(wiki_root, max_chars=500)
        assert n <= 520  # small buffer for truncation marker

    def test_includes_papers(self, tmp_dir):
        wiki_root = os.path.join(tmp_dir, "wiki")
        init_wiki(wiki_root)

        with open(os.path.join(wiki_root, "papers", "test.md"), "w") as f:
            f.write("node_id: paper:test2025\ntitle: Test Paper\n# One-line thesis\nA test.\n")

        rebuild_query_pack(wiki_root)
        with open(os.path.join(wiki_root, "query_pack.md")) as f:
            content = f.read()
        assert "Test Paper" in content
