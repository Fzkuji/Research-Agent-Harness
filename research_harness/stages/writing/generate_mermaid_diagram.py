from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def generate_mermaid_diagram(description: str, runtime: Runtime) -> str:
    """Generate a Mermaid diagram from user requirements, with file output and
    syntax verification.

    Supported diagram types:
    - Flowchart: processes, decisions, steps
    - Sequence Diagram: interactions, messaging, API calls
    - Class Diagram: class structure, inheritance, associations
    - State Diagram: state machines, state transitions
    - ER Diagram: database design, entity relationships
    - Gantt Chart: project planning, timelines
    - Pie Chart: proportions, distributions
    - Mindmap: hierarchical structures, knowledge graphs
    - Timeline: historical events, milestones
    - Git Graph: branches, merges, versions
    - Quadrant Chart: four-quadrant analysis
    - Sankey Diagram: flow, conversions
    - XY Chart: line charts, bar charts
    - Block Diagram: system components, modules
    - Architecture Diagram: system architecture
    - Radar Chart: multi-dimensional comparison
    - User Journey: user experience flows

    Workflow:
    1. Analyze user description to determine the most suitable diagram type
    2. If the diagram involves mathematical notation, apply LaTeX math syntax rules
    3. Identify all components, connections, and data flow
    4. Generate syntactically correct Mermaid code
    5. Save TWO files:
       - figures/<diagram-name>.mmd: raw Mermaid source (no markdown fences)
       - figures/<diagram-name>.md: markdown with embedded mermaid code block
    6. Verify syntax by running mmdc (Mermaid CLI) if available, or npx fallback
    7. If verification fails, fix and retry (up to 3 iterations)
    8. Visual review: check all arrows point correctly, all blocks have correct
       labels, all requirements are present, layout is clean and readable

    Common pitfalls to avoid:
    - Escape special characters in labels: use quotes for labels with spaces
    - Use proper arrow syntax: --> for flowchart, ->> for sequence
    - Avoid reserved words as node IDs
    - Use descriptive kebab-case naming (e.g., auth-flow, system-architecture)

    Output: Mermaid code block + saved file paths + verification result.
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": description},
    ])
