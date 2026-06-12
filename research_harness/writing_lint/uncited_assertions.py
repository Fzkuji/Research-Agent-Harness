# Adapted from academic-research-skills v3.12.0 (https://github.com/Imbad0202/academic-research-skills), (c) Cheng-I Wu, CC BY-NC 4.0
# Changes: D4-c detector + constants merged into one module; citation condition retargeted from markdown <!--ref:slug--> markers to LaTeX (\cite-family, \ref{tab:/fig:}, "Table N"); trigger set extended (outperform verbs, "improved by" phrases, p-values); hyphenated-identifier guard, LaTeX prose view, and check_tex / uncited_assertion_check entry points added — see LICENSE in this directory.
"""Uncited-assertion detector for LaTeX sources (ARS D4-c, retargeted).

A sentence becomes an uncited-assertion finding iff ALL THREE hold:

  1. A quantifier or empirical-claim token is present (percentages,
     "67 of 100", participant counts, p-values, "improved by",
     fuzzy quantifiers most/several/two-thirds, empirical verbs
     showed/demonstrated/observed/proved/confirmed/outperforms).
     Bare-number matches pass a guard that rejects years, version
     triples, section/figure/table numbers, and hyphenated identifiers
     (CIFAR-10, GPT-4).
  2. No citation marker in the sentence. In this LaTeX retargeting a
     citation marker is any \\cite-family / \\parencite command, OR an
     own-result reference: \\ref{tab:...} / \\ref{fig:...} (also
     \\autoref/\\cref) or textual "Table N" / "Figure N" — a number
     backed by the paper's own table or figure has a source.
  3. The sentence is not definitional ("refers to", "is defined as",
     "we define", "for the purposes of").

LaTeX noise (comments, math, tabular-like environments, commands) is
stripped before sentences are scanned — see _latex.py.

Zero-config entry points::

    from research_harness.writing_lint import check_tex, uncited_assertion_check
    findings = check_tex("paper/main.tex")        # or a LaTeX string
    print(uncited_assertion_check("paper/"))      # scans *.tex, writes report
"""
from __future__ import annotations

import re

from research_harness.writing_lint._files import load_source, run_scan
from research_harness.writing_lint._latex import split_sentences, strip_noise

__all__ = ["detect_uncited", "check_tex", "uncited_assertion_check"]

# ---------------------------------------------------------------------------
# D4-c constants (vendored from ARS scripts/_claim_audit_constants.py;
# trigger sets extended per the LaTeX retargeting noted in the header).
# ---------------------------------------------------------------------------

# Condition 1: empirical-claim verbs (case-insensitive whole-word match).
# ARS list: showed, demonstrated, observed, proved, confirmed.
# Harness addition: the outperform family.
UNCITED_EMPIRICAL_VERBS: frozenset[str] = frozenset({
    "showed", "demonstrated", "observed", "proved", "confirmed",
    "outperforms", "outperform", "outperformed",
})

# Condition 1: fuzzy English quantifier words (case-insensitive whole-word).
UNCITED_FUZZY_QUANTIFIERS: frozenset[str] = frozenset(
    {"most", "several", "two-thirds"}
)

# Condition 1 (harness addition): multiword empirical-claim phrases.
UNCITED_CLAIM_PHRASES: tuple[str, ...] = (
    "improved by", "improves by", "improvement of", "reduced by",
    "reduction of",
)

# Condition 1 (harness addition): p-value claims (`p < 0.05`, `p = .01`).
RE_P_VALUE = re.compile(r"\bp\s*[<>=≤≥]\s*0?\.\d+")

# Condition 1: numerical quantifier regex — match broadly, guard narrowly.
RE_NUMERIC_QUANTIFIER = re.compile(
    # Order matters: longest-prefix-first so percent and "N of M" bind
    # before the bare-number branch swallows the leading digits.
    r"\b\d+(?:\.\d+)?%"                  # percent quantifier
    r"|\b\d+(?:\.\d+)?\s+of\s+\d+\b"     # "N of M" quantifier idiom
    r"|\b\d+(?:\.\d+)*\b"                # bare number, possibly dotted
)

