from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def compile_paper(paper_dir: str, runtime: Runtime) -> str:
    """Compile LaTeX paper to PDF and fix any errors.

    You have full access to run shell commands.

    Steps:
    1. Verify prerequisites: check pdflatex, latexmk, bibtex are installed.
    2. Run: latexmk -pdf -interaction=nonstopmode <main.tex>
    3. If errors occur, read the .log file, diagnose, fix the .tex files,
       and recompile (up to 3 attempts).
    4. Verify the output PDF exists and report page count.

    Common fixes:
    - Missing packages: add \\usepackage{} or install via tlmgr
    - Undefined references: run bibtex + recompile
    - Overfull hbox: adjust text or figure sizes
    - Missing figures: check paths in \\includegraphics{}

    Page limits (main body to Conclusion, excluding refs & appendix):
    NeurIPS=9, ICML=8, ICLR=9, AAAI=7, ACL=8.
    IEEE venues: references ARE included in page count.

    Output: Compilation result (success/failure, page count, warnings).
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Paper directory: {paper_dir}"},
    ])
