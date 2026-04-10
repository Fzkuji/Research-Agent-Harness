"""Tests for research_harness.utils — parse_json."""

import pytest
from research_harness.utils import parse_json


class TestParseJson:
    """Test JSON extraction from various text formats."""

    def test_plain_json(self):
        result = parse_json('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_json_in_markdown_fence(self):
        text = 'Here is the result:\n```json\n{"winner": 1, "scores": [8, 6]}\n```'
        result = parse_json(text)
        assert result["winner"] == 1
        assert result["scores"] == [8, 6]

    def test_json_in_plain_fence(self):
        text = "Output:\n```\n{\"a\": 1}\n```\nDone."
        result = parse_json(text)
        assert result == {"a": 1}

    def test_json_embedded_in_text(self):
        text = 'The analysis shows {"score": 7, "pass": true} which is good.'
        result = parse_json(text)
        assert result["score"] == 7
        assert result["pass"] is True

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No valid JSON"):
            parse_json("This has no JSON at all.")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_json("")

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}, "flag": false}'
        result = parse_json(text)
        assert result["outer"]["inner"] == [1, 2, 3]
        assert result["flag"] is False

    def test_json_with_newlines(self):
        text = """```json
{
    "title": "Test Paper",
    "venue": "NeurIPS",
    "score": 8
}
```"""
        result = parse_json(text)
        assert result["title"] == "Test Paper"
        assert result["score"] == 8
