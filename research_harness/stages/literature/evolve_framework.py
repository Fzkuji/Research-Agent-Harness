from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def evolve_framework(framework_json: str, papers_json: str,
                     surveys_json: str, audit_tail: str,
                     runtime: Runtime) -> str:
    """Revise the topic framework based on accumulated evidence.

    You are refactoring the topic tree. Evidence to consider:
    - Current framework (what we have now)
    - All annotated papers (topic_path per paper + contribution_summary)
    - All surveys (TOC + key claims)
    - Recent audit tail (what's been changing recently — don't flip-flop)

    Decide what `delta` operations are justified. Available ops:
    - `add`    { "op":"add",    "path":"parent/new_leaf", "node":{...} }
    - `merge`  { "op":"merge",  "paths":["a","b"], "new_path":"merged", "new_node":{...} }
    - `split`  { "op":"split",  "path":"a/too_broad", "new_children":[ {...}, {...} ] }
    - `rename` { "op":"rename", "path":"old", "new_name":"better_name" }
    - `drop`   { "op":"drop",   "path":"a/empty_or_redundant" }

    When to apply each:
    - `add`:    orphan papers cluster around a missing topic; a survey's branch
                has no counterpart in our tree.
    - `merge`:  two siblings attract the same papers; their descriptions overlap.
    - `split`:  a node has >~15 papers of visibly distinct sub-methods.
    - `rename`: current name misleads or misaligns with field terminology.
    - `drop`:   node has 0 papers and no strong survey support.

    Be CONSERVATIVE. Prefer no change to churn. Only apply ops you can justify
    from the evidence. Do not rename for taste alone.

    Workflow:
    1. Scan orphan papers. Cluster them. If a cluster is coherent and >=3
       papers, propose an `add` (or a `split` on an existing broad node).
    2. Scan sibling overlap. If two sibling topics share >50% of their papers'
       contribution domain, propose a `merge`.
    3. Scan oversized leaves. If >=15 papers, propose `split`.
    4. Flag empty leaves (0 papers and no survey mention) for `drop`.
    5. Apply the operations in order; compute the resulting tree.
    6. For papers whose old `topic_path` is affected, propose a new placement
       (the orchestrator will update them; do NOT re-annotate contribution).

    7. Return ONE JSON object, nothing else:
    ```json
    {
      "new_framework": { ...tree... },
      "deltas": [ { "op": "...", ... }, ... ],
      "paper_relocations": [
        { "paper_id": "...", "old_path": "a/b", "new_path": "a/c" }
      ],
      "rationale": "2-6 sentences justifying each op by evidence",
      "stable": false
    }
    ```

    - Set `stable: true` if NO non-trivial op was justified (no add/merge/
      split/drop; rename-only counts as "stable" for convergence purposes).
    - `paper_relocations` only lists papers whose path literally changed.

    Rules:
    - Output ONLY the JSON.
    - `new_framework` must be a complete, consistent tree (not a patch).
    - If `deltas` is empty, `new_framework` equals the input framework.
    - The orchestrator already persists state — do NOT write extra files.

    Args:
        framework_json:  Current framework tree.
        papers_json:     All annotated papers (including orphans).
        surveys_json:    All surveys.
        audit_tail:      Last 5–10 audit entries as free text.
        runtime:         LLM runtime.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Current framework:\n{framework_json}\n\n"
            f"Annotated papers (+orphans):\n{papers_json}\n\n"
            f"Surveys:\n{surveys_json}\n\n"
            f"Recent audit tail:\n{audit_tail or '(none)'}"
        )},
    ])
