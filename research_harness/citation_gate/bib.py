"""Minimal BibTeX parser: extract what the citation gate needs.

Not a general BibTeX implementation — pulls citation_key, title, year, doi
and arxiv_id out of each entry with brace-aware field scanning. Entries it
cannot parse are reported, never silently dropped.
"""

from __future__ import annotations

import re
from pathlib import Path

_ENTRY_HEAD = re.compile(
    r"@(?P<type>[a-zA-Z]+)\s*\{\s*(?P<key>[^,\s}]+)\s*,", re.MULTILINE
)
_SKIP_TYPES = {"comment", "string", "preamble"}

# arXiv id forms: 2305.12345(v2) or legacy cs.CL/0301012
_ARXIV_ID = re.compile(
    r"(?:arxiv[:.\s/]*(?:abs/)?|^)(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})",
    re.IGNORECASE,
)
_DOI_ARXIV = re.compile(r"10\.48550/arxiv\.(\S+)", re.IGNORECASE)


def _entry_body(text: str, start: int) -> tuple[str, int]:
    """Return (body, end_index) of the brace-balanced entry starting at the
    '{' at `start`."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
    return text[start + 1:], len(text)


def _fields(body: str) -> dict[str, str]:
    """Scan `name = {value}` / `name = "value"` / `name = bare` fields."""
    out: dict[str, str] = {}
    i = 0
    n = len(body)
    field_pat = re.compile(r"([a-zA-Z][\w\-]*)\s*=\s*")
    while i < n:
        m = field_pat.search(body, i)
        if not m:
            break
        name = m.group(1).lower()
        j = m.end()
        if j < n and body[j] == "{":
            depth = 0
            k = j
            while k < n:
                if body[k] == "{":
                    depth += 1
                elif body[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            out[name] = body[j + 1:k]
            i = k + 1
        elif j < n and body[j] == '"':
            k = body.find('"', j + 1)
            k = k if k != -1 else n
            out[name] = body[j + 1:k]
            i = k + 1
        else:
            k = body.find(",", j)
            k = k if k != -1 else n
            out[name] = body[j:k].strip()
            i = k + 1
    return out


def _clean(value: str) -> str:
    """Strip protective braces, collapse whitespace, drop LaTeX commands."""
    value = re.sub(r"[{}]", "", value)
    value = re.sub(r"\\[a-zA-Z]+\s*", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_arxiv_id(fields: dict[str, str]) -> str | None:
    eprint = fields.get("eprint", "").strip()
    if eprint and "arxiv" in fields.get("archiveprefix", "").lower():
        return _clean(eprint)
    if eprint and re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", eprint):
        return eprint
    doi = fields.get("doi", "")
    m = _DOI_ARXIV.search(doi)
    if m:
        return m.group(1)
    for probe in (fields.get("url", ""), fields.get("note", ""),
                  fields.get("journal", ""), fields.get("howpublished", "")):
        m = _ARXIV_ID.search(probe)
        if m:
            return m.group(1)
    return None


def parse_bib(bib_path: str) -> tuple[list[dict], list[str]]:
    """Parse a .bib file into gate entries.

    Returns (entries, problems): entries are dicts with citation_key, title,
    year, doi, arxiv_id; problems are human-readable strings for entries the
    parser could not use (e.g. missing title).
    """
    text = Path(bib_path).read_text(encoding="utf-8", errors="replace")
    entries: list[dict] = []
    problems: list[str] = []
    for m in _ENTRY_HEAD.finditer(text):
        if m.group("type").lower() in _SKIP_TYPES:
            continue
        brace = text.index("{", m.start())
        body, _ = _entry_body(text, brace)
        # body re-includes "key," — strip up to first comma
        body = body.split(",", 1)[1] if "," in body else ""
        fields = _fields(body)
        key = m.group("key")
        title = _clean(fields.get("title", ""))
        if not title:
            problems.append(f"{key}: no title field — skipped")
            continue
        doi = _clean(fields.get("doi", "")) or None
        if doi and doi.lower().startswith("https://doi.org/"):
            doi = doi[16:]
        year = None
        ym = re.search(r"\d{4}", fields.get("year", ""))
        if ym:
            year = int(ym.group(0))
        entries.append({
            "citation_key": key,
            "title": title,
            "year": year,
            "doi": doi,
            "arxiv_id": _extract_arxiv_id(fields),
        })
    return entries, problems