# Condition 1 guard regexes: reject bare-number matches whose context
# identifies them as years, version triples, or section numbers.
RE_BARE_NUMERIC_YEAR = re.compile(r"^(19|20)\d{2}$")
RE_DOTTED_TRIPLE_OR_MORE = re.compile(r"^\d+(?:\.\d+){2,}$")
RE_DOTTED_PAIR = re.compile(r"^\d+\.\d+$")
# Harness addition: equation/eq./algorithm/alg./theorem/lemma/line/page
# cues (LaTeX papers number many more own structures than markdown drafts).
RE_SECTION_CUE = re.compile(
    r"(?:section|chapter|figure|table|fig\.|figs\.|tbl\.|tab\.|step|"
    r"appendix|equation|eq\.|eqs\.|algorithm|alg\.|theorem|lemma|line|"
    r"page|§)\s*$",
    re.IGNORECASE,
)
RE_VERSION_PREFIX = re.compile(r"v\s*$", re.IGNORECASE)
RE_NUMERIC_LEFT_ATTACHED = re.compile(r"\d+\.$")

# Condition 2 (retargeted): LaTeX citation marker — \cite, \citep, \citet,
# \parencite and friends (\citealp, \textcite, \autocite, \footcite, ...).
RE_LATEX_CITE = re.compile(
    r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\s*\{[^}]+\}"
)
# Condition 2 (retargeted): own-result reference — the number has a source
# in the paper's own tables/figures. \ref-family on tab:/fig: labels, or
# textual "Table 2" / "Figure 3" / "Fig. 4" (after ~ -> space).
RE_OWN_RESULT_REF = re.compile(
    r"\\(?:ref|autoref|cref|Cref)\{(?:tab|fig|table|figure):[^}]*\}"
    r"|\b(?:Table|Figure|Fig|Tab)\.?\s*\d+",
    re.IGNORECASE,
)

# Condition 3: definitional-phrase substrings (case-insensitive).
UNCITED_DEFINITION_PHRASES: tuple[str, ...] = (
    "refers to",
    "is defined as",
    "we define",
    "for the purposes of",
)

# Whole-word splitter for condition 1 fuzzy / verb matching.
_RE_WORD = re.compile(r"[A-Za-z][A-Za-z-]*")

# Left-context window length for guard pass cue detection. 24 chars covers
# `cf. Section ` and `as shown in Figure ` while avoiding catching cue
# words from a previous clause separated by punctuation.
_GUARD_LEFT_WINDOW = 24

# Prose-view helpers (harness addition): unwrap text-formatting commands,
# then drop remaining commands with their arguments so label/length numbers
# (\label{sec:3.2}, \vspace{2mm}) cannot fire condition 1.
_RE_TEXT_CMD = re.compile(
    r"\\(?:textbf|textit|textsc|textrm|texttt|emph|underline|mbox|text)"
    r"\s*\{([^{}]*)\}"
)
_RE_GENERIC_CMD = re.compile(
    r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])*(?:\s*\{[^{}]*\})*"
)


def _prose_view(sentence: str) -> str:
    """Strip LaTeX commands from one sentence, keeping human-readable text."""
    s = sentence.replace(r"\%", "%")
    for _ in range(2):  # unwrap possibly nested formatting commands
        s = _RE_TEXT_CMD.sub(r"\1", s)
    s = _RE_GENERIC_CMD.sub(" ", s)
    return s.replace("{", " ").replace("}", " ")


def _is_year_or_version_or_section(
    sentence: str, match_text: str, match_start: int
) -> bool:
    """Guard pass: return True when a bare-number match is NOT a quantifier.

    Disqualifying shapes (see ARS D4-c for full iteration history):
      1. 4-digit year in plausible academic range (1900-2099).
      2. Dotted X.Y.Z[.W...] form — version triple OR deep section number.
      3. Bare integer OR dotted X.Y form preceded by a section cue
         (covers `Table 2`, `Section 5`, `Section 3.1`).
      3b. Dotted X.Y form preceded by `v` (version literal).
      4. Any match whose immediate left neighbour is a dotted-number
         suffix like `3.` (reattaches version/section prefixes that
         Python's \\b cannot separate, e.g. `v3.7.3`).
      5. (Harness addition) Bare number attached to a letter by a hyphen —
         identifier fragments like `CIFAR-10`, `GPT-4`, `ResNet-50`.

    Percent and `N of M` matches never reach this guard — the caller is
    responsible for routing only bare-number matches through.
    """
    if RE_BARE_NUMERIC_YEAR.match(match_text):
        return True
    if RE_DOTTED_TRIPLE_OR_MORE.match(match_text):
        return True
    left = sentence[max(0, match_start - _GUARD_LEFT_WINDOW): match_start]
    if RE_SECTION_CUE.search(left):
        return True
    if RE_DOTTED_PAIR.match(match_text) and RE_VERSION_PREFIX.search(left):
        return True
    if (match_start >= 2 and sentence[match_start - 1] == "-"
            and sentence[match_start - 2].isalpha()):
        return True
    if match_start > 0:
        # Shape (i) — immediate left `.` always reattaches.
        if sentence[match_start - 1] == ".":
            left_search_start = max(0, match_start - _GUARD_LEFT_WINDOW)
            left = sentence[left_search_start:match_start]
            if RE_NUMERIC_LEFT_ATTACHED.search(left):
                return True
        # Shape (ii) — whitespace-separated only for dotted right tails.
        elif "." in match_text and sentence[match_start - 1].isspace():
            scan_idx = match_start - 1
            while scan_idx > 0 and sentence[scan_idx].isspace():
                scan_idx -= 1
            if sentence[scan_idx] == ".":
                left_search_start = max(0, scan_idx + 1 - _GUARD_LEFT_WINDOW)
                left = sentence[left_search_start: scan_idx + 1]
                if RE_NUMERIC_LEFT_ATTACHED.search(left):
                    return True
    return False


