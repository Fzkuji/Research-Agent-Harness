# Adapted from academic-research-skills v3.12.0
# (https://github.com/Imbad0202/academic-research-skills),
# (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: ARS's Style Calibration protocol (shared/
# style_calibration_protocol.md, 6-dimension Style Profile) is recast as
# one @agentic_function that persists a JSON profile, plus a plain
# loader that renders a compact "voice card" for write/polish prompts.
from __future__ import annotations

import json
import os

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"callers": 0})
def build_style_profile(sample_paths: str, output_path: str = "",
                        runtime: Runtime = None) -> str:
    """Learn the author's writing voice from past writing samples.

    `sample_paths` lists 1-3 documents of the author's OWN past writing
    (comma- or newline-separated paths: papers, drafts, notes). Read
    each one, then extract a structured style profile. The goal is
    personalization — text that sounds like the author — NOT evading AI
    detectors.

    Extract ONE JSON object with exactly these keys:
    - "avg_sentence_length_pref": mean words per sentence plus rhythm
      note (e.g. "~22 words, alternates short punchy with long complex").
    - "hedging_style": preferred hedging words/phrases the author uses
      ("suggests" vs "indicates", "may" vs "might"), as a list.
    - "transition_preferences": preferred connectives ("However" vs
      "Nevertheless" vs "Yet"), as a list.
    - "reporting_verbs": citation reporting verbs ("found",
      "demonstrated", "argued"), as a list.
    - "citation_narrative_ratio": fraction (0-1) of narrative citations
      "Smith (2024) found..." vs parenthetical "(Smith, 2024)".
    - "register_notes": 1-2 sentences on formality level, modifier
      density, and how tone shifts across sections.

    Base every field on the samples — do not fill from generic academic
    style. With fewer than 3 samples, still produce the profile but add
    "(low confidence: N samples)" inside register_notes.

    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"sample_paths: {sample_paths}\n"
            f"output_path: "
            f"{output_path or '[default: ./style_profile.json]'}"
        )},
    ])


def load_style_profile(path: str) -> str:
    """Render a saved style profile as a compact voice-card string.

    Plain Python, no LLM. Returns "" when the file is missing or
    unreadable, so callers can embed the result unconditionally.
    """
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(profile, dict):
        return ""
    fields = [
        ("avg_sentence_length_pref", "sentence length"),
        ("hedging_style", "hedging"),
        ("transition_preferences", "transitions"),
        ("reporting_verbs", "reporting verbs"),
        ("citation_narrative_ratio", "narrative citation ratio"),
        ("register_notes", "register"),
    ]
    lines = []
    for key, label in fields:
        value = profile.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"- {label}: {value}")
    if not lines:
        return ""
    return (
        "Author voice card (soft guide — venue conventions take "
        "priority):\n" + "\n".join(lines)
    )
