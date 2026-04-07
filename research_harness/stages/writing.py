"""
writing — paper writing stage.

All prompts live in @agentic_function docstrings. The docstring IS the
instruction sent to the LLM; content= carries only data.

For tasks with multiple approaches (e.g. polishing), competing functions
with different docstrings are evaluated via evaluate.compete().
"""

from __future__ import annotations

import os

from agentic.function import agentic_function
from agentic.runtime import Runtime


# ---------------------------------------------------------------------------
# Section writing
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_section(section: str, context: str, runtime: Runtime) -> str:
    """Write one section of an academic paper in LaTeX.

    You are a senior ML researcher writing for a top venue (NeurIPS/ICML/ICLR).

    Rules:
    - Start each subsection with WHY (motivation), then HOW (what you did).
    - Every claim needs evidence from experiments or citations.
    - Use continuous paragraphs, never bullet lists or \\item.
    - Introduction: background → problem → existing gaps → our approach → contributions.
      Only describe model advantages, NO technical details (save for Method).
    - Method: precise symbols, \\boldsymbol for vectors/matrices, \\mathbb{R} for dims.
    - Experiments: observation → reason (from model design) → conclusion for each result.
    - Related Work: summarize approaches per subsection, end with limitations vs ours.
    - Use \\citep{} for parenthetical, \\citet{} for textual. Never use citations as subjects.
    - Present tense for methods/results, past tense only for specific historical events.
    - No AI-flavor words (leverage, delve, tapestry, utilize). Use simple, clear vocabulary.

    Output ONLY the LaTeX content for the section. No explanation.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Section to write: {section}\n\n"
            f"Project context:\n{context}"
        )},
    ])


def gather_context(project_dir: str, section: str) -> str:
    """Gather context from project directory for writing a section."""
    project_dir = os.path.expanduser(project_dir)
    parts = []

    # Outline
    outline_path = os.path.join(project_dir, "outline", "outline.md")
    if os.path.exists(outline_path):
        with open(outline_path, "r") as f:
            parts.append(f"## Outline\n{f.read()[:3000]}")

    # Section-specific notes
    section_dir = os.path.join(project_dir, section)
    if os.path.isdir(section_dir):
        for fname in sorted(os.listdir(section_dir)):
            if fname == "README.md":
                continue
            fpath = os.path.join(section_dir, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r") as f:
                        parts.append(f"## Notes: {fname}\n{f.read()[:2000]}")
                except (UnicodeDecodeError, IOError):
                    pass

    return "\n\n".join(parts) if parts else "No context available yet."


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def translate_zh2en(text: str, runtime: Runtime) -> str:
    """Translate Chinese academic draft to English LaTeX.

    You are a top scientific writing expert and senior conference reviewer
    (ICML/ICLR). Zero tolerance for logic holes and language flaws.

    Rules:
    - No bold, italic, or quotes — keep LaTeX clean.
    - Rigorous logic, precise wording, concise and coherent.
    - Use common words, avoid obscure vocabulary.
    - No dashes (—), use clauses or appositives instead.
    - No \\item lists, use continuous paragraphs.
    - Remove AI flavor, write naturally.
    - Present tense for methods/results, past tense for historical events.
    - Escape special chars: % → \\%, _ → \\_, & → \\&.

    Output:
    - Part 1 [LaTeX]: English LaTeX only.
    - Part 2 [Translation]: Chinese back-translation for verification.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def translate_en2zh(text: str, runtime: Runtime) -> str:
    """Translate English LaTeX to readable Chinese text.

    You are a senior CS academic translator helping researchers
    quickly understand complex English paper paragraphs.

    Rules:
    - Remove all \\cite{}, \\ref{}, \\label{} commands.
    - Extract text from \\textbf{}, \\emph{} — ignore formatting.
    - Convert LaTeX math to natural language (e.g. $\\alpha$ → alpha).
    - Strict literal translation, preserve original sentence structure.
    - Do NOT polish or reorganize — reflect the original faithfully.

    Output: Pure Chinese text only, no LaTeX code.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


# ---------------------------------------------------------------------------
# Polishing — two competing approaches
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def polish_rigorous(text: str, runtime: Runtime) -> str:
    """Deep polish for top-tier conference submission (rigor-focused).

    You are a senior academic editor for NeurIPS/ICLR/ICML submissions.
    Focus on academic rigor, clarity, and zero-error publishing standard.

    Rules:
    - Optimize sentence structure for top-venue conventions.
    - Eliminate non-native stiffness, make prose flow naturally.
    - Fix ALL spelling, grammar, punctuation, and article errors.
    - Formal register: use "it is" not "it's", "does not" not "doesn't".
    - Simple & clear vocabulary, no fancy or obscure words.
    - No noun possessives for methods (use "the performance of X" not "X's performance").
    - Preserve LaTeX commands (\\cite{}, \\ref{}, \\eg, \\ie).
    - Keep existing formatting (\\textbf{} if present), add no new emphasis.
    - Never convert paragraphs to lists.

    Output:
    - Part 1 [LaTeX]: Polished English LaTeX code only.
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: Brief summary of changes.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def polish_natural(text: str, runtime: Runtime) -> str:
    """Polish for naturalness — remove mechanical/AI writing patterns.

    You are a senior editor focused on making academic text sound like
    it was written by a native English-speaking researcher.

    Rules:
    - Replace overused AI words: leverage→use, delve→investigate,
      tapestry→context, conceptualize→design, unveil→show, etc.
    - Remove mechanical connectors: "First and foremost", "It is worth noting".
    - Reduce dashes (—), use commas, parentheses, or clauses.
    - No bold/italic emphasis in body text.
    - Keep LaTeX commands intact.
    - If text is already natural with no AI signatures, output it unchanged
      and note "[检测通过] — natural, no changes needed."

    Output:
    - Part 1 [LaTeX]: Rewritten code (or original if already good).
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: Changes made, or "[检测通过]".
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


# ---------------------------------------------------------------------------
# Logic check
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def check_logic(text: str, runtime: Runtime) -> str:
    """Final manuscript check — only flag fatal errors.

    You are an experienced CS paper reviewer doing a final pass.

    Check ONLY for showstoppers:
    - Logical contradictions between statements
    - Terminology inconsistency (same concept, different names)
    - Severe grammar errors that affect comprehension
    - Data inconsistency (numbers in text vs tables/figures)

    High tolerance: style preferences and minor wording are NOT in scope.
    If nothing serious found, output: "[检测通过，无实质性问题]"
    Otherwise: brief Chinese bullet points with location and issue.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


