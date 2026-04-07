"""
init_research — initialize a research project directory structure.

Creates a structured workspace for academic paper writing, organized by
paper sections. Includes a code repository, section-specific working
directories with guidance READMEs, and a LaTeX paper scaffold following
academic conventions.

Usage:
    from research_harness.stages.init import init_research

    path = init_research(
        name="LLM Uncertainty",
        venue="NeurIPS",
        base_dir="~/research",
    )
"""

import os
import subprocess
import re
from typing import Optional


def init_research(
    name: str,
    venue: Optional[str] = None,
    base_dir: Optional[str] = None,
    code_repo_url: Optional[str] = None,
    author: Optional[str] = None,
) -> str:
    """Initialize a research project directory structure for academic paper writing.

    Creates the following structure:
        <name>/
        ├── code/               # Git repository for implementation
        ├── outline/            # Paper outline (write before paper, get advisor approval)
        ├── introduction/       # Motivation, problem statement, approach
        ├── method/             # Method design, architecture, iterations
        ├── experiments/        # Results, analysis scripts, figures
        ├── related_work/       # Literature survey, paper notes
        ├── paper/              # LaTeX source (one .tex per section)
        ├── references/         # Writing guides and templates
        └── README.md           # Project overview

    Args:
        name:           Project name (e.g. "LLM Uncertainty"). Used as
                        directory name and LaTeX \\name macro.
        venue:          Target venue (e.g. "NeurIPS", "KDD", "ICML").
                        Affects LaTeX header and naming convention.
        base_dir:       Parent directory. Defaults to current directory.
        code_repo_url:  GitHub URL to clone into code/. If None, runs git init.
        author:         Author name for LaTeX and directory naming.

    Returns:
        Absolute path to the created project directory.
    """
    if base_dir is None:
        base_dir = os.getcwd()
    base_dir = os.path.expanduser(base_dir)

    project_dir = os.path.join(base_dir, name)
    os.makedirs(project_dir, exist_ok=True)

    # --- Code repository ---
    code_dir = os.path.join(project_dir, "code")
    if code_repo_url:
        if not os.path.exists(code_dir):
            subprocess.run(
                ["git", "clone", code_repo_url, code_dir],
                check=True, capture_output=True,
            )
    else:
        os.makedirs(code_dir, exist_ok=True)
        git_dir = os.path.join(code_dir, ".git")
        if not os.path.exists(git_dir):
            subprocess.run(
                ["git", "init", code_dir],
                check=True, capture_output=True,
            )

    # --- Outline (must be written and approved before paper) ---
    _create_section(project_dir, "outline", _OUTLINE_README)
    _write_if_missing(
        os.path.join(project_dir, "outline", "outline.md"),
        _outline_template(name),
    )

    # --- Section directories with README guidance ---
    _create_section(project_dir, "introduction", _INTRO_README)
    _create_section(project_dir, "method", _METHOD_README)
    _create_section(project_dir, "experiments", _EXPERIMENTS_README)
    _create_section(project_dir, "related_work", _RELATED_WORK_README)

    # --- LaTeX paper scaffold ---
    _create_paper(project_dir, name, venue, author)

    # --- References directory (writing guides, templates) ---
    refs_dir = os.path.join(project_dir, "references")
    os.makedirs(refs_dir, exist_ok=True)

    # --- Project README ---
    _write_if_missing(
        os.path.join(project_dir, "README.md"),
        _project_readme(name, venue),
    )

    return os.path.abspath(project_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _create_section(project_dir: str, section: str, readme_content: str):
    """Create a section directory with its README."""
    section_dir = os.path.join(project_dir, section)
    os.makedirs(section_dir, exist_ok=True)
    _write_if_missing(os.path.join(section_dir, "README.md"), readme_content)


def _write_if_missing(path: str, content: str):
    """Write file only if it doesn't already exist (never overwrite)."""
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content)


def _sanitize_name(name: str) -> str:
    """Convert project name to a LaTeX-safe command name."""
    return re.sub(r'[^a-zA-Z]', '', name)


def _create_paper(project_dir: str, name: str, venue: Optional[str], author: Optional[str]):
    """Create the LaTeX paper directory with section files."""
    paper_dir = os.path.join(project_dir, "paper")
    os.makedirs(paper_dir, exist_ok=True)

    latex_name = _sanitize_name(name)
    year = "2026"  # Update as needed
    venue_str = venue or "Venue"
    author_str = author or "Author"

    # Overleaf naming convention: Year-Venue-Author-Title
    # e.g., 2026-NeurIPS-AuthorName-LLMUncertainty
    overleaf_name = f"{year}-{venue_str}-{author_str}-{latex_name}"

    # Main .tex file
    _write_if_missing(
        os.path.join(paper_dir, f"0{overleaf_name}.tex"),
        _main_tex(name, latex_name, venue_str),
    )

    # Section files
    sections = {
        "1Introduction.tex": _section_tex("Introduction", "sec:intro"),
        "2Method.tex": _section_tex("Method", "sec:method"),  # or "Framework"
        "3Experiments.tex": _section_tex("Experiments", "sec:exp"),
        "5RelatedWork.tex": _section_tex("Related Work", "sec:related"),
        "6Conclusion.tex": _section_tex("Conclusion", "sec:conclusion"),
        "7Appendix.tex": _appendix_tex(),
    }
    for filename, content in sections.items():
        _write_if_missing(os.path.join(paper_dir, filename), content)

    # Bibliography
    _write_if_missing(
        os.path.join(paper_dir, "9Reference.bib"),
        "% Bibliography — use ONLY Google Scholar entries.\n"
        "% Do NOT use AI to generate or modify this file.\n"
        "% Verify every entry before submission.\n\n",
    )


