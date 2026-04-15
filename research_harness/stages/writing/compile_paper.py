from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def compile_paper(paper_dir: str, runtime: Runtime) -> str:
    """Compile LaTeX paper to PDF, fix errors, and verify output.

    You have full access to run shell commands.

    Workflow:
    1. Verify prerequisites: check pdflatex, latexmk, bibtex are installed.
       If not: macOS -> brew install --cask mactex-no-gui,
       Ubuntu -> sudo apt-get install texlive-full,
       Server -> conda install -c conda-forge texlive-core.
       Verify main.tex, references.bib, sections/*.tex, figures/ exist.

    2. First compilation attempt:
       cd $PAPER_DIR && latexmk -C && latexmk -pdf -interaction=nonstopmode
       -halt-on-error main.tex 2>&1 | tee compile.log

    3. Error diagnosis and auto-fix (up to 3 attempts):
       - Missing packages: install via tlmgr or remove unused \\\\usepackage
       - Undefined references: check \\\\label exists in correct environment
       - Missing figures: check extension (.png vs .pdf), update \\\\includegraphics path
       - Citation undefined: add entry to references.bib or fix citation key
       - [VERIFY] markers: search for correct info or flag to user
       - Overfull hbox: minor if <20pt, rephrase if severe
       - BibTeX syntax errors: fix missing comma, unmatched braces, special chars
       - \\\\crefname undefined: add after \\\\newtheorem in preamble

    4. Post-compilation checks:
       - PDF exists and is > 100KB
       - No "??" in output (undefined references)
       - No "[?]" in output (undefined citations)
       - Figures are rendered (not placeholders)
       - Check for orphaned section files not referenced by main.tex

    5. Page count verification (CRITICAL):
       ML conferences (ICLR/NeurIPS/ICML/CVPR/ACL/AAAI): main body = first page
       through end of Conclusion. References and appendix NOT counted.
       Page limits: NeurIPS=9, ICML=8, ICLR=9, AAAI=7, ACL=8.
       IEEE venues: references ARE included in page count.
       IEEE journal ~12-14 pages, IEEE conference ~5-8 pages (all inclusive).
       If over limit: identify longest sections, suggest specific cuts
       (move proofs to appendix, compress tables, tighten writing).

    6. Detect CJK text: if paper contains Chinese/Japanese/Korean, switch
       engine to xelatex.

    Output: Compilation result (success/failure, page count, warnings,
    undefined references/citations count, overfull hbox count).
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Paper directory: {paper_dir}"},
    ])
