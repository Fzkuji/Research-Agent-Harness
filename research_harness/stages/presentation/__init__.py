"""Stage: presentation"""

from research_harness.stages.presentation.generate_poster import generate_poster
from research_harness.stages.presentation.generate_slides import generate_slides
from research_harness.stages.presentation.generate_speaker_notes import generate_speaker_notes

import os
from typing import Optional
from openprogram.agentic_programming.runtime import Runtime


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


__all__ = ['generate_poster', 'generate_slides', 'generate_speaker_notes', 'run_slides']