def detect_uncited(sentence: str) -> tuple[bool, list[str]]:
    """Return `(is_candidate, trigger_tokens)` for one LaTeX prose sentence.

    Trigger tokens come back in document order with order-preserving dedup,
    matching the upstream D4-c detector contract.
    """
    # Condition 3 fires first — if the sentence is definitional we never
    # need to inspect quantifier tokens.
    lowered = sentence.lower()
    if any(phrase in lowered for phrase in UNCITED_DEFINITION_PHRASES):
        return False, []

    # Condition 2 — a LaTeX citation or an own-result reference means the
    # number/claim has a source.
    if RE_LATEX_CITE.search(sentence) or RE_OWN_RESULT_REF.search(sentence):
        return False, []

    # Condition 1 — collect every quantifier / verb match with its offset
    # so the final token list reflects document order. Matching runs on a
    # command-stripped prose view of the sentence.
    prose = _prose_view(sentence)
    matches: list[tuple[int, str]] = []
    for m in RE_NUMERIC_QUANTIFIER.finditer(prose):
        text = m.group(0)
        # Percent and `N of M` matches always pass through; only bare-
        # number matches need the year/version/section guard.
        if "%" not in text and " of " not in text:
            if _is_year_or_version_or_section(prose, text, m.start()):
                continue
        matches.append((m.start(), text))

    for m in RE_P_VALUE.finditer(prose):
        matches.append((m.start(), m.group(0)))

    prose_lower = prose.lower()
    for phrase in UNCITED_CLAIM_PHRASES:
        idx = prose_lower.find(phrase)
        if idx != -1:
            matches.append((idx, phrase))

    # Fuzzy quantifiers + empirical verbs match on lower-cased whole words.
    triggers = UNCITED_FUZZY_QUANTIFIERS | UNCITED_EMPIRICAL_VERBS
    for m in _RE_WORD.finditer(prose):
        token = m.group(0).lower()
        if token in triggers:
            matches.append((m.start(), token))

    # Sort by source offset, then dedup preserving first occurrence.
    matches.sort(key=lambda pair: pair[0])
    trigger_tokens = list(dict.fromkeys(token for _, token in matches))
    return (bool(trigger_tokens), trigger_tokens)


def check_tex(path_or_text: str) -> list[dict]:
    """Run the uncited-assertion detector over a .tex file or LaTeX string.

    Returns a list of findings, each ``{"line", "sentence", "reason"}``.
    Line numbers refer to the source file; the sentence is whitespace-
    collapsed prose after comment/math stripping.
    """
    text = load_source(path_or_text)
    findings: list[dict] = []
    for line, sentence in split_sentences(strip_noise(text)):
        is_candidate, tokens = detect_uncited(sentence)
        if is_candidate:
            findings.append({
                "line": line,
                "sentence": sentence,
                "reason": ("quantified/empirical claim without citation or "
                           "own-result reference (triggers: "
                           + ", ".join(tokens) + ")"),
            })
    return findings


def uncited_assertion_check(paper_dir: str) -> str:
    """Scan LaTeX sources for quantified or empirical claims (percentages, improvement numbers, participant counts, p-values, outperforms/showed-style verbs) that carry no citation and no own-result Table/Figure reference — deterministic lint, no LLM; writes uncited_assertions_report.md next to the sources.

    Args:
        paper_dir: Directory containing .tex sources (scanned recursively), or a single .tex file.

    Returns:
        Summary string with the finding count and report path.
    """
    return run_scan(
        paper_dir, check_tex, "uncited_assertions_report.md",
        "Uncited assertion report",
        "uncited quantified/empirical assertion(s)",
    )
