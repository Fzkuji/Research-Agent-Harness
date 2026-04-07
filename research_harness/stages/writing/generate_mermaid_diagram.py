from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_mermaid_diagram(description: str, runtime: Runtime) -> str:
    """Generate a Mermaid diagram from a description.

    Supports: flowchart, sequence diagram, class diagram, ER diagram,
    Gantt chart, state diagram, pie chart, mindmap, timeline, and more.

    Steps:
    1. Determine the best diagram type for the description.
    2. Generate syntactically correct Mermaid code.
    3. Verify syntax (no unescaped special chars, proper arrow syntax).
    4. Save as .mmd file to figures/ directory.

    Common pitfalls to avoid:
    - Escape special characters in labels: use quotes for labels with spaces
    - Use proper arrow syntax: --> for flowchart, ->> for sequence
    - Avoid reserved words as node IDs

    Output: Mermaid code block + saved file path.
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])