# ---------------------------------------------------------------------------
# Experiment analysis
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def analyze_results(data: str, runtime: Runtime) -> str:
    """Analyze experimental data and write LaTeX analysis paragraphs.

    You are a senior data scientist with sharp insight into experimental
    results, writing for a top-tier conference.

    Rules:
    - ALL conclusions must be strictly based on the input data.
      NEVER fabricate data, exaggerate improvements, or invent phenomena.
    - Focus on comparisons and trends, not raw number reporting.
    - Analysis pattern for each finding:
      Observation (B beats A) → Reason (B has X, A lacks it) → Conclusion
      (proves importance of X / necessity of introducing Y).
    - Use \\paragraph{Core Conclusion} + analysis text format (Title Case).
    - No bold/italic, no list environments, pure text paragraphs.
    - Escape special chars: %, _, &.

    Output:
    - Part 1 [LaTeX]: Analysis paragraphs.
    - Part 2 [Translation]: Chinese translation for verification.
    """
    return runtime.exec(content=[
        {"type": "text", "text": data},
    ])


# ---------------------------------------------------------------------------
# Compression / expansion
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def compress_text(text: str, runtime: Runtime) -> str:
    """Reduce word count by 5-15 words through sentence optimization.

    Preserve ALL information, technical details, and experimental parameters.
    Use clause compression, passive-to-active conversion, redundancy removal.

    Output:
    - Part 1 [LaTeX]: Compressed text.
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: What was compressed.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def expand_text(text: str, runtime: Runtime) -> str:
    """Add 5-15 words by deepening logic, adding connectors, upgrading expressions.

    Only add content grounded in the original text's reasoning. NEVER fabricate.
    Add logical transitions, methodology details, or result interpretation.

    Output:
    - Part 1 [LaTeX]: Expanded text.
    - Part 2 [Translation]: Chinese translation.
    - Part 3 [Log]: What was added.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


