"""Citation-context lint for LaTeX sources.

Original code (this repository; the directory as a whole is distributed
under CC BY-NC 4.0 — see LICENSE). A lightweight descendant of the failure
classes in ARS's three-layer citation lint
(scripts/check_v3_7_3_three_layer_citation.py) — citations whose anchoring
prose does not discriminate or support them — re-expressed as three simple
LaTeX checks; no ARS code is reused:

  (a) bare citation dumps — >= 4 keys in one \\cite command with no
      discriminating prose around (no "e.g.", "such as", ... cue);
  (b) citation-as-noun misuse — a parenthetical citation used as the
      sentence subject ("\\cite{x} proposed ...") where \\citet belongs;
  (c) cargo-cult cites — a strong claim verb (proved / demonstrated /
      established) plus a citation in a sentence with fewer than 6
      content words, i.e. the claim itself is never stated.

Zero-config entry points::

    from research_harness.writing_lint import check_citations, citation_context_check
    findings = check_citations("paper/main.tex")     # or a LaTeX string
    print(citation_context_check("paper/"))          # scans *.tex, writes report
"""
from __future__ import annotations

import re

from research_harness.writing_lint._files import load_source, run_scan
from research_harness.writing_lint._latex import split_sentences, strip_noise

__all__ = ["check_citations", "citation_context_check"]

# Any \cite-family command, capturing the key list.
RE_CITE_ANY = re.compile(
    r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\s*\{([^}]*)\}"
)

# (a) Bare dump: this many keys in one command needs discriminating prose.
DUMP_THRESHOLD = 4
_ENUM_CUES = (
    "e.g.", "such as", "including", "among others", "inter alia",
    "see ", "respectively", "survey",
)

# (b) Parenthetical citation forms only — \citet/\textcite are the fix,
# so they must not match here.
_PAREN_CITE = (
    r"\\(?:cite|citep|citealp|citealt|parencite|autocite|footcite)\*?"
    r"(?:\[[^\]]*\])*\s*\{[^}]*\}"
)
_VERBS_AFTER = (
    "propose", "proposes", "proposed", "show", "shows", "showed",
    "demonstrate", "demonstrates", "demonstrated", "introduce",
    "introduces", "introduced", "argue", "argues", "argued",
    "find", "finds", "found", "develop", "develops", "developed",
    "present", "presents", "presented", "suggest", "suggests",
    "suggested", "observe", "observes", "observed", "report",
    "reports", "reported", "establish", "establishes", "established",
    "prove", "proves", "proved", "extend", "extends", "extended",
    "study", "studies", "studied", "investigate", "investigates",
    "investigated",
)
RE_NOUN_MISUSE = re.compile(
    _PAREN_CITE + r"\s+(" + "|".join(_VERBS_AFTER) + r")\b",
    re.IGNORECASE,
)

# (c) Cargo-cult cites: strong claim verb + citation + thin sentence.
MIN_CONTENT_WORDS = 6
_STRONG_VERBS = frozenset({
    "prove", "proves", "proved",
    "demonstrate", "demonstrates", "demonstrated",
    "establish", "establishes", "established",
})
_STOPWORDS = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "it", "its",
    "is", "are", "was", "were", "be", "been", "being", "has", "have",
    "had", "do", "does", "did", "can", "could", "may", "might", "will",
    "would", "should", "of", "in", "on", "to", "for", "by", "with",
    "as", "at", "from", "and", "or", "but", "not", "no", "we", "our",
    "they", "their", "he", "she", "which", "who", "whom", "what",
    "when", "where", "while", "than", "then", "there", "here", "also",
    "et", "al", "very",
})
_RE_WORD = re.compile(r"[A-Za-z][A-Za-z-]*")
_RE_GENERIC_CMD = re.compile(
    r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])*(?:\s*\{[^{}]*\})*"
)


def _content_word_count(sentence: str) -> int:
    """Count substantive words: cite commands, other LaTeX commands, and
    stopwords excluded."""
    s = RE_CITE_ANY.sub(" ", sentence)
    s = _RE_GENERIC_CMD.sub(" ", s)
    return sum(1 for w in _RE_WORD.findall(s)
               if w.lower() not in _STOPWORDS)


def check_citations(path_or_text: str) -> list[dict]:
    """Run the citation-context lint over a .tex file or LaTeX string.

    Returns a list of findings, each ``{"line", "sentence", "reason"}``,
    mirroring uncited_assertions.check_tex.
    """
    text = load_source(path_or_text)
    findings: list[dict] = []
    for line, sentence in split_sentences(strip_noise(text)):
        lowered = sentence.lower()

        # (a) bare citation dumps
        for m in RE_CITE_ANY.finditer(sentence):
            keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
            if (len(keys) >= DUMP_THRESHOLD
                    and not any(c in lowered for c in _ENUM_CUES)):
                findings.append({
                    "line": line,
                    "sentence": sentence,
                    "reason": (f"bare citation dump: {len(keys)} keys in one "
                               "cite command with no discriminating prose — "
                               "split it up and say what each work "
                               "contributes"),
                })

        # (b) citation-as-noun misuse
        for m in RE_NOUN_MISUSE.finditer(sentence):
            findings.append({
                "line": line,
                "sentence": sentence,
                "reason": (f"citation-as-noun: parenthetical citation used "
                           f"as the subject of '{m.group(1)}' — use \\citet "
                           "(textual citation) instead"),
            })

        # (c) cargo-cult cites
        if RE_CITE_ANY.search(sentence):
            strong = [w for w in _RE_WORD.findall(lowered)
                      if w in _STRONG_VERBS]
            if strong:
                n = _content_word_count(sentence)
                if n < MIN_CONTENT_WORDS:
                    findings.append({
                        "line": line,
                        "sentence": sentence,
                        "reason": (f"cargo-cult citation: strong claim verb "
                                   f"'{strong[0]}' with only {n} content "
                                   "word(s) — state what the cited work "
                                   "actually showed"),
                    })
    return findings


def citation_context_check(paper_dir: str) -> str:
    """Lint how citations sit in the prose of LaTeX sources — flags bare citation dumps (4+ keys in one \\cite with no discriminating prose), \\cite-as-noun misuse ("\\cite{x} proposed" where \\citet belongs), and cargo-cult cites (strong claim verb but almost no content words) — deterministic, no LLM; writes citation_context_report.md next to the sources.

    Args:
        paper_dir: Directory containing .tex sources (scanned recursively), or a single .tex file.

    Returns:
        Summary string with the finding count and report path.
    """
    return run_scan(
        paper_dir, check_citations, "citation_context_report.md",
        "Citation context report",
        "citation-context issue(s)",
    )
