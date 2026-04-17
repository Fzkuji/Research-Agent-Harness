from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def extract_framework(direction: str, surveys_json: str,
                      current_framework_json: str,
                      runtime: Runtime) -> str:
    """Synthesize (or refresh) a topic framework from surveys and prior framework.

    You are building the backbone of a literature review: a topic tree that
    organizes the field. Source material:
    - The surveys' tables of contents (how experts partition the field)
    - The surveys' key claims (what boundaries/camps they identify)
    - Your own knowledge of the field
    - The prior framework (if any — treat as seed to refine, not overwrite)

    Workflow:
    1. Read the surveys. Focus on their TOCs. Different surveys cut the field
       differently — your job is to combine them, NOT pick one arbitrarily.
    2. If a prior framework is provided, keep its structure where it is still
       supported by the evidence. Change minimally.
    3. Build a tree of topics, 2–3 levels deep. Each node:
       - `name`: short, canonical name for the sub-field (no jargon beyond field norms)
       - `description`: one sentence — what belongs here, what doesn't
       - `source`: "survey" | "llm-induced" | "paper-induced"
                   (for nodes directly from a survey TOC, use "survey";
                    for nodes you add from your own knowledge, "llm-induced";
                    for nodes required by papers already placed, "paper-induced")
       - `open_questions`: 0–3 bullet points — what's unresolved in this sub-field
       - `children`: list of same-shape nodes (or [] for leaves)

    4. Return ONE JSON object, nothing else:
    ```json
    {
      "framework": {
        "name": "<direction>",
        "description": "...",
        "source": "llm-induced",
        "open_questions": [],
        "children": [
          { "name": "...", "description": "...", "source": "survey",
            "open_questions": ["..."], "children": [ ... ] }
        ]
      },
      "rationale": "2-4 sentences: how you merged the surveys' TOCs and what tradeoffs you made"
    }
    ```

    Rules:
    - Output ONLY the JSON — no markdown fence, no commentary.
    - Do NOT invent topics without evidence. If unsure, leave it out.
    - Do NOT make the tree too wide — prefer merging semi-redundant branches.
    - Leaves should be concrete enough that we can search papers for them.
    - Paths use "/" separators, e.g. "retrieval/dense retrieval/multi-vector".
      You do not need to output paths; consumers derive them from the tree.
    - The orchestrator already persists state — do NOT write extra files.

    Args:
        direction:               User's research direction (root of the tree).
        surveys_json:            JSON array of surveys in state (with toc + key_claims).
        current_framework_json:  JSON of existing framework (or "" for first run).
        runtime:                 LLM runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research direction: {direction}\n\n"
            f"Surveys in state:\n{surveys_json}\n\n"
            f"Prior framework (refine this, don't overwrite):\n"
            f"{current_framework_json or '(none — build from scratch)'}"
        )},
    ])
