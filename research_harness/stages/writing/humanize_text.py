from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def humanize_text(text: str, lang: str, voice_sample: str,
                  runtime: Runtime,
                  phrase_library_json: str = "") -> str:
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
    - phrase_library_json: optional JSON string from
                    stages/review/review_corpus/processed/phrase_library.json. When non-
                    empty, activates STRICT mode (Pass 5 below): the
                    rewrite must match the corpus's sentence-length
                    distribution, hedge density, paragraph length, and
                    first-person rate within tight tolerances, and must
                    sample opening-hook patterns + hedging phrases from the
                    pools. Used when GPTZero must be defeated (paper
                    abstract/intro). For routine cleanup, leave empty.

    # Task — four passes
    Pass 1 (Detect): scan for the 28 AI-writing patterns listed in
    `stages/review/detect_ai_flavor.py` (groups A-T + Chinese-specific).
    For every hit, plan a concrete rewrite.

    Pass 2 (Rewrite — surface cleanup): produce a draft that:
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

    Pass 3 (Cadence + voice — REQUIRED, this is what AI detectors actually
    measure). Surface cleanup alone is not enough. AI-detection tools score
    on perplexity and burstiness — i.e. the rhythm and unpredictability of
    the text — not on a lexicon. After Pass 2, deliberately rewrite the
    cadence:

      a. Burstiness — vary sentence length AGGRESSIVELY.
         - Target distribution: roughly 20% very short (5-12 words),
           50% medium (13-25 words), 30% long (26-45 words). NEVER write
           4+ consecutive sentences in the same length band.
         - After a long sentence, drop a short stub. Pattern examples:
           "Long, dense sentence with three sub-clauses. Hard to verify."
           "The estimate is rough. Prefill, KV-cache reuse, batching, and
           wall-clock latency are all unaccounted for. Same problem in
           Table 4."
         - Sentence fragments are FINE in moderation (1-2 per page) when
           they read like a real reviewer's terse aside: "Not enough
           ablations." "Hard to audit." "Same concern as R2."

      b. Structural irregularity — break parallel paragraph templates.
         - If 3+ weakness/strength paragraphs each open with "The X is Y"
           or "The Z lacks W", REWRITE openings so no two consecutive
           paragraphs share the same opening pattern.
         - Vary closing patterns too — don't end every paragraph with
           "this would strengthen the paper" or similar formulaic clauses.

      c. Voice — inject 1-3 personal markers per ~500 words.
         Reviewer-appropriate examples (DO use):
           - "I'm not sure this matters in practice, but ..."
           - "To me, the bigger issue is ..."
           - "If I were the AC I would push back here."
           - "Honestly, the appendix raises more questions than it answers."
           - "I would have liked to see ..."
         DO NOT use casual filler ("lol", "tbh", "kinda"), sycophancy
         ("great paper but"), or first-person bragging.
         Aim: ONE personal aside per ~250 words, not on every paragraph.

      d. Punctuation inconsistency — humans are inconsistent on purpose.
         - Mix in one or two parentheticals "(this is the heavier issue)"
           where they actually clarify.
         - Mix em dashes and commas across paragraphs — don't pick one
           and use it everywhere.
         - It's OK to leave one slightly informal phrase ("kind of",
           "more or less", "in the end") if it fits the register.

      e. Mid-thought hedges — humans don't always finish neatly.
         - 1-2 places, allow a hedge or backtrack: "...though I admit
           this might be addressed in the appendix I haven't fully
           read." "...assuming I'm reading Table 3 correctly."

      f. CRITICAL constraint — preserve all factual content. References,
         numbers, citations, technical claims must survive verbatim. Only
         the wrapper prose changes.

    Pass 4 (Audit + revise): after the draft, score yourself on:
      - Burstiness: list the sentence lengths in order. Are 4+ consecutive
        sentences within 5 words of each other? If yes, FIX.
      - Structural parallelism: do paragraphs open with the same template?
        If yes, FIX.
      - Voice markers: count personal asides. If zero in a 500+ word
        passage, ADD 1-2.
      - List remaining AI tells in 2-3 short bullets.
      - Produce the final revision.

    Pass 5 (STRICT mode — only when phrase_library_json is non-empty).
    Treat the corpus statistics as hard constraints, not suggestions.
    The library has these fields you must conform to:

      - sentence_length.histogram: target the SAME distribution
        (very_short_<=8, short_9_15, medium_16_25, long_26_40,
         very_long_>=41).
        Procedure: count your draft's sentences in each bucket; if any
        bucket is off by > 30% relative to the target, rewrite sentences
        to rebalance. Especially: human reviewers produce 15-25% very_short
        (<=8 word) sentences and 10-15% very_long (>=41 word) — most LLM
        output has nearly zero of either.

      - paragraph_length.mean: ≈ 2-3 sentences per paragraph. If your
        paragraphs are 5+ sentences, BREAK them.

      - first_person_per_100_words: ≥ 1.0 (i.e. at least one I/me/my per
        100 words on average). Reviewer prose is openly first-person.

      - em_dash_per_1000_chars: ≤ 1.0 (essentially zero). LLM output
        loves em-dashes; humans don't. Replace every em-dash with a
        comma, period, or parenthetical.

      - parenthetical_per_1000_chars: 1-3. Some parentheticals are fine.

      - hedging_phrases.matches_count: sample 1-3 hedges per ~500 words
        from this list (use the actual phrasing, not paraphrases):
        I think / to me / perhaps / arguably / in my opinion / kind of /
        somewhat / I'm not sure / I worry / I would push back /
        I would have liked / unless I'm missing something /
        if I'm reading X correctly.

      - opening_hook_patterns + top_sentence_openings_3w: at least 30%
        of your paragraph openings should match patterns from these
        pools (e.g. "The paper", "I think", "However", "Although",
        "It is unclear", "Can the authors").

    STRICT-mode self-audit (replace Pass 4's audit with this):
      - Sentence-length bucket counts: emit them. Compare to target
        histogram. State which buckets are off and what you fixed.
      - Personal-marker count: state count and rate per 100 words.
      - Em-dash count: must be 0 unless quoting source.
      - Hedge phrases used: list them (verbatim quotes from your draft).
      - Opening-hook coverage: % of paragraph openings drawn from pool.

    The library JSON appears in the input block under
    "=== PHRASE LIBRARY ===". Read it carefully before drafting.

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
    - Surface cleanup (Pass 2) is gentle: don't churn for its own sake.
    - Cadence and voice (Pass 3) is mandatory whenever the input passage
      is > 200 words AND was clearly LLM-produced (uniform sentence length,
      perfectly parallel paragraph structure, zero personal markers). The
      author/reviewer/section context implies LLM authorship — humanize
      properly. Returning the text essentially unchanged ("[clean]") is only
      acceptable when the original was already varied in cadence and voice,
      not just when it was lexically clean.
    - For genuinely human-written text passing through, return unchanged
      and report "[检测通过]" / "[clean]" in the modification log.

    # Output format (strict)
    Three sections, in order, no extra commentary:

    Part 1 [Final text]
    The humanized text. For `lang == "zh"`, plain text only — no markdown
    symbols. For `lang == "en"`, preserve LaTeX commands and math (`$...$`,
    `\\command{...}`) verbatim; humanize only the surrounding prose.

    Part 2 [Audit notes]
    A 3-5 bullet self-audit. Required items:
      - Sentence-length distribution: list the lengths (in words) of the
        first 8 sentences. Confirm at least 2 are < 13 words and at least
        2 are > 25 words.
      - Personal voice markers: count and quote them.
      - Structural variation: confirm no two consecutive paragraphs share
        the same opening pattern.
      - Any remaining AI tells (1-2 bullets max).
    If nothing remains, write "[clean] — burstiness, voice, and structure
    pass."

    Part 3 [Modification log]
    Bulleted list of changes, grouped by pass:
      - Pass 2 (lexical/surface): which AI patterns you rewrote.
      - Pass 3 (cadence/voice): which sentences you split or merged for
        burstiness; where you inserted personal asides; which paragraph
        openings you varied.
    If unchanged, write "[检测通过] 原文表达自然，无明显 AI 特征，建议保留。"
    / "[clean] no changes needed."

    # Persistence
    Save your COMPLETE output (Part 1 + Part 2 + Part 3) to a file in the
    current working directory. Choose a descriptive filename based on the
    function and context (e.g., humanize_intro_en.md, humanize_method_zh.md).
    After saving, return a brief summary (2-3 sentences) including the file
    path, the language detected, and whether the text was changed or passed
    through.
    Format: "Saved to <path>. <summary>."
    """
    library_block = ""
    if phrase_library_json:
        library_block = (
            "\n=== PHRASE LIBRARY (STRICT mode active — Pass 5 applies) ===\n"
            f"{phrase_library_json}\n"
            "=== END LIBRARY ===\n"
        )
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"lang: {lang}\n"
            f"voice_sample: {voice_sample if voice_sample else '[none]'}\n"
            f"{library_block}\n"
            f"=== TEXT TO HUMANIZE ===\n{text}\n=== END ==="
        )},
    ])
