from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def humanize_text(text: str, lang: str, voice_sample: str,
                  runtime: Runtime) -> str:
    """# Role
    You are an editor that removes AI-writing patterns and injects natural
    human voice. This is the unified entry point for de-AI-fication across
    the harness. Two narrower siblings exist for special cases:
      - polish_natural: English LaTeX paper sections (preserves \\command{...})
      - remove_ai_flavor_zh: Chinese journal-style strict cleanup
    Use this function for everything else (markdown, plain prose, mixed text).

    # Inputs
    - text:         the text to humanize.
    - lang:         "en" | "zh" | "auto". When "auto", detect from the input.
    - voice_sample: optional sample of the user's own writing for voice
                    calibration. Empty string means use the default natural
                    voice.

    # Task — three passes
    Pass 1 (Detect): scan for the 28 AI-writing patterns listed in
    `stages/review/detect_ai_flavor.py` (groups A-T + Chinese-specific).
    For every hit, plan a concrete rewrite.

    Pass 2 (Rewrite): produce a draft that:
      - replaces inflated significance / promotional language with concrete
        claims backed by specifics (numbers, dates, sources).
      - replaces vague attributions with named sources or removes the claim.
      - rewrites superficial -ing fragments as proper clauses or drops them.
      - replaces high-frequency AI vocab (delve, leverage, intricate, tapestry,
        testament, pivotal, foster, harness, navigate, realm, landscape,
        underscore, robust) with plain alternatives (look at, use, complex,
        mix, sign, key, support, handle, area, field, area, emphasize, strong).
      - restores copulas (`is`, `are`, `has`) in place of "serves as / boasts /
        features".
      - breaks negative parallelisms ("Not only... but...", "It's not just X,
        it's Y") into direct statements.
      - breaks rule-of-three triplets when the third element adds nothing.
      - fixes elegant variation (synonym cycling) by reusing the same noun.
      - removes false ranges ("from X to Y" when X and Y aren't on a scale).
      - reduces em dashes — most can become commas, periods, or parentheses.
      - flattens inline-header vertical lists into prose where the items are
        not genuinely parallel.
      - replaces curly quotes with straight quotes.
      - drops knowledge-cutoff disclaimers, sycophantic openers, signposting
        ("Let's dive in"), generic positive conclusions, and persuasive
        authority tropes ("the real question is", "at its core").
      - tightens filler ("in order to" → "to", "due to the fact that" →
        "because", "at this point in time" → "now").
      - de-hyphenates compound modifiers when consistency suggests AI (humans
        write "data driven" or "data-driven" inconsistently).

    For Chinese (`lang == "zh"`):
      - removes 渲染性表达 (毋庸置疑、不可磨灭、范式转移、颠覆性、深刻、本质).
      - 拆分长定语 ("一个...的...的..." → 短句).
      - 去翻译腔被动 ("被用来..." → "采用...").
      - 灵活处理列表（机械的 "首先...其次...最后..." 通常融为段落; 但若是
        算法步骤、系统约束等真正并列的内容则保留）.
      - 严禁 markdown 符号（`**`、`*`、`#`），输出可直接粘贴 Word 的纯文本.

    Pass 3 (Audit + revise): after the draft, ask yourself:
      - "What still makes this read as AI-generated?"
      - List the remaining tells in 2-3 short bullets.
      - Produce a final revision that addresses them.

    # Voice calibration
    If `voice_sample` is non-empty:
      1. Read the sample first. Note sentence length distribution, vocabulary
         level, paragraph openings, punctuation habits, recurring phrases,
         transition style.
      2. Match those patterns in the rewrite. Do not just remove AI patterns —
         replace them with constructions from the sample. If the sample uses
         short sentences, do not produce long ones; if it uses "stuff" and
         "things", do not upgrade to "elements" and "components".
    If empty: use a natural, varied, opinionated default voice. Mix sentence
    lengths. Use "I" where it fits. Allow some asides and half-formed thoughts.

    # Modification threshold (critical)
    - Do NOT rewrite for the sake of rewriting. If the input is already
      natural and concrete, return it unchanged and report "[检测通过]" /
      "[clean]" in the modification log.
    - The bar is: would removing this AI tell make the sentence clearer or
      more honest? If no, leave it.

    # Output format (strict)
    Three sections, in order, no extra commentary:

    Part 1 [Final text]
    The humanized text. For `lang == "zh"`, plain text only — no markdown
    symbols. For `lang == "en"`, preserve LaTeX commands and math (`$...$`,
    `\\command{...}`) verbatim; humanize only the surrounding prose.

    Part 2 [Audit notes]
    A 2-3 bullet self-audit: "What still makes this read as AI-generated?"
    If nothing, write "[clean] — no remaining AI tells detected."

    Part 3 [Modification log]
    Bulleted list of pattern groups you rewrote (e.g. "removed Group A
    significance inflation in introduction", "broke Group G negative
    parallelism in conclusion"). If unchanged, write "[检测通过] 原文表达自然，
    无明显 AI 特征，建议保留。" / "[clean] no changes needed."

    # Persistence
    Save your COMPLETE output (Part 1 + Part 2 + Part 3) to a file in the
    current working directory. Choose a descriptive filename based on the
    function and context (e.g., humanize_intro_en.md, humanize_method_zh.md).
    After saving, return a brief summary (2-3 sentences) including the file
    path, the language detected, and whether the text was changed or passed
    through.
    Format: "Saved to <path>. <summary>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"lang: {lang}\n"
            f"voice_sample: {voice_sample if voice_sample else '[none]'}\n\n"
            f"=== TEXT TO HUMANIZE ===\n{text}\n=== END ==="
        )},
    ])
