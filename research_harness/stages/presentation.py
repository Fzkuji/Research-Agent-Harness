"""
presentation — generate slides and posters from paper.

Creates Beamer slides for conference talks and LaTeX posters
for poster sessions.
"""

from __future__ import annotations

import os

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_slides(paper_content: str, venue: str, talk_type: str,
                    minutes: int, runtime: Runtime) -> str:
    """Generate Beamer presentation slides from a paper.

    Talk types and slide counts:
    - poster-talk (3-5 min): 5-8 slides
    - spotlight (5-8 min): 8-12 slides
    - oral (15-20 min): 15-22 slides
    - invited (30-45 min): 25-40 slides

    Slide structure for oral/spotlight:
    1. Title slide
    2. Problem & Motivation (why should the audience care?)
    3. Key insight / contribution (the "aha" moment)
    4. Method overview (1-2 slides, visual-first)
    5. Key results (most impactful numbers/figures)
    6. Analysis / ablation (1 slide)
    7. Conclusion & future work
    8. Thank you + QR code to paper

    Rules:
    - Tell a STORY, not a summary. Build understanding progressively.
    - One message per slide. If you need two points, use two slides.
    - Figures > text. Minimize bullet points.
    - ~1 slide per minute for oral, ~1.5 for spotlight.
    - Include \\note{} blocks for speaker notes.
    - Use venue-appropriate color scheme.

    Output: Complete Beamer LaTeX source code.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n"
            f"Talk type: {talk_type} ({minutes} minutes)\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_poster(paper_content: str, venue: str,
                    runtime: Runtime) -> str:
    """Generate a conference poster from a paper.

    Poster principles:
    - ONE page, visual-first. Tell the story in 60 seconds.
    - 4 columns for landscape A0, 3 for portrait A0.
    - Figures dominant, text minimal. Bullet points only.
    - Sections: Title/Authors, Motivation, Method (diagram),
      Key Results (1-2 figures), Conclusion, QR code.

    Color scheme: deep saturated colors for primary (visible from distance).
    Text: minimum 24pt body, 32pt section headers, 48pt+ title.

    Output: Complete LaTeX poster source code (tcbposter or baposter).
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Venue: {venue}\n\n"
            f"Paper:\n{paper_content}"
        )},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_speaker_notes(slides_content: str, runtime: Runtime) -> str:
    """Generate speaker notes / talk script for presentation slides.

    For each slide:
    - What to SAY (natural spoken language, not reading bullet points)
    - Timing hint (e.g. "~90 seconds")
    - Transition to next slide ("This leads us to...")

    Also generate:
    - Q&A preparation: 5 likely questions + suggested answers
    - Backup slides: what to prepare for tough questions

    Output: Structured speaker notes per slide + Q&A prep.
    """
    return runtime.exec(content=[
        {"type": "text", "text": slides_content},
    ])


def run_slides(
    paper_dir: str,
    venue: str = "NeurIPS",
    talk_type: str = "spotlight",
    minutes: int = 8,
    runtime: Runtime = None,
) -> dict:
    """Generate presentation slides from paper.

    Args:
        paper_dir:   Path to paper directory.
        venue:       Target venue.
        talk_type:   oral / spotlight / poster-talk / invited.
        minutes:     Talk duration.
        runtime:     LLM runtime.

    Returns:
        dict with slides LaTeX and speaker notes.
    """
    if runtime is None:
        raise ValueError("runtime is required")

    paper_dir = os.path.expanduser(paper_dir)
    parts = []
    for f in sorted(os.listdir(paper_dir)):
        if f.endswith(".tex"):
            with open(os.path.join(paper_dir, f), "r") as fh:
                parts.append(fh.read())
    paper_content = "\n".join(parts)[:15000]

    slides = generate_slides(
        paper_content=paper_content, venue=venue,
        talk_type=talk_type, minutes=minutes, runtime=runtime,
    )
    notes = generate_speaker_notes(slides_content=slides, runtime=runtime)

    # Save
    project_dir = os.path.dirname(paper_dir)
    slides_dir = os.path.join(project_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)

    with open(os.path.join(slides_dir, "slides.tex"), "w") as f:
        f.write(slides)
    with open(os.path.join(slides_dir, "speaker_notes.md"), "w") as f:
        f.write(notes)

    return {"slides": slides, "notes": notes}
