from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_poster(paper_content: str, venue: str,
                    runtime: Runtime) -> str:
    """Generate a conference poster (article + tcbposter LaTeX) from a compiled paper.

    Unlike papers (dense prose, 8-15 pages), posters are visual-first: one page,
    bullet points only, figures dominant. A good poster tells the story in 60 seconds.

    Critical LaTeX architecture decisions:
    - MUST use article class, NEVER beamer class (beamer exceeds TeX grouping levels
      with tcbposter's enhanced style on 8+ posterboxes)
    - NEVER use adjustbox package (may not be installed). Use plain
      \\\\includegraphics[width=0.96\\\\linewidth]{{file}} instead.
    - NEVER use \\\\usepackage[most]{{tcolorbox}} (pulls in listingsutf8.sty which may
      not be installed). Use \\\\tcbuselibrary{{poster,skins,fitting}} explicitly.
    - Use [table]{{xcolor}} not plain {{xcolor}} for \\\\rowcolor support.

    Layout rules:
    - 4 columns for landscape A0 (IMRAD flow), 3 for portrait A0 (research consensus:
      4 columns at 841mm width gives only ~195mm per column, too narrow for readability).
    - Use rows=20 for fine-grained vertical control (~42mm per row on A0 landscape).
    - Always use between=rowN and rowM syntax (not below=name) for precise vertical placement.
    - Use spacing=0mm for tight layouts; card separation via card styles (left accent stripe).

    Modern card design system (left accent stripe):
    - Define 4 card styles using the venue's 3-color system:
      redcard, bluecard, darkcard, highlightcard
    - Each card has: enhanced, arc=0pt, boxrule=0pt, colored background,
      borderline west={{5pt}}{{0pt}}{{color}}, drop shadow

    Venue color schemes (deep saturated for visibility at poster distance):
    - NeurIPS: primary #4C1D95, secondary #6D28D9, accent #2563EB, bg #F5F3FF
    - ICML: primary #7F1D1D, secondary #B91C1C, accent #1E40AF, bg #EDD5D5
    - ICLR: primary #065F46, secondary #059669, accent #0284C7, bg #F0FDF4
    - CVPR: primary #1E3A8A, secondary #2563EB, accent #7C3AED, bg #F8FAFC
    - GENERIC: primary #1E293B, secondary #334155, accent #2563EB, bg #F8FAFC

    Poster size defaults: A0 landscape (841x1189mm).
    Text minimums: 24pt body, 32pt section headers, 48pt+ title.
    Sections: Title/Authors, Stat Banner, Motivation, Method (diagram),
    Key Results (1-2 figures), Analysis/Ablation, Conclusion, QR code.

    Output: Complete LaTeX poster source code using article class + tcbposter.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])
