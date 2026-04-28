"""Mine the GPTZero-validated human review corpus for stylistic primitives.

Output: stages/review/review_corpus/processed/phrase_library.json — fed to humanize_text
and review_paper prompts as a forced-sampling pool.

What we extract:
  - opening_patterns:   first 3-7 words of every paragraph
  - hedging_phrases:    "I'm not sure", "to me,", "though", "honestly", ...
  - reviewer_verbs:     verbs human reviewers use vs LLM defaults
  - sentence_lengths:   distribution (in words) — humanize prompt targets it
  - paragraph_lengths:  sentences per paragraph distribution
  - personal_markers:   "I", "to me", "in my view", "I would push back"
  - first_person_count: per-100-words rate of first-person constructs
  - punctuation_stats:  em-dash density, parenthetical density, etc.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DERIVED_ROOT = _HERE.parent / "processed"
CORPUS_PATH = DERIVED_ROOT / "human_reviews.json"
OUT_PATH = DERIVED_ROOT / "phrase_library.json"


# Hand-curated patterns we want frequencies for. These are NOT the only
# things we extract — we also emit raw n-gram top lists below.
HEDGING_PATTERNS = [
    r"\bI'?m not sure\b",
    r"\bI think\b",
    r"\bin my view\b",
    r"\bin my opinion\b",
    r"\bto me,?\b",
    r"\bhonestly,?\b",
    r"\bto be honest\b",
    r"\bI would push back\b",
    r"\bI would have liked\b",
    r"\bI'?d argue\b",
    r"\bI suspect\b",
    r"\bI worry\b",
    r"\bmy concern\b",
    r"\bmy main concern\b",
    r"\bI'?m concerned\b",
    r"\bI find it\b",
    r"\bit seems to me\b",
    r"\barguably\b",
    r"\bperhaps\b",
    r"\bsomewhat\b",
    r"\bkind of\b",
    r"\bmore or less\b",
    r"\bif I'?m reading .* correctly\b",
    r"\bunless I'?m missing something\b",
]

OPENING_HOOK_PATTERNS = [
    r"^The main\b", r"^My main\b",
    r"^It is not clear\b", r"^It'?s not clear\b",
    r"^It is unclear\b",
    r"^One concern\b", r"^Another concern\b",
    r"^I would\b", r"^I think\b", r"^I'?m\b",
    r"^Why\b", r"^How\b",
    r"^The paper\b", r"^This paper\b",
    r"^Although\b", r"^However,?\b",
    r"^Looking at\b",
]


def _split_paragraphs(text: str) -> list[str]:
    paras = re.split(r"\n{2,}|\r\n\r\n", text)
    return [p.strip() for p in paras if p.strip()]


def _split_sentences(text: str) -> list[str]:
    # Cheap sentence splitter — good enough for stats, not for NLP.
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", text.strip())
    return [s.strip() for s in sents if s.strip()]


def _ngram(words: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(w.lower() for w in words[i:i + n])
            for i in range(len(words) - n + 1)]


def _is_generic(ngram: tuple[str, ...]) -> bool:
    """Filter trivial n-grams ("of the", "in the", "to the", ...).

    These pollute the top-K but don't carry style information. We keep
    n-grams that contain at least one substantive token (length >= 4 and
    not in the closed-class stopword list)."""
    closed = {"the", "a", "an", "of", "to", "in", "on", "at", "for",
              "with", "and", "or", "but", "is", "are", "was", "were",
              "this", "that", "these", "those", "it", "its", "be", "by",
              "as", "if", "then", "than", "from", "into", "over",
              "such", "some", "any", "all", "no", "not"}
    return all((w in closed) or (len(w) < 3) for w in ngram)


def mine() -> dict:
    with open(CORPUS_PATH) as f:
        corpus = json.load(f)
    if not corpus:
        raise SystemExit("voice corpus is empty — run _filter.py first")

    all_text = []
    paragraph_lens: list[int] = []
    sentence_lens: list[int] = []
    opening_words_3: Counter = Counter()
    opening_words_5: Counter = Counter()
    bigrams: Counter = Counter()
    trigrams: Counter = Counter()
    word_freq: Counter = Counter()
    em_dash_total = 0
    parenthetical_total = 0
    word_total = 0

    for sample in corpus:
        text = sample.get("text") or ""
        if not text:
            continue
        all_text.append(text)
        em_dash_total += text.count("—")
        parenthetical_total += len(re.findall(r"\([^)]+\)", text))

        for para in _split_paragraphs(text):
            sents = _split_sentences(para)
            paragraph_lens.append(len(sents))
            for s in sents:
                words = re.findall(r"[A-Za-z']+", s)
                if not words:
                    continue
                sentence_lens.append(len(words))
                word_total += len(words)
                word_freq.update(w.lower() for w in words)
                # 3-word and 5-word opening of each sentence
                opening_words_3[" ".join(words[:3]).lower()] += 1
                if len(words) >= 5:
                    opening_words_5[" ".join(words[:5]).lower()] += 1
                # bi/tri-grams across the whole sentence (for body phrases)
                for ng in _ngram(words, 2):
                    if not _is_generic(ng):
                        bigrams[ng] += 1
                for ng in _ngram(words, 3):
                    if not _is_generic(ng):
                        trigrams[ng] += 1

    full_text = "\n\n".join(all_text)

    # Hedging hits — count and extract example contexts.
    hedge_hits: dict[str, int] = {}
    hedge_examples: dict[str, list[str]] = {}
    for pat in HEDGING_PATTERNS:
        rx = re.compile(pat, flags=re.IGNORECASE)
        matches = rx.findall(full_text)
        if matches:
            label = pat.replace("\\b", "").replace("?", "").strip()
            hedge_hits[label] = len(matches)
            # Pull up to 3 surrounding-context examples.
            ctx = []
            for m in rx.finditer(full_text):
                start = max(0, m.start() - 40)
                end = min(len(full_text), m.end() + 60)
                ctx.append("…" + full_text[start:end].replace("\n", " ") + "…")
                if len(ctx) >= 3:
                    break
            hedge_examples[label] = ctx

    # Opening hook hits per pattern (start of paragraph).
    opening_hook_hits: dict[str, int] = {}
    for pat in OPENING_HOOK_PATTERNS:
        rx = re.compile(pat, flags=re.MULTILINE)
        matches = rx.findall(full_text)
        if matches:
            label = pat.replace("^", "").replace("\\b", "").replace("?", "").strip()
            opening_hook_hits[label] = len(matches)

    # Sentence length distribution buckets (in words).
    def _hist(values: list[int], buckets: list[tuple[str, int, int]]
              ) -> dict[str, int]:
        out = {label: 0 for label, _, _ in buckets}
        for v in values:
            for label, lo, hi in buckets:
                if lo <= v <= hi:
                    out[label] += 1
                    break
        return out

    sent_buckets = [
        ("very_short_<=8",  0, 8),
        ("short_9_15",      9, 15),
        ("medium_16_25",   16, 25),
        ("long_26_40",     26, 40),
        ("very_long_>=41", 41, 10**6),
    ]
    para_buckets = [
        ("1_sentence",   1, 1),
        ("2_3",          2, 3),
        ("4_6",          4, 6),
        ("7_10",         7, 10),
        ("11_plus",     11, 10**6),
    ]

    # First-person rate per 100 words.
    first_person_words = re.findall(
        r"\b(I|i'm|I'm|me|my|mine|myself)\b", full_text)
    first_person_per_100 = (len(first_person_words) / max(1, word_total)) * 100

    library = {
        "corpus_meta": {
            "n_samples": len(corpus),
            "total_chars": sum(len(s.get("text") or "") for s in corpus),
            "total_words": word_total,
            "venues": sorted({s.get("venue") for s in corpus if s.get("venue")}),
            "year_range": [
                min((s.get("year", 9999) for s in corpus), default=None),
                max((s.get("year", 0) for s in corpus), default=None),
            ],
        },
        "sentence_length": {
            "mean": round(sum(sentence_lens) / max(1, len(sentence_lens)), 2),
            "n": len(sentence_lens),
            "histogram": _hist(sentence_lens, sent_buckets),
            "percentiles": {
                "p10": _percentile(sentence_lens, 10),
                "p25": _percentile(sentence_lens, 25),
                "p50": _percentile(sentence_lens, 50),
                "p75": _percentile(sentence_lens, 75),
                "p90": _percentile(sentence_lens, 90),
            },
        },
        "paragraph_length": {
            "mean": round(sum(paragraph_lens) / max(1, len(paragraph_lens)), 2),
            "n": len(paragraph_lens),
            "histogram": _hist(paragraph_lens, para_buckets),
        },
        "first_person_per_100_words": round(first_person_per_100, 2),
        "em_dash_per_1000_chars":
            round((em_dash_total / max(1, len(full_text))) * 1000, 2),
        "parenthetical_per_1000_chars":
            round((parenthetical_total / max(1, len(full_text))) * 1000, 2),
        "hedging_phrases": {
            "matches_count": hedge_hits,
            "examples": hedge_examples,
        },
        "opening_hook_patterns": opening_hook_hits,
        "top_sentence_openings_3w":
            [(p, c) for p, c in opening_words_3.most_common(40)],
        "top_sentence_openings_5w":
            [(p, c) for p, c in opening_words_5.most_common(30)],
        "top_bigrams":
            [(" ".join(ng), c) for ng, c in bigrams.most_common(40)],
        "top_trigrams":
            [(" ".join(ng), c) for ng, c in trigrams.most_common(40)],
        # AI-vocab vs reviewer-vocab diff: words that are common in this
        # corpus but normally flagged as AI-y. Useful to see which "AI"
        # words are actually fine for academic peer review.
        "vocab_top_50":
            [(w, c) for w, c in word_freq.most_common(50)
             if w.isalpha() and len(w) >= 4],
    }
    with open(OUT_PATH, "w") as f:
        json.dump(library, f, ensure_ascii=False, indent=2)
    return library


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = int(round(pct / 100 * (len(s) - 1)))
    return s[idx]


if __name__ == "__main__":
    lib = mine()
    print(f"wrote {OUT_PATH}")
    print(f"\ncorpus: {lib['corpus_meta']['n_samples']} samples, "
          f"{lib['corpus_meta']['total_words']} words, "
          f"venues={lib['corpus_meta']['venues']}, "
          f"years {lib['corpus_meta']['year_range']}")
    print(f"\nsentence length: mean={lib['sentence_length']['mean']} "
          f"p25/50/75={lib['sentence_length']['percentiles']['p25']}/"
          f"{lib['sentence_length']['percentiles']['p50']}/"
          f"{lib['sentence_length']['percentiles']['p75']}")
    print("histogram:")
    for k, v in lib["sentence_length"]["histogram"].items():
        print(f"  {k:<22}{v}")
    print(f"\nparagraph length mean: {lib['paragraph_length']['mean']} sentences")
    print(f"first-person/100w:  {lib['first_person_per_100_words']}")
    print(f"em-dash/1000ch:     {lib['em_dash_per_1000_chars']}")
    print(f"parenthetical/1000ch: {lib['parenthetical_per_1000_chars']}")
    print(f"\ntop hedges:")
    for k, v in sorted(lib["hedging_phrases"]["matches_count"].items(),
                       key=lambda kv: -kv[1])[:10]:
        print(f"  [{v:3d}] {k}")
    print(f"\ntop opening-hook patterns:")
    for k, v in sorted(lib["opening_hook_patterns"].items(),
                       key=lambda kv: -kv[1])[:10]:
        print(f"  [{v:3d}] {k}")
    print(f"\ntop sentence-opening 3-grams:")
    for p, c in lib["top_sentence_openings_3w"][:15]:
        print(f"  [{c:3d}] '{p}'")