# ---------------------------------------------------------------------------
# Chinese paper support (中文论文)
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def rewrite_zh(text: str, runtime: Runtime) -> str:
    """Rewrite fragmented Chinese draft into polished academic Chinese (中转中).

    You are a senior editor for top Chinese CS journals (计算机学报, 软件学报).

    Rules:
    - Restructure logic: identify the main thread, reconnect loose sentences.
    - One paragraph = one core idea. No multi-topic paragraphs.
    - Convert oral speech to formal academic writing
      (e.g. "我们觉得" → "实验结果表明", "不管A还是B" → "无论A抑或B").
    - Convert lists to continuous paragraphs.
    - Pure text output, NO Markdown formatting (no bold, italic, headers).
    - Use Chinese full-width punctuation (，。；：""）.
    - Preserve English technical terms (Transformer, CNN, Few-shot).

    Output:
    - Part 1 [Refined Text]: Rewritten Chinese paragraph.
    - Part 2 [Logic flow]: Brief explanation of restructuring logic.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def polish_zh(text: str, runtime: Runtime) -> str:
    """Polish Chinese academic paper text (表达润色中文).

    You are a senior editor for core Chinese CS journals, following the
    principle of "respect the original, restrain modifications."

    Rules:
    - Only modify when detecting: oral expressions, grammar errors,
      logic breaks, or severely Europeanized long sentences.
    - If the original is already clear and correct, DO NOT change it.
    - Use modern academic Chinese, not archaic bureaucratic style.
    - Replace oral speech with objective statements.
    - Pure text output, NO Markdown formatting.
    - Chinese full-width punctuation.

    Output:
    - Part 1 [Refined Text]: Polished text (or original if no changes needed).
    - Part 2 [Review Comments]: Changes made, or affirmation if unchanged.
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def remove_ai_flavor_zh(text: str, runtime: Runtime) -> str:
    """Remove AI-generated patterns from Chinese text (去AI味中文).

    Eliminate machine-translated, over-rendered language patterns:
    - Remove meaningless emotional words (毋庸置疑, 颠覆性, 深刻, 至关重要).
    - Break up English-style long attributive structures.
    - Reduce passive voice, replace list formats with logical prose.
    - No Markdown formatting in output.

    Output:
    - Part 1 [Text]: Cleaned text (or original if already natural).
    - Part 2 [Log]: Changes made, or "[检测通过] 原文自然，无AI味。"
    """
    return runtime.exec(content=[
        {"type": "text", "text": text},
    ])


# ---------------------------------------------------------------------------
# Figures & Tables
# ---------------------------------------------------------------------------

@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_figure_caption(description: str, runtime: Runtime) -> str:
    """Generate an English figure caption for a top-tier conference paper.

    Title Case for noun phrases (no period). Sentence case for sentences (with period).
    Minimal style: never start with "The figure shows..."
    Use "show", "compare", "present" — avoid "showcase", "depict".
    Do NOT include "Figure X:" prefix — just the caption text.

    Output: English caption text only.
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_table_caption(description: str, runtime: Runtime) -> str:
    """Generate an English table caption for a top-tier conference paper.

    Recommended structures: "Comparison of ... on ...",
    "Ablation study on ...", "Results on ... dataset", "Effect of ... on ...".
    Use "show", "compare", "report" — avoid "showcase", "depict".
    Do NOT include "Table X:" prefix.

    Output: English caption text only.
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def recommend_visualization(data_description: str, runtime: Runtime) -> str:
    """Recommend chart types for experimental data visualization.

    Available types: grouped bar, horizontal bar, stacked bar,
    line with CI, Pareto front, radar, scatter, heatmap, bubble,
    violin, box, ROC/PR, dual-axis, facet grid, inset zoom.

    Consider: data scale (broken axes, log scale), color-blind palettes,
    vector format (PDF/EPS), text size >= body text.

    Output: Recommended chart type + rationale + design specs.
    """
    return runtime.exec(content=[
        {"type": "text", "text": data_description},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def design_architecture_figure(method_description: str, runtime: Runtime) -> str:
    """Design a paper architecture/framework diagram.

    Style: flat vector, clean lines (DeepMind/OpenAI style).
    Professional pastels on white background. English labels, minimal text.

    Output: diagram layout description, component list, connections,
    color scheme, and draw.io / TikZ reproduction notes.
    """
    return runtime.exec(content=[
        {"type": "text", "text": method_description},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def results_to_claims(results: str, intended_claims: str,
                      runtime: Runtime) -> str:
    """Judge what claims experimental results actually support.

    For each claim: supported? (yes/partial/no), evidence strength,
    gaps, suggested rewording if too strong. Be brutally honest.

    Output JSON: {"claims": [{"claim": "...", "supported": "yes/partial/no",
    "evidence": "...", "gaps": "...", "suggested_wording": "..."}]}
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Intended claims:\n{intended_claims}\n\n"
            f"Experimental results:\n{results}"
        )},
    ])
