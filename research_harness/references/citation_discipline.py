"""Citation discipline and hallucination prevention — reference document."""

CITATION_DISCIPLINE = r"""
# Citation Discipline and Hallucination Prevention

## Core Principle

**Never generate citations from memory.** If a citation cannot be verified
programmatically, mark it as [VERIFY] — do not fabricate BibTeX.

## Typical Hallucination Patterns

- Real authors + fake title
- Real title + wrong year
- Real arXiv ID + wrong venue
- Preprint and published version silently merged

## Verification Workflow (5 Steps)

1. SEARCH — find candidates via DBLP / Semantic Scholar / arXiv
2. VERIFY — confirm in at least 2 trustworthy sources
3. RETRIEVE — get BibTeX programmatically (DBLP .bib or DOI negotiation)
4. VALIDATE — confirm the cited paper actually supports your claim
5. ADD — add to .bib with clean keys and formatting

## Source Priority

| Source | Best Use |
|--------|----------|
| DBLP | CS/ML conference papers, BibTeX retrieval |
| CrossRef | DOI lookup, BibTeX content negotiation |
| Semantic Scholar | Paper search, citation graph, abstracts |
| arXiv | Preprint lookup |

## BibTeX Retrieval

DBLP:
    curl -s "https://dblp.org/search/publ/api?q=TITLE+AUTHOR&format=json&h=3"
    curl -s "https://dblp.org/rec/{key}.bib"

CrossRef/DOI:
    curl -sLH "Accept: application/x-bibtex" "https://doi.org/{doi}"

## Citation Key Format

    firstauthor_year_keyword
    e.g.: vaswani_2017_attention, devlin_2019_bert

## Placeholder Policy

If verification fails, leave explicit markers:

    % [VERIFY] could not confirm DOI / venue / exact title
    \cite{PLACEHOLDER_author2024_verify}

## BibTeX Management Rules

- Keep only cited entries (no dumping ground)
- Remove duplicates — choose between preprint and published version
- Prefer published version when formal venue version exists
- If project already uses a key style, maintain consistency

## Pre-Citation Checklist

- [ ] Paper confirmed in at least 2 sources
- [ ] DOI or arXiv ID checked
- [ ] BibTeX retrieved programmatically
- [ ] Entry type correct (@inproceedings / @article / @misc)
- [ ] Author list complete
- [ ] Year and venue verified
- [ ] Cited claim actually supported by the paper
- [ ] Unresolved uncertainty marked with [VERIFY]
""".strip()
