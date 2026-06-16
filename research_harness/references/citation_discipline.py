"""Citation discipline and hallucination prevention — reference document."""

CITATION_DISCIPLINE = r"""
# Citation Discipline and Hallucination Prevention

## Core Principle

**Never generate citations from memory, but never leave scaffolding in the
paper either.** Two non-negotiables that work together:
  1. Do not fabricate a citation (real author + fake title, real arXiv id +
     wrong venue, etc.). Cite only papers you have verified.
  2. The finished paper must read as camera-ready — NO `[VERIFY]` comments,
     NO `\cite{PLACEHOLDER_...}` keys, NO "citation pending" notes left in
     the body.

When a claim needs a citation: VERIFY it first (you have search tools), then
cite the real key. If you cannot verify a citation for a specific claim,
REWRITE the sentence so it stands on its own without that citation (state it
as the paper's own reasoning, or drop the unsupported specific) — do NOT keep
the claim with a placeholder. "Verify and cite" or "rephrase to not need it"
— never "leave a marker".

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

## When verification fails

Do NOT leave a marker in the paper. Either:
  - find a different, verifiable source for the same point, or
  - rewrite the sentence so it no longer depends on an external citation
    (present it as the paper's own argument, or remove the unverifiable
    specific claim).
The body must never contain `[VERIFY]` or `PLACEHOLDER` — those are working
notes, not paper content.

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
- [ ] Unverifiable claims rewritten to not need a citation (NOT left as a marker)
""".strip()