# ---------------------------------------------------------------------------
# LaTeX templates
# ---------------------------------------------------------------------------

def _main_tex(name: str, latex_name: str, venue: str) -> str:
    return f"""\\documentclass{{article}}

% ============================================================
% Common packages
% ============================================================
\\usepackage{{amsmath,amssymb,amsfonts}}
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}       % Better tables
\\usepackage{{hyperref}}
\\usepackage{{xspace}}
\\usepackage{{color}}
\\usepackage{{enumitem}}

% ============================================================
% Macros
% ============================================================
\\newcommand{{\\etal}}{{\\emph{{et al.}}\\xspace}}
\\newcommand{{\\eg}}{{\\emph{{e.g.,}}\\xspace}}
\\newcommand{{\\ie}}{{\\emph{{i.e.,}}\\xspace}}
\\newcommand{{\\etc}}{{\\emph{{etc.}}\\xspace}}
\\newcommand{{\\name}}{{{latex_name}\\xspace}}

% Review comments (remove before camera-ready)
\\newcommand{{\\todo}}[1]{{{{\\color{{red}} [TODO: #1]}}}}
\\newcommand{{\\rev}}[1]{{{{\\color{{blue}} [#1]}}}}

% ============================================================
% Title
% ============================================================
\\title{{{name}}}
% \\author{{}}  % Add for camera-ready

\\begin{{document}}
\\maketitle

\\input{{1Introduction}}
\\input{{2Method}}
\\input{{3Experiments}}
\\input{{5RelatedWork}}
\\input{{6Conclusion}}

\\bibliographystyle{{plain}}
\\bibliography{{9Reference}}

\\appendix
\\input{{7Appendix}}

\\end{{document}}
"""


def _section_tex(title: str, label: str) -> str:
    return f"""\\section{{{title}}}
\\label{{{label}}}

% TODO: Write {title.lower()} content.

"""


def _appendix_tex() -> str:
    return """\\section{Additional Details}
\\label{sec:appendix}

% Supplementary material goes here.

"""


# ---------------------------------------------------------------------------
# README templates
# ---------------------------------------------------------------------------

_OUTLINE_README = """# Outline

Paper outline — **must be written and approved by advisor before writing the paper**.

## What goes here

- **outline.md**: The paper outline (use the template provided)
- Share via Google Doc with advisor for review
- Only start writing paper sections after outline is approved

## Workflow

1. Fill in outline.md following the template structure
2. Share with advisor (Google Doc or equivalent)
3. Get approval
4. Then start writing LaTeX in paper/

## Outline structure

The outline should cover:
- Introduction: background, problem, existing methods & limitations, our approach, contributions
- Related Work: categorized by topic, with limitations of each category
- Method: framework overview, key components, optimization
- Experiments: research questions, datasets, baselines, expected experiment types
- Conclusion: summary and future directions
"""

_INTRO_README = """# Introduction

Working directory for introduction-related materials.

## What goes here

- **Motivation**: Why is this problem important? What is the research significance?
- **Problem statement**: What specific problem are we solving?
- **Existing approaches**: What methods exist? What are their limitations?
- **Our approach**: How do we address the limitations? (high-level, no technical details)
- **Challenges**: What makes our approach non-trivial?

## Writing guidelines

- Introduction only describes model advantages, NOT technical details
- Technical details go in Method section
- Each claim needs support from existing work or our experiments
- Structure: background -> problem -> existing work & gaps -> our approach -> contributions
- Contributions: (1) discovery/phenomenon, (2) model innovation, (3) experimental results
"""

_METHOD_README = """# Method

Working directory for method design materials.

## What goes here

- **Architecture diagrams**: draw.io source files, exported PDFs
- **Algorithm design**: pseudocode, design iterations
- **Theoretical analysis**: proofs, derivations
- **Design iterations**: version history of method refinements

## Writing guidelines

- Start each section/subsection with WHY (motivation), then HOW (what you did)
- Use as few symbols as possible; each symbol means only one thing
- Matrices: bold uppercase. Vectors: bold lowercase. Scalars: no bold.
- Dimensions: use \\mathbb{R}
- All inline equations: use $...$, not \\(...\\)
"""

