from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"siblings": -1})
def comprehensive_lit_review(topic: str, subtopics: str,
                             runtime: Runtime) -> str:
    """Write a comprehensive, publication-ready related work section with
    communications-domain awareness.

    This produces a full Related Work section suitable for direct inclusion in a
    paper, deeper than a survey. Uses a knowledge-base-first retrieval strategy.

    Retrieval order (knowledge-base-first):
    1. Zotero library (if configured): search by topic, capture annotations/tags
    2. Obsidian vault (if configured): search notes, wikilinks, tags
    3. Local paper library: papers/*.pdf and literature/*.pdf
    4. IEEE Xplore (preferred for communications/EE topics)
    5. ScienceDirect
    6. ACM Digital Library
    7. Broader web (last resort)
    Graceful degradation: if a source is unavailable, skip silently.

    Venue priority (for communications topics):
    Tier A journals: JSAC, ToN, TWC, TCOM
    Tier A conferences: SIGCOMM, NSDI, MobiCom, CoNEXT, INFOCOM
    Tier B journals: TVT, WCL, Communications Letters, Computer Networks
    Tier B conferences: ICC, GLOBECOM, WCNC, PIMRC, MobiHoc

    Publication policy:
    - Prefer peer-reviewed journals and major conferences
    - Label workshop papers as "workshop", arXiv-only as "preprint"
    - If both preprint and formal version exist, cite formal version first
    - Include both foundational (pre-2022) and recent (2022-present) work

    Structure per subsection (choose progression or parallel style):

    Progression style:
    - Start with foundational concept, list existing works, end with limitations
      that motivate our approach.

    Parallel style:
    - Overview sentence -> subtopic 1 works -> subtopic 2 works -> our novelty.

    LaTeX citation rules:
    - Use \\\\citep{{}} for parenthetical citations, \\\\citet{{}} for textual citations
    - Never use citations as sentence subjects (wrong: "\\\\citet{{smith}} proposes..."
      -> right: "Smith et al. \\\\citep{{smith}} propose...")
    - Cite published versions over arXiv when available
    - Include recent work (within 2 years) for baselines
    - End each subsection discussing limitations of existing work vs our method

    Output: LaTeX related work section with proper citations.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Topic: {topic}\n\n"
            f"Subtopics to cover:\n{subtopics}"
        )},
    ])
