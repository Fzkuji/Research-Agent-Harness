"""Venue-specific submission checklists — reference document."""

VENUE_CHECKLISTS = r"""
# Venue Checklists

## Universal Requirements

- Anonymous submission (unless camera-ready or IEEE)
- References and appendices outside main page budget (ML venues)
- Enough experimental detail for reproduction
- Honest limitations and scope boundaries
- Clear mapping from claims to evidence

## NeurIPS

- Paper checklist is MANDATORY
- Claims must align with actual evidence
- Discuss limitations honestly
- Document: reproducibility details, hyperparameters, data access, compute
- Statistical reporting: error bars, number of runs, uncertainty method
- Theory papers: assumptions and full proofs in main paper or appendix
- Page limit: 9 pages (body), references/appendix unlimited

## ICML

- Broader Impact statement REQUIRED
- Strong reproducibility expectations: splits, hyperparameters, search ranges, compute
- Statistical reporting: specify std dev vs std error vs confidence intervals
- Strict anonymization: no author names, acknowledgments, grant IDs, self-identifying repos
- Page limit: 8 pages (body), references/appendix unlimited

## ICLR

- Reproducibility and ethics statements recommended
- LLM disclosure if materially contributed to ideation/writing
- Story must be front-loaded — reviewers judge quickly from early pages
- Include code/data availability and limitations discussion
- Page limit: 9 pages (body), references/appendix unlimited

## CVPR

- Supplementary material must be self-contained
- Figure quality requirements strict (vector preferred)
- Page limit: 8 pages (body + references), supplementary separate

## ACL

- Ethics statement required
- Limitations section required
- Page limit: 8 pages (body), references/appendix unlimited

## AAAI

- Page limit: 7 pages (body), +1 page references, +2 pages appendix
- Ethics/broader impact discussion expected

## IEEE Journal (Transactions / Letters)

- NOT anonymous — include full author names, affiliations, IEEE membership
- Use \documentclass[journal]{IEEEtran} with \cite{} (numeric, NOT natbib)
- References COUNT toward page limit (Transactions: 12-14pp, Letters: 4-5pp)
- Include \begin{IEEEkeywords} after abstract
- Use IEEEtran.bst bibliography style
- Camera-ready may need \begin{IEEEbiography} per author
- No \citep or \citet — IEEE uses \cite{} only

## IEEE Conference (ICC, GLOBECOM, INFOCOM, ICASSP)

- Usually NOT anonymous (except IEEE S&P)
- Use \documentclass[conference]{IEEEtran} with \cite{}
- References COUNT toward page limit (typically 5-6pp, INFOCOM up to 8pp)
- Include \begin{IEEEkeywords} after abstract
- No author biographies in conference papers
- Use IEEEtran.bst, no \citep/\citet

## Minimal Pre-Submission Checklist

- [ ] Venue-specific required sections present
- [ ] Page budget satisfied for main body
- [ ] Contribution bullets do not overclaim
- [ ] Citations, figures, tables internally consistent
- [ ] PDF anonymized and reviewer-ready
""".strip()