_EXPERIMENTS_README = """# Experiments

Working directory for experimental results and analysis.

## What goes here

- **Results data**: CSV/JSON output from code repository
- **Analysis scripts**: plotting code, statistical tests
- **Figures**: generated plots (save as PDF/EPS vector format, NOT PNG/JPG)
- **Tables**: raw data for paper tables

## Experiment types checklist

- [ ] Overall Performance (all datasets, all baselines)
- [ ] Ablation Study (remove key components)
- [ ] Parameter Analysis (vary hyperparameters)
- [ ] Efficiency Study (time/space analysis)
- [ ] Case Study / Visualization
- [ ] Compatibility / Transferability (if applicable)

## Analysis guidelines

- Each result analysis: Observation -> Reason (from model design) -> Conclusion
- Hypothesis testing with best baseline (two-sided t-test, p<0.05)
- Figures: text size >= paper body text size, use dark colors
- All figures/tables must be referenced in text
"""

_RELATED_WORK_README = """# Related Work

Working directory for literature survey and paper notes.

## What goes here

- **Paper notes**: summaries of related papers, organized by topic
- **Comparison tables**: feature/method comparison matrices
- **Survey drafts**: organized related work writeups

## Organization

Create subdirectories by topic area, e.g.:
- `topic_A/` — papers and notes on topic A
- `topic_B/` — papers and notes on topic B

## Writing guidelines

- Cite published versions, not arXiv (if published version exists)
- Do NOT cite multiple versions of the same paper
- Cite recent work (within 2 years) for baselines
- Each subsection: summarize approaches, then discuss limitations vs our method
- Use \\citep{} for parenthetical, \\citet{} for textual citations
- Never use citations as subjects: "\\citet{foo} proposes..." not "[1] proposes..."
"""


def _outline_template(name: str) -> str:
    return f"""# {name} — Outline

> Write this outline first, share with advisor for approval,
> then start writing the paper.

## Introduction

### Background and Macro Issues

<!-- Background, research significance -> introduce research problem -->
<!-- Template:
1. Macro goal: why the ultimate goal is important, applications
2. Macro method: current mainstream approach and what it does
3. Specific goals: list sub-problems/challenges under the macro goal
4. Specific methods: list fine-grained directions, introduce our direction
-->

### Specific Problem and Challenges

<!-- Concrete problem statement and difficulties -->
<!-- Template:
1. Summarize macro goal + method technically, introduce specific target
2. Why this target needs research (list reasons with examples)
3. Introduce the specific method direction we study
-->

### Existing Methods and Limitations

<!-- Overview of current approaches and their problems -->
<!-- Template:
1. Method category 1: implementation, examples, limitations
2. Method category 2: implementation, examples, limitations
3. Method category 3: implementation, examples, limitations
Note: each limitation should correspond to one of our innovations
-->

### Our Approach

<!-- Propose our model (high-level, no technical details) -->
<!-- Template:
1. Address limitation 1 -> our solution
2. Address limitation 2 -> our solution
3. Address limitation 3 -> our solution
4. Experimental validation summary
-->

### Contributions

<!-- Template:
1. Contribution 1: propose X method, which does Y, achieving Z
2. Contribution 2: propose X method, which does Y, achieving Z
3. Experiments on datasets A, B showing improvements of X%
-->

## Related Work

### Topic A

<!-- Progression style: concept -> existing work -> limitations -->

### Topic B

<!-- Parallel style: overview -> subtopic 1 -> subtopic 2 -> our novelty -->

## Method / Framework

### Framework Overview

<!-- High-level architecture, key components -->

### Component 1

<!-- Detail of first key component -->

### Component 2

<!-- Detail of second key component -->

### Optimization

<!-- Training procedure, loss functions -->

## Experiments

### Research Questions

- RQ1:
- RQ2:
- RQ3:

### Experimental Settings

- **Datasets**:
- **Evaluation Metrics**:
- **Baselines** (include recent work within 2 years):
- **Implementation Details**:

### Overall Performance (RQ1)

### Ablation Study (RQ2)

### Parameter Analysis (RQ3)

### Additional Experiments

<!-- Efficiency / Transferability / Case Study as needed -->

## Conclusion

<!-- Summary of contributions and future directions -->
"""


def _project_readme(name: str, venue: Optional[str]) -> str:
    venue_line = f"\n**Target venue**: {venue}\n" if venue else ""
    return f"""# {name}
{venue_line}
## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `outline/` | Paper outline (**write and get approval first**) |
| `code/` | Implementation code (git repository) |
| `introduction/` | Motivation, problem statement, approach design |
| `method/` | Method design, architecture, algorithm iterations |
| `experiments/` | Results, analysis scripts, figures |
| `related_work/` | Literature survey, paper notes |
| `paper/` | LaTeX source files |
| `references/` | Writing guides and templates |

## Workflow

1. **Survey**: Read related work, take notes in `related_work/`
2. **Outline**: Write outline in `outline/`, share with advisor, **get approval**
3. **Design**: Iterate on method in `method/`
4. **Implement**: Write code in `code/`
5. **Experiment**: Run experiments, save results to `experiments/`
6. **Write**: Draft paper in `paper/` (only after outline approved)

## Conventions

- Figures: vector format (PDF/EPS), drawn with draw.io
- Bibliography: Google Scholar entries only, verify before submission
- Code: no personal info, no hardcoded paths
- Submission: check anonymity, page limits, run Grammarly + iThenticate
"""
