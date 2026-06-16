from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"callers": 0})
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
