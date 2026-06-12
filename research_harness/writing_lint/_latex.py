"""LaTeX preprocessing shared by the writing_lint checks.

Original code (this repository; the directory as a whole is distributed
under CC BY-NC 4.0 — see LICENSE). Strips comments, math, and non-prose
environments while preserving newlines — so finding line numbers map back
to the source file — then splits the remaining prose into sentences.
"""
from __future__ import annotations

import re

__all__ = ["strip_noise", "split_sentences"]

# Environments whose body is not prose — numbers inside are math symbols,
# table cells, or code, never quantitative claims in running text.
_NON_PROSE_ENVS = (
    "equation", "align", "alignat", "eqnarray", "gather", "multline",
    "math", "displaymath", "tabular", "tabularx", "longtable", "array",
    "verbatim", "lstlisting", "minted", "algorithmic", "algorithm",
    "tikzpicture",
)

_RE_COMMENT = re.compile(r"(?<!\\)%[^\n]*")
_RE_ENV = re.compile(
    r"\\begin\{(" + "|".join(re.escape(e) for e in _NON_PROSE_ENVS) + r")\*?\}"
    r".*?\\end\{\1\*?\}",
    re.DOTALL,
)
_RE_DISPLAY_MATH = re.compile(r"\\\[.*?\\\]|\$\$.*?\$\$", re.DOTALL)
_RE_INLINE_MATH = re.compile(r"\\\(.*?\\\)|(?<!\\)\$[^$]*\$", re.DOTALL)

# Dots in these never end a sentence; protected before splitting.
_ABBREVIATIONS = (
    "e.g.", "i.e.", "et al.", "etc.", "cf.", "vs.", "viz.", "resp.",
    "w.r.t.", "Fig.", "fig.", "Figs.", "figs.", "Tab.", "tab.",
    "Eq.", "eq.", "Eqs.", "eqs.", "Sec.", "sec.", "Secs.", "No.",
    "approx.", "Dr.", "Prof.",
)


def _blank_keep_newlines(match: re.Match) -> str:
    """Replace a matched span with its newlines so line numbers stay stable."""
    return "".join(ch for ch in match.group(0) if ch == "\n") or " "


def strip_noise(text: str) -> str:
    """Remove LaTeX comments / math / non-prose environments; keep newlines."""
    text = _RE_COMMENT.sub("", text)
    text = _RE_ENV.sub(_blank_keep_newlines, text)
    text = _RE_DISPLAY_MATH.sub(_blank_keep_newlines, text)
    text = _RE_INLINE_MATH.sub(_blank_keep_newlines, text)
    return text.replace("~", " ")  # ties: Table~2 -> Table 2


def split_sentences(text: str) -> list[tuple[int, str]]:
    """Split prose into sentences; return (line_number, sentence) pairs.

    Boundaries are `.` / `!` / `?` followed by whitespace (with common
    abbreviations protected) plus blank lines. Each sentence is
    whitespace-collapsed; the line number is where the sentence starts.
    """
    protected = text
    for ab in _ABBREVIATIONS:
        protected = protected.replace(ab, ab.replace(".", "\x00"))
    ends = sorted(
        {m.end() for m in re.finditer(r"[.!?](?=\s|$)", protected)}
        | {m.end() for m in re.finditer(r"\n[ \t]*\n", protected)}
    )
    sentences: list[tuple[int, str]] = []
    pos = 0
    for end in ends + [len(protected)]:
        if end <= pos:
            continue
        chunk = protected[pos:end]
        stripped = chunk.strip()
        if stripped:
            lead = len(chunk) - len(chunk.lstrip())
            line = protected.count("\n", 0, pos + lead) + 1
            sentence = re.sub(r"\s+", " ", stripped).replace("\x00", ".")
            sentences.append((line, sentence))
        pos = end
    return sentences
